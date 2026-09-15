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

Nothing else is ever generated, validated, or interpreted. The filled
result the panel writes is called the "runtime config".

## Current status: minor improvements stage (no specific milestone)

Milestones 0–5 are done; there is no active milestone now. Work happens as
small, self-contained improvements with no shared purpose — naming, UI
polish, cleanups. Latest: share-link generation now reads `flow` from
an inbound's `settings.flow` and appends it as a `flow=` query param.

| # | What | Status |
|---|------|--------|
| 0 | Skeleton: FastAPI + SQLite + GET /api/users (seeded demo user) | done (commit f3952e4) |
| 1 | Full user CRUD + pydantic models (backend/models.py, backend/routers/users.py, ensure_uuids) | done |
| 2 | Fill config's `routing.rules` + VLESS `clients` from DB users; run/restart Xray subprocess | done |
| 3 | Endpoints: GET /api/inbounds, /api/outbounds (tags read from config), GET /api/status, POST /api/config (replace config) | done |
| 4 | React frontend (Vite, plain JS, Tailwind CDN): status bar, user table, add/edit modal with inbound/outbound checkboxes, config tab showing config + runtime config; + GET /api/config, GET /api/config/runtime | done |
| 5 | Share links (vless:// URIs): per-user links, copy/QR, REALITY public key derivation | done |
| — | Minor improvements, no fixed scope (template→config / generated→runtime config rename) | done |
| later | Xray gRPC stats API, auth, expiry/quota jobs, Docker | deferred |
