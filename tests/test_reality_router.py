"""Tests for the REALITY router endpoints, called directly (no HTTP layer).

Run from the repo root:
    python -m unittest tests.test_reality_router -v
"""

import tempfile
import unittest
from unittest import mock

from backend import db
from backend.services import xray_service


def _reality_config():
    """One REALITY inbound and one plain one — the minimum the router needs."""
    return {
        "inbounds": [
            {
                "tag": "REALITY",
                "protocol": "vless",
                "streamSettings": {
                    "network": "raw",
                    "security": "reality",
                    "realitySettings": {"privateKey": "x"},
                },
            },
            {"tag": "PLAIN", "protocol": "vless"},
        ],
        "outbounds": [],
    }


def _fresh_conn():
    """A throwaway database in a temp file; mirrors tests/test_users.py."""
    from backend import db

    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    conn = db.connect(path)
    db.init_schema(conn)
    return conn


class TestRealityRouter(unittest.TestCase):
    def setUp(self):
        self.conn = _fresh_conn()

    @mock.patch("backend.routers.reality.reality_service.list_keys")
    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_get_keys_returns_envelope(self, mock_load, mock_list):
        mock_load.return_value = _reality_config()
        mock_list.return_value = [
            {"inbound": "REALITY", "public_key": "pbk", "created_at": 1}
        ]

        from backend.routers.reality import get_reality_keys

        self.assertEqual(
            get_reality_keys(conn=self.conn),
            {"keys": [{"inbound": "REALITY", "public_key": "pbk", "created_at": 1}]},
        )
        mock_list.assert_called_once_with(self.conn, mock_load.return_value)

    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_get_keys_404_when_no_config(self, mock_load):
        mock_load.return_value = None

        from backend.routers.reality import get_reality_keys
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            get_reality_keys(conn=self.conn)
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.reality.xray_service.sync")
    @mock.patch("backend.routers.reality.reality_service.rotate_key")
    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_rotate_all_rotates_every_reality_inbound(self, mock_load, mock_rotate, mock_sync):
        mock_load.return_value = _reality_config()

        from backend.routers.reality import rotate_all_keys

        result = rotate_all_keys(conn=self.conn)

        self.assertEqual(result, {"rotated": ["REALITY"]})
        mock_rotate.assert_called_once_with(self.conn, "REALITY")
        mock_sync.assert_called_once_with(self.conn)

    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_rotate_all_404_when_no_reality_inbound(self, mock_load):
        mock_load.return_value = {"inbounds": [{"tag": "PLAIN", "protocol": "vless"}],
                                  "outbounds": []}

        from backend.routers.reality import rotate_all_keys
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            rotate_all_keys(conn=self.conn)
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.reality.xray_service.sync")
    @mock.patch("backend.routers.reality.reality_service.rotate_key")
    @mock.patch("backend.routers.reality.reality_service.public_key")
    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_rotate_one_returns_new_public_key(self, mock_load, mock_pbk,
                                               mock_rotate, mock_sync):
        mock_load.return_value = _reality_config()
        mock_pbk.return_value = "new-public-key"

        from backend.routers.reality import rotate_key

        result = rotate_key("REALITY", conn=self.conn)

        self.assertEqual(result, {"inbound": "REALITY", "public_key": "new-public-key"})
        mock_rotate.assert_called_once_with(self.conn, "REALITY")
        mock_sync.assert_called_once_with(self.conn)

    @mock.patch("backend.routers.reality.xray_service.load_config")
    def test_rotate_one_404_for_unknown_tag(self, mock_load):
        mock_load.return_value = _reality_config()

        from backend.routers.reality import rotate_key
        from fastapi import HTTPException

        for tag in ("NOPE", "PLAIN"):  # missing entirely, and not REALITY
            with self.assertRaises(HTTPException) as ctx:
                rotate_key(tag, conn=self.conn)
            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
