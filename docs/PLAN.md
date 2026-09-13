# PLAN.md — Lesserv milestone roadmap

This file holds the project's volatile state: what is done, what is next.
Update the Status column after each milestone. Stable context (architecture,
conventions, how to run) lives in AGENTS.md at the repo root.

## What "the config" means in this file

The Xray config is an opaque template the panel preserves verbatim. Any
milestone phrase like "generate" or "fill the config" means ONLY replacing
two places in the template:

1. `routing.rules` — one rule per outbound: `regexp:.*@TAG$` -> that outbound
2. `settings.clients` of each VLESS inbound — entries `{id, email}`

Nothing else is ever generated, validated, or interpreted.

## Current status: Milestone 2 done, Milestone 3 next

| # | What | Status |
|---|------|--------|
| 0 | Skeleton: FastAPI + SQLite + GET /api/users (seeded demo user) | done (commit f3952e4) |
| 1 | Full user CRUD + pydantic models (backend/models.py, backend/routers/users.py, ensure_uuids) | done |
| 2 | Fill template's `routing.rules` + VLESS `clients` from DB users; run/restart Xray subprocess | done |
| 3 | Endpoints: GET /api/inbounds, /api/outbounds (tags read from template), GET /api/status, POST /api/config (replace template) | NEXT |
| 4 | React frontend (Vite, plain JS): user table + add/edit form with inbound/outbound checkboxes | pending |
| 5 | Share links (vless:// URIs) — optional stretch | pending |
| later | Xray gRPC stats API, auth, expiry/quota jobs, Docker | deferred |