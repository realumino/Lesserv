"""Build the filled Xray config from the template and the users table.

Why this exists: turning DB users into `settings.clients` and
`routing.rules` is a pure transformation — no files, no subprocesses, no
SQLite — so it can be unit-tested with plain dicts. xray_service owns the
I/O around it.
"""

import copy

from backend.core import allocator


def user_permissions(users):
    """Return {username: {allowed_inbounds, allowed_outbounds}} for active users.

    Why disabled users are dropped here: a disabled user must disappear
    from the Xray config on the next sync, so the allocator never sees
    them.
    """
    return {
        user["username"]: {
            "allowed_inbounds": user["allowed_inbounds"],
            "allowed_outbounds": user["allowed_outbounds"],
        }
        for user in users
        if user["status"] == "active"
    }


def uuids_map(users):
    """Merge every active user's uuid map into one flat {email: uuid} dict.

    Why one flat dict: the allocator is keyed by email
    (username@outboundtag) and knows nothing about users.
    """
    merged = {}
    for user in users:
        if user["status"] == "active":
            merged.update(user["uuids"])
    return merged


def inbound_summaries(template):
    """Extract {tag, protocol, network, security} from every inbound.

    Why this exists: the allocator only needs tag + protocol; the API
    endpoint also exposes network and security so the frontend can show
    richer checkboxes. Extra fields in the dict don't hurt the allocator.
    """
    result = []
    for inbound in template["inbounds"]:
        stream = inbound.get("streamSettings") or {}
        result.append({
            "tag": inbound["tag"],
            "protocol": inbound["protocol"],
            "network": stream.get("network", ""),
            "security": stream.get("security", ""),
        })
    return result


def outbound_tags(template):
    """Return the tag strings of every regular outbound (BLOCK excluded).

    Why BLOCK is excluded: it is a system catch-all, not a real exit node;
    the allocator must not generate a regexp:.*@BLOCK$ rule for it.
    """
    return [o["tag"] for o in template["outbounds"] if o["tag"] != "BLOCK"]


def outbound_summaries(template):
    """Extract {tag, protocol} from every outbound in the template.

    Why this exists: the allocator needs just the tag strings, but the
    API endpoint also exposes the protocol so the frontend can show
    richer checkboxes.
    """
    return [
        {"tag": outbound["tag"], "protocol": outbound["protocol"]}
        for outbound in template["outbounds"]
    ]


def clients_and_rules(users, template):
    """Run the allocator; return (clients_by_inbound, routing_rules, warnings).

    Why the BLOCK catch-all is appended here and not inside the allocator:
    the allocator is a verbatim copy from the sibling repo; panel policy
    stays in this module. The catch-all drops traffic whose email matched
    no per-outbound rule. BLOCK is guaranteed to exist by the time this
    runs (build_config auto-injects it if absent), so there is no else.
    """
    tags = outbound_tags(template)
    clients, rules, warnings = allocator.allocate(
        user_permissions(users), inbound_summaries(template), tags, uuids_map(users)
    )
    rules.append({"outboundTag": "BLOCK"})
    return clients, rules, warnings


def build_config(template, users):
    """Return a deep copy of the template with clients and routing filled in.

    Why a deep copy: the caller's template dict must stay untouched — it is
    re-read from disk on every sync, and mutating it would leak filled
    state into the opaque parts we promise to preserve.

    Why routing is optional: novice operators may omit the routing section
    entirely; the panel creates it automatically. When the user does supply
    their own routing.rules, the generated rules are appended after them so
    user-authored rules stay at the front and the BLOCK catch-all still
    trails at the end.

    Why BLOCK is auto-injected: every Xray config needs a catch-all
    outbound; requiring the user to add one manually is a papercut. The
    panel injects a blackhole BLOCK outbound when none exists.
    """
    config = copy.deepcopy(template)
    block_exists = any(
        o.get("tag") == "BLOCK" for o in config.get("outbounds", [])
    )
    if not block_exists:
        config.setdefault("outbounds", []).append(
            {"tag": "BLOCK", "protocol": "blackhole"}
        )
    clients, rules, warnings = clients_and_rules(users, config)
    for inbound in config["inbounds"]:
        if inbound["protocol"] != "vless":
            continue
        inbound["settings"]["clients"] = clients.get(inbound["tag"], [])
    routing = config.setdefault("routing", {})
    routing["rules"] = routing.get("rules", []) + rules
    return config, warnings
