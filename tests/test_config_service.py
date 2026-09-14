"""Tests for config_service: turning users + template into a filled config.

Run from the repo root:
    python -m unittest tests.test_config_service -v
"""

import unittest

from backend.services import config_service


def _template():
    """A tiny stand-in for a real Xray template with one of each piece.

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

        config, warnings = config_service.build_config(_template(), users)

        self.assertEqual(
            config["inbounds"][0]["settings"]["clients"],
            [{"id": "u1", "email": "alice@OUTBOUND"}],
        )
        self.assertEqual(
            config["routing"]["rules"],
            [
                {},
                {"user": ["regexp:.*@OUTBOUND$"], "outboundTag": "OUTBOUND"},
                {"user": ["regexp:.*@BLOCK$"], "outboundTag": "BLOCK"},
                {"outboundTag": "BLOCK"},
            ],
        )
        self.assertEqual(warnings, [])

    def test_template_not_mutated(self):
        template = _template()
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config_service.build_config(template, users)

        self.assertEqual(template, _template())

    def test_opaque_parts_preserved(self):
        template = _template()
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(template, users)

        self.assertEqual(config["log"], template["log"])
        self.assertEqual(config["outbounds"], template["outbounds"])
        self.assertEqual(config["inbounds"][0]["port"], 443)

    def test_unused_vless_inbound_gets_empty_clients(self):
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(_template(), users)

        self.assertEqual(config["inbounds"][1]["settings"]["clients"], [])

    def test_disabled_user_excluded(self):
        users = [
            _user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"}),
            _user("bob", ["REALITY"], ["OUTBOUND"], {"bob@OUTBOUND": "u2"},
                  status="disabled"),
        ]

        config, _ = config_service.build_config(_template(), users)

        self.assertEqual(
            config["inbounds"][0]["settings"]["clients"],
            [{"id": "u1", "email": "alice@OUTBOUND"}],
        )

    def test_no_block_outbound_skips_catch_all(self):
        template = _template()
        template["outbounds"] = [{"tag": "OUTBOUND", "protocol": "wireguard"}]

        config, warnings = config_service.build_config(template, [])

        self.assertIn("no BLOCK outbound; skipping catch-all rule", warnings)
        self.assertEqual(len(config["routing"]["rules"]), 2)

    def test_missing_routing_is_auto_created(self):
        template = _template()
        del template["routing"]
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, warnings = config_service.build_config(template, users)

        self.assertIn("routing", config)
        self.assertGreater(len(config["routing"]["rules"]), 0)

    def test_user_rules_are_preserved_and_extended(self):
        template = _template()
        user_rule = {
            "user": ["regexp:.*@CUSTOM$"],
            "outboundTag": "OUTBOUND",
        }
        template["routing"]["rules"] = [user_rule]
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(template, users)

        self.assertEqual(config["routing"]["rules"][0], user_rule)
        self.assertGreater(len(config["routing"]["rules"]), 1)

    def test_routing_other_keys_preserved(self):
        template = _template()
        template["routing"]["domainStrategy"] = "IPOnDemand"
        users = [_user("alice", ["REALITY"], ["OUTBOUND"], {"alice@OUTBOUND": "u1"})]

        config, _ = config_service.build_config(template, users)

        self.assertEqual(config["routing"]["domainStrategy"], "IPOnDemand")
        self.assertIn("rules", config["routing"])


if __name__ == "__main__":
    unittest.main()
