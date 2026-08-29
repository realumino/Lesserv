"""Business rules for users: UUID generation and update merging.

Why this layer exists: routers should only handle HTTP concerns (status
codes, JSON in/out) and db.py only knows SQL. Everything that is a *rule* —
how UUIDs are minted, what "update" means — lives here, so milestone 2 can
add "rebuild config + restart Xray after any change" without touching the
routers.
"""

import time
import uuid

from backend import db
from backend.models import UserCreate, UserUpdate


def ensure_uuids(username, outbound_tags, uuids):
    """Return a copy of `uuids` with an entry for every (username, outbound) pair.

    Why stability matters: an existing pair keeps its UUID, so configs
    already shared with a user keep working after edits; only genuinely
    new pairs get a freshly generated UUID. Pure function — no database,
    which makes it trivial to test.
    """
    result = dict(uuids)
    for tag in outbound_tags:
        email = "%s@%s" % (username, tag)
        result.setdefault(email, str(uuid.uuid4()))
    return result


def create_user(conn, data: UserCreate):
    """Turn a UserCreate payload into a complete user and store it.

    Why the service fills uuids and created_at: those are server-generated
    facts, not client choices — the client never sends them.
    """
    user = {
        "username": data.username,
        "status": data.status,
        "expire": data.expire,
        "allowed_inbounds": data.allowed_inbounds,
        "allowed_outbounds": data.allowed_outbounds,
        "uuids": ensure_uuids(data.username, data.allowed_outbounds, {}),
        "note": data.note,
        "created_at": int(time.time()),
    }
    db.create_user(conn, user)
    return user


def update_user(conn, username, data: UserUpdate):
    """Merge a partial update into the existing user and store the result.

    Returns None when the user does not exist (the router maps that to 404).
    Why a loop over field names: it applies one rule — "None means keep the
    old value" — to every field without repeating it five times.
    """
    existing = db.get_user(conn, username)
    if existing is None:
        return None

    user = dict(existing)
    for field in ("status", "expire", "allowed_inbounds",
                  "allowed_outbounds", "note"):
        value = getattr(data, field)
        if value is not None:
            user[field] = value

    user["uuids"] = ensure_uuids(username, user["allowed_outbounds"],
                                 user["uuids"])
    db.replace_user(conn, user)
    return user


def delete_user(conn, username):
    """Remove a user; True if deleted, False if they did not exist."""
    return db.delete_user(conn, username)
