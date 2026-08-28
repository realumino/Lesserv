# PLAN.md — Lesserv milestone roadmap

This file holds the project's volatile state: what is done, what is next.
Update the Status column after each milestone. Stable context (architecture,
conventions, how to run) lives in AGENTS.md at the repo root.

## Current status: Milestone 0 done, Milestone 1 next

| # | What | Status |
|---|------|--------|
| 0 | Skeleton: FastAPI + SQLite + GET /api/users (seeded demo user) | done (commit f3952e4) |
| 1 | Full user CRUD + pydantic models (backend/models.py, backend/routers/users.py, ensure_uuids) | NEXT |
| 2 | Config + Xray services: build full config from DB, run/restart Xray subprocess | pending |
| 3 | Config & status endpoints: GET /api/inbounds, /api/outbounds, /api/status, POST /api/config | pending |
| 4 | React frontend (Vite, plain JS): user table + add/edit form with inbound/outbound checkboxes | pending |
| 5 | Share links (vless:// URIs) — optional stretch | pending |
| later | Xray gRPC stats API, auth, expiry/quota jobs, Docker | deferred |