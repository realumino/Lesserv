"""Generate, store, and rotate the REALITY X25519 keys of the inbounds.

Why this exists: the panel owns `realitySettings.privateKey` — every sync
overwrites it with a key generated here and stored in SQLite, regardless
of what the operator's config says. The database is the source of truth,
so share links can derive the right public key (`pbk`) even when the
config file still carries the operator's own (or a placeholder) key.

Keys are stable across restarts and syncs: generated once per inbound
tag, replaced only by explicit rotation (which breaks every client using
the old key — hence it must be a deliberate operator action).
"""

import time

from backend import db
from backend.core import x25519
from backend.services import config_service


def key_map(conn):
    """Return {inbound_tag: private_key} for every stored REALITY key.

    Why the flat shape: build_config's runtime is filled by looking up
    each inbound's tag, and share links pick their private key per
    inbound the same way — a plain dict keeps both callers trivial.
    """
    return {
        tag: row["private_key"]
        for tag, row in db.list_reality_keys(conn).items()
    }


def ensure_keys(conn, config):
    """Generate and store a private key for every REALITY inbound missing one.

    Why called from every sync: a config posted via the API may add a
    REALITY inbound at any time; re-running this (idempotent, only the
    missing tags generate) is the simplest guarantee that `apply_reality_keys`
    finds a key for each inbound. Returns the full {tag: private_key} map.
    """
    stored = key_map(conn)
    for tag in config_service.reality_inbound_tags(config):
        if tag not in stored:
            db.upsert_reality_key(conn, tag, x25519.generate_private_key(),
                                  int(time.time()))
    return key_map(conn)


def rotate_key(conn, tag):
    """Replace the stored key of one REALITY inbound; return the new private key.

    Why the timestamp is refreshed: `created_at` doubles as the
    generation/rotation time, so the UI can show when the current key
    became effective. Callers must resync Xray afterwards — until then
    the runtime config still serves the old key.
    """
    private_key = x25519.generate_private_key()
    db.upsert_reality_key(conn, tag, private_key, int(time.time()))
    return private_key


def public_key(conn, tag):
    """Return the derived public key of one stored key, or None when absent.

    Why derive and not store: the public key is a pure function of the
    private key, so storing it would only invite the two disagreeing.
    None means the tag has no key yet (sync has not seen it) — the caller
    renders an empty state.
    """
    stored = db.list_reality_keys(conn).get(tag)
    if stored is None:
        return None
    return x25519.derive_public_key(stored["private_key"])


def list_keys(conn, config):
    """Rows for GET /api/reality: config-ordered REALITY keys with public parts.

    Why ordered by the config: the operator reads the panel in the shape
    of their own config, and a stable order keeps the UI from jumping
    between renders. Tags without a stored key (sync not yet run after a
    manual file drop) appear with null public_key/created_at instead of
    being hidden — the admin must see that a key is pending.
    """
    stored = db.list_reality_keys(conn)
    return [
        {
            "inbound": tag,
            "public_key": public_key(conn, tag),
            "created_at": stored.get(tag, {}).get("created_at"),
        }
        for tag in config_service.reality_inbound_tags(config)
    ]
