"""Tests for config_service: turning users + config into a filled runtime config.

Run from the repo root:
    python -m unittest tests.test_config_service -v
"""

import unittest

from backend.services import config_service


def _config():
    """A tiny stand-in for a real Xray config with one of each piece.

    Why so small: config_service must only touch routing.rules and VLESS
    clients; a small fixture makes the "everything else survives" checks
    readable.
    """
    return {
        "log": {"loglevel": "debug"},
        "routing": {"rules": [{}]},
        "inbounds": [
            {
                "tag": "REALITY",
                "protocol": "vless",
                "port": 443,
                "settings": {"clients": [], "decryption": "none"},
            },
            {
                "tag": "XHTTP",
                "protocol": "vless",
                "listen": "sock",
                "settings": {"clients": [{}]},
            },
        ],
        "outbounds": [
            {"tag": "OUTBOUND", "protocol": "wireguard"},
            {"tag": "BLOCK", "protocol": "blackhole"},
        ],
    }


def _user(username, inbounds, outbounds, uuids, status="active"):
    """Build one user dict in the shape db.list_users returns."""
    return {
        "username": username,
        "status": status,
        "allowed_inbounds": inbounds,
        "allowed_outbounds": outbounds,
        "uuids": uuids,
    }


class TestBuildConfig(unittest.TestCase):
    def test_clients_and_rules_filled(self):
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, warnings = config_service.build_config(_config(), users)

        self.assertEqual(
            config["inbounds"][0]["settings"]["clients"],
            [{"id": "u1", "email": "alice@OUTBOUND"}],
        )
        self.assertEqual(
            config["routing"]["rules"],
            [
                {},
                {"user": ["regexp:.*@OUTBOUND$"], "outboundTag": "OUTBOUND"},
                {"outboundTag": "BLOCK"},
            ],
        )
        self.assertEqual(warnings, [])

    def test_config_not_mutated(self):
        source = _config()
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config_service.build_config(source, users)

        self.assertEqual(source, _config())

    def test_opaque_parts_preserved(self):
        source = _config()
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(source, users)

        self.assertEqual(config["log"], source["log"])
        self.assertEqual(config["outbounds"], source["outbounds"])
        self.assertEqual(config["inbounds"][0]["port"], 443)

    def test_unused_vless_inbound_gets_empty_clients(self):
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(_config(), users)

        self.assertEqual(config["inbounds"][1]["settings"]["clients"], [])

    def test_disabled_user_excluded(self):
        users = [
            _user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"}),
            _user("bob", ["REALITY"], ["OUTBOUND"], {"bob@OUTBOUND": "u2"},
                  status="disabled"),
        ]

        config, _ = config_service.build_config(_config(), users)

        self.assertEqual(
            config["inbounds"][0]["settings"]["clients"],
            [{"id": "u1", "email": "alice@OUTBOUND"}],
        )

    def test_block_auto_injected_and_catch_all_present(self):
        source = _config()
        source["outbounds"] = [{"tag": "OUTBOUND", "protocol": "wireguard"}]

        config, warnings = config_service.build_config(source, [])

        tags = [o["tag"] for o in config["outbounds"]]
        self.assertIn("BLOCK", tags)
        self.assertNotIn("no BLOCK", warnings)
        self.assertEqual(
            config["routing"]["rules"],
            [
                {},
                {"user": ["regexp:.*@OUTBOUND$"], "outboundTag": "OUTBOUND"},
                {"outboundTag": "BLOCK"},
            ],
        )

    def test_missing_routing_is_auto_created(self):
        source = _config()
        del source["routing"]
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, warnings = config_service.build_config(source, users)

        self.assertIn("routing", config)
        self.assertGreater(len(config["routing"]["rules"]), 0)

    def test_user_rules_are_preserved_and_extended(self):
        source = _config()
        user_rule = {
            "user": ["regexp:.*@CUSTOM$"],
            "outboundTag": "OUTBOUND",
        }
        source["routing"]["rules"] = [user_rule]
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(source, users)

        self.assertEqual(config["routing"]["rules"][0], user_rule)
        self.assertGreater(len(config["routing"]["rules"]), 1)

    def test_routing_other_keys_preserved(self):
        source = _config()
        source["routing"]["domainStrategy"] = "IPOnDemand"
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(source, users)

        self.assertEqual(config["routing"]["domainStrategy"], "IPOnDemand")
        self.assertIn("rules", config["routing"])

    def test_outbound_tags_excludes_block(self):
        source = _config()

        tags = config_service.outbound_tags(source)

        self.assertNotIn("BLOCK", tags)
        self.assertIn("OUTBOUND", tags)


if __name__ == "__main__":
    unittest.main()
