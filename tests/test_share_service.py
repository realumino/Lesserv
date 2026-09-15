"""Tests for share link generation.

Run:
    python -m unittest tests.test_share_service -v
"""

import unittest
from unittest import mock

from backend.services import share_service


class TestShareService(unittest.TestCase):
    """Build VLESS URIs from users and the Xray config."""

    def _config(self):
        """Return a config that exercises raw/reality, xhttp, and ws."""
        return {
            "inbounds": [
                {
                    "tag": "REALITY_IN",
                    "protocol": "vless",
                    "listen": "0.0.0.0",
                    "port": 443,
                    "settings": {"flow": "xtls-rprx-vision"},
                    "streamSettings": {
                        "network": "raw",
                        "security": "reality",
                        "realitySettings": {
                            "serverNames": ["apple.com"],
                            "privateKey": "sMS4KcvOCag9dZsYPa3sFfVLSn3IGNEI34B7ENhGBFE",
                            "shortIds": ["1234"],
                        },
                    },
                },
                {
                    "tag": "XHTTP_IN",
                    "protocol": "vless",
                    "listen": "203.0.113.5",
                    "port": 8080,
                    "streamSettings": {
                        "network": "xhttp",
                        "xhttpSettings": {
                            "path": "/xhttp-path",
                            "host": "xhttp.example.com",
                            "mode": "auto",
                        },
                    },
                },
                {
                    "tag": "WS_IN",
                    "protocol": "vless",
                    "listen": "::",
                    "port": 8443,
                    "streamSettings": {
                        "network": "ws",
                        "wsSettings": {
                            "path": "/ws-path",
                            "host": "ws.example.com",
                        },
                    },
                },
                {"tag": "HTTP_ONLY", "protocol": "http", "port": 80},
            ],
            "outbounds": [
                {"tag": "JAPAN", "protocol": "freedom"},
                {"tag": "HK", "protocol": "freedom"},
            ],
        }

    def _user(self, inbounds=None):
        """Return a test user; default inbounds exclude the non-VLESS one."""
        return {
            "username": "alice",
            "status": "active",
            "allowed_inbounds": inbounds or ["REALITY_IN", "XHTTP_IN", "WS_IN"],
            "allowed_outbounds": ["JAPAN"],
            "uuids": {
                "alice@JAPAN": "11111111-1111-1111-1111-111111111111",
            },
        }

    def test_raw_reality_link(self):
        """REALITY inbound produces a correctly ordered vless:// URI."""
        links, warnings = share_service.links_for_user(
            self._user(["REALITY_IN"]), self._config(), "example.com"
        )

        self.assertEqual(len(links), 1)
        reality = links[0]
        self.assertEqual(reality["outbound"], "JAPAN")
        self.assertIn("vless://11111111-", reality["uri"])
        self.assertIn("example.com:443", reality["uri"])
        self.assertIn("type=tcp", reality["uri"])
        self.assertIn("security=reality", reality["uri"])
        self.assertIn("sni=apple.com", reality["uri"])
        self.assertIn("pbk=w_OZ1uUriCcd12KatYIFBJulAFDGNp9V1wL_XiQBt08", reality["uri"])
        self.assertIn("sid=1234", reality["uri"])
        self.assertIn("fp=chrome", reality["uri"])
        self.assertIn("encryption=none", reality["uri"])
        self.assertIn("flow=xtls-rprx-vision", reality["uri"])
        self.assertEqual(warnings, [])

    def test_xhttp_link(self):
        """XHTTP inbound uses address fallback, path, host, and mode."""
        links, warnings = share_service.links_for_user(
            self._user(["XHTTP_IN"]), self._config(), ""
        )

        self.assertEqual(len(links), 1)
        self.assertIn("203.0.113.5:8080", links[0]["uri"])
        self.assertIn("type=xhttp", links[0]["uri"])
        self.assertIn("path=%2Fxhttp-path", links[0]["uri"])
        self.assertIn("host=xhttp.example.com", links[0]["uri"])
        self.assertIn("mode=auto", links[0]["uri"])
        self.assertNotIn("flow=", links[0]["uri"])
        self.assertEqual(warnings, [])

    def test_non_vless_inbound_is_skipped(self):
        """HTTP inbound is skipped with a warning."""
        links, warnings = share_service.links_for_user(
            self._user(["REALITY_IN", "HTTP_ONLY"]),
            self._config(),
            "example.com",
        )
        tags = [link["inbound"] for link in links]

        self.assertEqual(tags, ["REALITY_IN"])
        self.assertIn("skipping non-vless inbound 'HTTP_ONLY'", warnings)

    def test_unknown_outbound_warns(self):
        """An allowed outbound not in the config is skipped."""
        user = self._user(["REALITY_IN"])
        user["allowed_outbounds"] = ["NOWHERE"]
        links, warnings = share_service.links_for_user(
            user, self._config(), "example.com"
        )

        self.assertEqual(links, [])
        self.assertIn("unknown outbound 'NOWHERE'", warnings)

    def test_disabled_user_generates_links_with_warning(self):
        """Disabled users still get links, but a warning is included."""
        user = self._user(["REALITY_IN"])
        user["status"] = "disabled"
        links, warnings = share_service.links_for_user(
            user, self._config(), "example.com"
        )

        self.assertTrue(links)
        self.assertIn("user alice is disabled", warnings)

    def test_wildcard_listen_ignored_when_no_configured_address(self):
        """0.0.0.0 and :: listens do not provide a usable address."""
        links, warnings = share_service.links_for_user(
            self._user(), self._config(), ""
        )
        tags = [link["inbound"] for link in links]

        self.assertEqual(tags, ["XHTTP_IN"])
        self.assertIn("no address for inbound 'REALITY_IN'", warnings)
        self.assertIn("no address for inbound 'WS_IN'", warnings)

    def test_has_usable_address(self):
        """Detect when at least one inbound has a real listen address."""
        self.assertTrue(
            share_service.has_usable_address(self._config(), "example.com")
        )
        # With no configured address, XHTTP_IN's real IP is still usable.
        self.assertTrue(share_service.has_usable_address(self._config(), ""))

        config = {"inbounds": [{"tag": "ONLY", "listen": "0.0.0.0"}]}
        self.assertFalse(share_service.has_usable_address(config, ""))


class TestShareRouter(unittest.TestCase):
    """GET /api/users/{username}/links endpoint."""

    @mock.patch("backend.routers.users.xray_service.load_config")
    @mock.patch("backend.routers.users.settings.SERVER_ADDRESS", "example.com")
    @mock.patch("backend.routers.users.db.get_user")
    def test_returns_links(self, mock_get_user, mock_load_config):
        mock_get_user.return_value = {
            "username": "alice",
            "status": "active",
            "allowed_inbounds": ["REALITY_IN"],
            "allowed_outbounds": ["JAPAN"],
            "uuids": {"alice@JAPAN": "11111111-1111-1111-1111-111111111111"},
        }
        mock_load_config.return_value = {
            "inbounds": [
                {
                    "tag": "REALITY_IN",
                    "protocol": "vless",
                    "listen": "0.0.0.0",
                    "port": 443,
                    "streamSettings": {
                        "network": "raw",
                        "security": "reality",
                        "realitySettings": {
                            "serverNames": ["apple.com"],
                            "privateKey": "sMS4KcvOCag9dZsYPa3sFfVLSn3IGNEI34B7ENhGBFE",
                            "shortIds": [""],
                        },
                    },
                }
            ],
            "outbounds": [{"tag": "JAPAN", "protocol": "freedom"}],
        }

        from backend.routers.users import get_user_links
        result = get_user_links("alice", conn=mock.MagicMock())

        self.assertEqual(result["username"], "alice")
        self.assertEqual(len(result["links"]), 1)
        self.assertIn("vless://", result["links"][0]["uri"])

    @mock.patch("backend.routers.users.db.get_user")
    def test_404_when_user_missing(self, mock_get_user):
        mock_get_user.return_value = None
        from backend.routers.users import get_user_links
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            get_user_links("ghost", conn=mock.MagicMock())
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.users.xray_service.load_config")
    @mock.patch("backend.routers.users.db.get_user")
    def test_503_when_config_missing(self, mock_get_user, mock_load_config):
        mock_get_user.return_value = {"username": "alice"}
        mock_load_config.return_value = None
        from backend.routers.users import get_user_links
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            get_user_links("alice", conn=mock.MagicMock())
        self.assertEqual(ctx.exception.status_code, 503)

    @mock.patch("backend.routers.users.xray_service.load_config")
    @mock.patch("backend.routers.users.settings.SERVER_ADDRESS", "")
    @mock.patch("backend.routers.users.db.get_user")
    def test_409_when_address_missing(self, mock_get_user, mock_load_config):
        mock_get_user.return_value = {"username": "alice"}
        mock_load_config.return_value = {
            "inbounds": [
                {"tag": "IN", "protocol": "vless", "listen": "0.0.0.0", "port": 443}
            ],
            "outbounds": [],
        }
        from backend.routers.users import get_user_links
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            get_user_links("alice", conn=mock.MagicMock())
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
