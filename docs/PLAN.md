# PLAN.md — Lesserv milestone roadmap

This file holds the project's volatile state: what is done, what is next.
Update the Status column after each milestone. Stable context (architecture,
conventions, how to run) lives in AGENTS.md at the repo root.

## What "the config" means in this file

The user-provided Xray config is opaque: the panel preserves it verbatim.
Any milestone phrase like "generate" or "fill the config" means ONLY
replacing two places in it:

1. `routing.rules` — one rule per outbound: `regexp:.*@TAG$` -> that outbound
2. `settings.clients` of each VLESS inbound — entries `{id, email}`
3. `streamSettings.realitySettings.privateKey` of every inbound that has a
   `realitySettings` block — always replaced with the panel-generated X25519
   key stored in `data/panel.db` (table `reality_keys`), whether the config
   carries one or not. Rotation happens only via the API.
4. `outbounds` — ORDER only: BLOCK is guaranteed to be the first outbound
   (injected as `blackhole` when absent). Xray falls back to the first
   outbound when no rule matches, so BLOCK first = catch-all. A rule with
   only `outboundTag` is an Xray error (rules need a matcher), so no
   catch-all rule is ever generated.

Nothing else is ever generated, validated, or interpreted. The filled
result the panel writes is called the "runtime config".

## Current status: milestone 7 — routing fix, BLOCK-first default (done)

Milestones 0–6 are done. Latest: the matcher-less catch-all rule
(`{"outboundTag": "BLOCK"}`) is gone — Xray rejects rules without a
matcher. `config_service.ensure_block_first` now guarantees BLOCK is the
first outbound, and Xray's own "no rule matched -> first outbound" fallback
acts as the catch-all.

Milestone 6: REALITY key management — the panel now
owns `realitySettings.privateKey`: every sync generates an X25519 key per
REALITY inbound (stored in the new `reality_keys` SQLite table), injects
it into the runtime config, and share links derive `pbk` from that stored
key. New endpoints `GET /api/reality`, `POST /api/reality/{tag}/rotate`,
`POST /api/reality/rotate`; the Config tab shows each inbound's public key
with Rotate buttons.

| # | What | Status |
|---|------|--------|
| 0 | Skeleton: FastAPI + SQLite + GET /api/users (seeded demo user) | done (commit f3952e4) |
| 1 | Full user CRUD + pydantic models (backend/models.py, backend/routers/users.py, ensure_uuids) | done |
| 2 | Fill config's `routing.rules` + VLESS `clients` from DB users; run/restart Xray subprocess | done |
| 3 | Endpoints: GET /api/inbounds, /api/outbounds (tags read from config), GET /api/status, POST /api/config (replace config) | done |
| 4 | React frontend (Vite, plain JS, Tailwind CDN): status bar, user table, add/edit modal with inbound/outbound checkboxes, config tab showing config + runtime config; + GET /api/config, GET /api/config/runtime | done |
| 5 | Share links (vless:// URIs): per-user links, copy/QR, REALITY public key derivation | done |
| — | Minor improvements, no fixed scope (template→config / generated→runtime config rename) | done |
| 6 | REALITY key management: auto-generated per-inbound X25519 keys in SQLite, injected at sync; share links use the stored key; rotate endpoints + Config-tab UI | done |
| 7 | Routing fix: matcher-less catch-all rule removed (Xray error); BLOCK is now guaranteed first outbound = Xray's own catch-all | done |
| later | Xray gRPC stats API, auth, expiry/quota jobs, Docker | deferred |
