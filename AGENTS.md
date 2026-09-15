# AGENTS.md — project context for Lesserv

Hobbyist-built, VLESS-only Xray user-management panel. NOT a fork of Marzban;
built from scratch to learn full-stack development. Core differentiator vs
existing panels: per-user outbound selection via email routing
(email = `username@outbound`, Xray routing rules use `regexp:.*@TAG$`).

## Project state

Roadmap and current milestone status live in docs/PLAN.md. Always read it
at the start of a session to know where the project stands. The code
walkthrough (how each module works, request flows, concepts) lives in
docs/ARCHITECTURE.md — update it in the same commit that changes code;
wrong documentation is worse than none.

## Run it

- conda env: `lesserv` (Python 3.14). Deps: `python -m pip install -r requirements.txt`
- Start backend: `uvicorn backend.main:app --reload` from repo root -> http://127.0.0.1:8000/docs
- Start frontend: `cd frontend && npm install && npm run dev` -> http://localhost:5173
  (Vite proxies /api/* to the backend; no CORS setup needed)
- DB file: `data/panel.db` (gitignored, auto-created)

## Architecture decisions (locked)

- Backend: FastAPI + plain `sqlite3` (no ORM). JSON columns for
  allowed_inbounds / allowed_outbounds / uuids.
- v1 user sync = regenerate full runtime config + restart Xray. No Xray gRPC API in v1 (deferred).
- The user's Xray config is opaque EXCEPT three panel-owned places the
  panel FILLS: routing.rules, VLESS inbounds' settings.clients, and
  every inbound's streamSettings.realitySettings.privateKey (panel-
  generated X25519 key, stored in SQLite — the config file's value is
  ignored). Never generate, validate, or interpret anything else.
- Only VLESS. UUID per (user, outbound) pair, stable across changes.
  REALITY keys are per inbound tag, stable across syncs, changed only
  by explicit rotation.
- No auth in v1.
- File map: backend/main.py (app + lifespan), backend/db.py (all SQLite:
  users + reality_keys tables),
  backend/services/* (business logic: user_service, config_service,
  reality_service, xray_service, share_service), backend/routers/*
  (users, system, reality), backend/core/allocator.py (copy of
  vless_allocator from sibling repo xray_multi_inout_generator),
  backend/core/x25519.py (pure X25519 derive/generate, no deps),
  backend/settings.py
  (env-overridable: config path, runtime config path, Xray binary,
  server address for share links). The user-provided config goes in
  config/ (gitignored dir, user-provided); the generated runtime config
  goes in data/.

## Conventions (user requirement — non-negotiable)

- Every function: docstring explaining WHAT it does and WHY it exists.
- Functions under ~30 lines, one job each. Plain dicts/lists, no clever abstractions.
- Dependencies must be justifiable; keep them minimal.
- User reads every file before moving to the next milestone; explain code, don't just generate it.

## Gotchas

- FastAPI runs sync `def` endpoints in a worker-thread pool -> sqlite
  connections need `check_same_thread=False` (see backend/db.py:connect).