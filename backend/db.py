"""All SQLite access for the panel lives in this file.

Nothing else in the project talks to the database directly, so every
query is visible in one place.

Lists (allowed_inbounds, allowed_outbounds) and the UUID map are stored
as JSON text because they are just strings to us; if they ever grow into
real relationships we can migrate them to proper tables.
"""

import json
import os
import sqlite3
import time


def connect(path):
    """Open (and return) a SQLite connection at `path`.

    Why this exists: one place decides *how* we talk to SQLite —
    dict-like rows via row_factory, and a data folder that creates
    itself on first run — so the rest of the code stays simple.

    Why check_same_thread=False: FastAPI runs sync endpoints in a
    worker-thread pool, so a connection opened at startup (in the
    main thread) gets used from other threads. SQLite normally
    refuses that; this flag allows it. It is safe here because the
    panel is a single, low-traffic process.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn):
    """Create the users table if it does not exist yet.

    Why "IF NOT EXISTS": this runs on every startup; the first run
    creates the table, later runs are no-ops.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username          TEXT PRIMARY KEY,
            status            TEXT NOT NULL DEFAULT 'active',
            expire            INTEGER,
            allowed_inbounds  TEXT NOT NULL DEFAULT '[]',
            allowed_outbounds TEXT NOT NULL DEFAULT '[]',
            uuids             TEXT NOT NULL DEFAULT '{}',
            note              TEXT,
            created_at        INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def seed(conn):
    """Insert one demo user so a fresh install has something to show.

    Why "INSERT OR IGNORE": it is idempotent — restarting the panel
    never duplicates the row and never errors.

    Why these specific tags: they mirror the REALITY/XHTTP inbound and
    OUTBOUND/BLOCK outbound layout of a typical config, so the demo
    user's client actually matches a routing rule instead of falling
    into the BLOCK catch-all.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO users
            (username, status, allowed_inbounds, allowed_outbounds,
             uuids, note, created_at)
        VALUES
            (?, 'active', ?, ?, ?, 'seeded demo user', ?)
        """,
        (
            "demo",
            json.dumps(["REALITY", "XHTTP"]),
            json.dumps(["OUTBOUND"]),
            json.dumps({"demo@OUTBOUND": "123e4567-e89b-12d3-a456-426614174000"}),
            int(time.time()),
        ),
    )
    conn.commit()


def list_users(conn):
    """Return every user as a list of dicts, oldest first."""
    rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [row_to_dict(row) for row in rows]


def get_user(conn, username):
    """Fetch one user by username, or None when not found.

    Why this exists: the API needs to answer "does this user exist?" (for
    404s) and the update flow needs the current values to merge into.
    """
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row_to_dict(row) if row else None


def create_user(conn, user):
    """Insert one full user row.

    Why it takes a complete dict (uuids and created_at included): deciding
    what values a new user gets is business logic that belongs to the
    service layer; this function only knows how to store what it is given.
    """
    conn.execute(
        """
        INSERT INTO users
            (username, status, expire, allowed_inbounds, allowed_outbounds,
             uuids, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["username"],
            user["status"],
            user["expire"],
            json.dumps(user["allowed_inbounds"]),
            json.dumps(user["allowed_outbounds"]),
            json.dumps(user["uuids"]),
            user["note"],
            user["created_at"],
        ),
    )
    conn.commit()


def replace_user(conn, user):
    """Overwrite every editable column of an existing user row.

    Why a full overwrite instead of a partial UPDATE: the service layer
    merges partial changes into a complete user first, so this stays one
    fixed SQL statement with no dynamic column list to build.
    """
    conn.execute(
        """
        UPDATE users SET
            status = ?, expire = ?, allowed_inbounds = ?, allowed_outbounds = ?,
            uuids = ?, note = ?, created_at = ?
        WHERE username = ?
        """,
        (
            user["status"],
            user["expire"],
            json.dumps(user["allowed_inbounds"]),
            json.dumps(user["allowed_outbounds"]),
            json.dumps(user["uuids"]),
            user["note"],
            user["created_at"],
            user["username"],
        ),
    )
    conn.commit()


def delete_user(conn, username):
    """Remove a user row; return True if one was deleted, False if not found.

    Why a return value: the router turns False into a 404 without needing
    a separate existence check first.
    """
    cursor = conn.execute(
        "DELETE FROM users WHERE username = ?", (username,)
    )
    conn.commit()
    return cursor.rowcount > 0


def row_to_dict(row):
    """Convert one SQLite row to a plain dict and decode its JSON columns.

    Why this exists: SQLite has no list/dict types, so we store JSON
    text; this is the single spot that turns it back into real
    structures for the API.
    """
    user = dict(row)
    user["allowed_inbounds"] = json.loads(user["allowed_inbounds"])
    user["allowed_outbounds"] = json.loads(user["allowed_outbounds"])
    user["uuids"] = json.loads(user["uuids"])
    return user
