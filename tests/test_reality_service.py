"""Tests for the REALITY key service: generation, storage, rotation, listing.

Run from the repo root:
    python -m unittest tests.test_reality_service -v
"""

import os
import tempfile
import unittest

from backend import db
from backend.services import reality_service


def _fresh_conn():
    """Create a database in a brand-new temp file and initialize it.

    Why a temp file (not the real data/panel.db): tests must never touch
    real data, and each test gets its own empty database so they cannot
    interfere with each other.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = db.connect(path)
    db.init_schema(conn)
    return conn


def _config():
    """A small config with one REALITY inbound and one plain inbound."""
    return {
        "inbounds": [
            {
                "tag": "REALITY",
                "protocol": "vless",
                "settings": {"clients": []},
                "streamSettings": {
                    "network": "raw",
                    "security": "reality",
                    "realitySettings": {"privateKey": "operator-owned-key"},
                },
            },
            {"tag": "PLAIN", "protocol": "vless", "settings": {"clients": []}},
        ],
        "outbounds": [{"tag": "OUT", "protocol": "freedom"}],
    }


class TestEnsureKeys(unittest.TestCase):
    def setUp(self):
        self.conn = _fresh_conn()

    def test_generates_and_stores_key_for_missing_inbound(self):
        keys = reality_service.ensure_keys(self.conn, _config())

        self.assertIn("REALITY", keys)
        stored = db.list_reality_keys(self.conn)["REALITY"]
        self.assertEqual(keys["REALITY"], stored["private_key"])
        self.assertTrue(stored["created_at"] > 0)

    def test_existing_key_is_reused(self):
        first = reality_service.ensure_keys(self.conn, _config())
        db.upsert_reality_key(self.conn, "REALITY", "pinned-key", 123)

        second = reality_service.ensure_keys(self.conn, _config())

        self.assertEqual(second["REALITY"], "pinned-key")
        self.assertNotEqual(second["REALITY"], first["REALITY"])

    def test_non_reality_inbound_gets_no_key(self):
        reality_service.ensure_keys(self.conn, _config())

        self.assertNotIn("PLAIN", db.list_reality_keys(self.conn))

    def test_missing_stream_settings_is_ignored(self):
        config = {"inbounds": [{"tag": "BARE", "protocol": "vless"}], "outbounds": []}

        reality_service.ensure_keys(self.conn, config)

        self.assertEqual(db.list_reality_keys(self.conn), {})


class TestRotateKey(unittest.TestCase):
    def setUp(self):
        self.conn = _fresh_conn()
        reality_service.ensure_keys(self.conn, _config())

    def test_rotation_replaces_key_and_timestamp(self):
        old = db.list_reality_keys(self.conn)["REALITY"]

        reality_service.rotate_key(self.conn, "REALITY")

        new = db.list_reality_keys(self.conn)["REALITY"]
        self.assertNotEqual(new["private_key"], old["private_key"])
        self.assertGreaterEqual(new["created_at"], old["created_at"])

    def test_rotation_returns_new_private_key(self):
        returned = reality_service.rotate_key(self.conn, "REALITY")

        self.assertEqual(returned, db.list_reality_keys(self.conn)["REALITY"]["private_key"])


class TestListKeys(unittest.TestCase):
    def setUp(self):
        self.conn = _fresh_conn()

    def test_rows_follow_config_order_with_public_keys(self):
        reality_service.ensure_keys(self.conn, _config())

        rows = reality_service.list_keys(self.conn, _config())

        self.assertEqual([row["inbound"] for row in rows], ["REALITY"])
        self.assertEqual(
            rows[0]["public_key"],
            reality_service.public_key(self.conn, "REALITY"),
        )
        self.assertTrue(rows[0]["created_at"] > 0)

    def test_pending_inbound_shows_nulls(self):
        # config on disk changed but sync has not run: no key stored yet
        rows = reality_service.list_keys(self.conn, _config())

        self.assertEqual(rows, [{"inbound": "REALITY", "public_key": None, "created_at": None}])


if __name__ == "__main__":
    unittest.main()
