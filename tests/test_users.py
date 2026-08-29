"""Tests for the user models, the UUID rule, and the db CRUD layer.

Uses the standard library's unittest so there are no extra dependencies.

Run from the repo root (with the lesserv env active):
    python -m unittest tests.test_users -v
"""

import os
import tempfile
import unittest

from pydantic import ValidationError

from backend import db
from backend.models import UserCreate, UserUpdate
from backend.services import user_service


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


class TestUserCreateModel(unittest.TestCase):
    def test_valid_username_and_defaults(self):
        user = UserCreate(username="alice", allowed_outbounds=["JAPAN"])

        self.assertEqual(user.username, "alice")
        self.assertEqual(user.status, "active")
        self.assertEqual(user.allowed_inbounds, [])
        self.assertIsNone(user.expire)
        self.assertIsNone(user.note)

    def test_username_with_at_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(username="ali@ce")

    def test_blank_username_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(username="   ")

    def test_long_username_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(username="a" * 33)

    def test_bad_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(username="alice", status="banned")


class TestEnsureUuids(unittest.TestCase):
    def test_creates_one_uuid_per_outbound(self):
        uuids = user_service.ensure_uuids("alice", ["JAPAN", "HK"], {})

        self.assertEqual(set(uuids), {"alice@JAPAN", "alice@HK"})

    def test_existing_uuids_are_stable(self):
        first = user_service.ensure_uuids("alice", ["JAPAN"], {})
        second = user_service.ensure_uuids("alice", ["JAPAN"], first)

        self.assertEqual(first, second)

    def test_new_outbound_only_adds_new_uuid(self):
        first = user_service.ensure_uuids("alice", ["JAPAN"], {})
        second = user_service.ensure_uuids("alice", ["JAPAN", "HK"], first)

        self.assertEqual(first["alice@JAPAN"], second["alice@JAPAN"])
        self.assertIn("alice@HK", second)


class TestDbCrud(unittest.TestCase):
    def setUp(self):
        self.conn = _fresh_conn()

    def tearDown(self):
        self.conn.close()

    def test_create_then_get_roundtrip(self):
        payload = UserCreate(username="bob", allowed_outbounds=["JAPAN"])
        created = user_service.create_user(self.conn, payload)

        fetched = db.get_user(self.conn, "bob")

        self.assertEqual(fetched["username"], "bob")
        self.assertEqual(fetched["status"], "active")
        self.assertEqual(fetched["allowed_outbounds"], ["JAPAN"])
        self.assertEqual(fetched["uuids"], created["uuids"])

    def test_get_missing_user_returns_none(self):
        self.assertIsNone(db.get_user(self.conn, "ghost"))

    def test_delete_reports_whether_user_existed(self):
        user_service.create_user(self.conn, UserCreate(username="bob"))

        self.assertTrue(db.delete_user(self.conn, "bob"))
        self.assertFalse(db.delete_user(self.conn, "bob"))

    def test_update_keeps_untouched_fields_and_uuids(self):
        created = user_service.create_user(
            self.conn,
            UserCreate(username="bob", allowed_inbounds=["REALITY"],
                       allowed_outbounds=["JAPAN"], note="old"),
        )

        updated = user_service.update_user(
            self.conn, "bob", UserUpdate(note="new")
        )

        self.assertEqual(updated["note"], "new")
        self.assertEqual(updated["allowed_inbounds"], ["REALITY"])
        self.assertEqual(updated["allowed_outbounds"], ["JAPAN"])
        self.assertEqual(updated["uuids"], created["uuids"])

    def test_update_missing_user_returns_none(self):
        self.assertIsNone(
            user_service.update_user(self.conn, "ghost", UserUpdate(note="x"))
        )


if __name__ == "__main__":
    unittest.main()
