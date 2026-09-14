# ARCHITECTURE.md — how Lesserv works, explained

A human-readable walkthrough of the code: what each module does, how the
pieces fit together, and what happens when a request arrives.

**Maintenance rule: this file is updated in the same commit that changes
the code.** When you add a module, add its section; when a behavior
changes, fix the section that describes it. Treat it like code — wrong
documentation is worse than none.

## What Lesserv is

A VLESS-only, user-management panel for [Xray](https://github.com/XTLS/Xray-core),
built from scratch to learn full-stack development. The one thing it does
differently from other panels:

- A user's client email inside Xray is `username@outboundtag`
  (e.g. `alice@JAPAN`).
- Routing rules match that email with a regex
  (`regexp:.*@JAPAN$` -> outbound `JAPAN`).
- Result: each user may be allowed different outbounds (exit nodes) on the
  same server — per-user exit selection, without writing a routing rule per
  user.

**Current state (after milestone 3):** the panel stores users in SQLite,
serves a REST API for user CRUD, after every user change regenerates the
Xray config and restarts Xray, and exposes endpoints for the template
structure (inbounds/outbounds tags), system health, and template
replacement via the API.

## The layers

```
Browser / curl / React (milestone 4)
   │  HTTP
   ▼
uvicorn                server: opens the port, speaks HTTP
   │  ASGI
   ▼
backend/main.py        the FastAPI app: lifespan + wiring
   │
   ▼
backend/routers/*      HTTP concerns only: paths, status codes, JSON
   │
   ▼
backend/services/*     business rules (uuid generation, config fill, sync)
   │
   ▼
backend/db.py          the only file that contains SQL
   │
   ▼
SQLite (data/panel.db)
```

And the Xray branch, which hangs off the same service layer:

```
template (config/xray_template.json — user-provided, gitignored)
   │
config_service + allocator   (pure, no I/O)
   │
data/xray_config.json        (filled config, gitignored)
   │
xray_service                 (subprocess lifecycle)
   │
   ▼
Xray process
```

And the pure pieces:

- `backend/models.py` — pydantic shapes (the API contract), used by every layer.
- `backend/routers/system.py` — system endpoints: inbounds/outbounds tag lists,
  composite status, and config replacement via POST.
- `backend/core/allocator.py` — the copied `vless_allocator` brain, pure and
  dependency-free. Verbatim copy from the sibling repo; panel policy never
  goes in here.
- `backend/settings.py` — the three paths, overridable via environment
  variables so dev and server runs differ without editing code.

**Flow rules that keep this healthy:**

- Requests flow DOWN only: router -> service -> db. Never reverse.
- main.py wires things together; routers do HTTP; services hold rules;
  db holds SQL; models hold shapes.
- A module never knows about the layer above it (db.py has no idea HTTP
  exists; routers have no idea SQL exists).

## How to run it

```
conda activate lesserv
uvicorn backend.main:app --reload     # server, from repo root
python -m unittest tests.test_users -v    # tests
```

- Interactive API docs: http://127.0.0.1:8000/docs
- DB file: `data/panel.db` (gitignored, auto-created on first start)

## Module by module

### backend/main.py — the app and its lifetime

- `app = FastAPI(title="Lesserv", lifespan=lifespan)` creates the
  application object. It is an ASGI application (a callable uvicorn can
  drive); it holds the routing table that every `@app.get`/`@router.get`
  fills.
- `lifespan(app)` is an async context manager run once at server start and
  once at shutdown: it opens the database, initializes the schema, seeds
  the demo user, stores the connection on `app.state.db` (a "bag" on the
  app object), calls `xray_service.sync(conn)` (fill the config, start
  Xray), yields (server runs), then stops Xray and closes the connection.
- `app.include_router(users.router)` merges the users router into the
  app's single routing table at startup.
- `/api/health` is the liveness check.

### backend/models.py — the API contract

Pydantic classes describing the shape of data entering/leaving the API:

- `UserCreate` — POST body. `username` (validated: no `@`, no spaces,
  non-empty, <= 32 chars — the `@` would break the email scheme), `status`
  (`active`/`disabled`), `expire` (unix ts or None; `0` = never expires),
  `allowed_inbounds`/`allowed_outbounds` (lists, default empty), `note`.
- `UserUpdate` — PUT body. Same fields, all optional; `None` = "leave
  unchanged". No `username`: the username is the identity and cannot be
  renamed.
- `UserOut` — response shape: everything plus server-generated `uuids`
  (dict of `email -> uuid`) and `created_at`.

What pydantic gives us: input validation (bad JSON -> 422 with a clear
message, before our code runs), guaranteed types inside functions, and the
shapes rendered in /docs. When the future frontend disagrees about a field
name, this file is where to look.

### backend/routers/users.py — HTTP concerns only

- `router = APIRouter(prefix="/api/users")` groups the user endpoints;
  `include_router` flattens them into the app's routing table. APIRouter
  is a FastAPI feature for organizing routes — uvicorn never sees it.
- `get_db(request)` is a FastAPI dependency returning `request.app.state.db`
  (the connection stored by lifespan). It exists to avoid a circular import
  (main.py imports this router; the router must not import main.py back).
- The five endpoints translate between HTTP and the service layer:

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | /api/users | 200 list | — |
| POST | /api/users | 201 | 409 duplicate username, 422 invalid body |
| GET | /api/users/{username} | 200 | 404 |
| PUT | /api/users/{username} | 200 (partial update) | 404 |
| DELETE | /api/users/{username} | 204 | 404 |

Validation errors are 422 (FastAPI's code for pydantic rejection), not 400.

### backend/routers/system.py — system info and config management

Four endpoints that the React frontend (milestone 4) will use to populate
inbound/outbound checkbox lists and show the status bar. All share
`prefix="/api"` and `tags=["system"]`.

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | /api/inbounds | 200 `[{tag, protocol, network, security}]` | 503 template not loaded |
| GET | /api/outbounds | 200 `[{tag, protocol}]` | 503 template not loaded |
| GET | /api/status | 200 `{template_loaded, xray_running, xray_pid, user_count}` | — |
| POST | /api/config | 200 `{"message": "config updated"}` | 422 invalid JSON body |

- `/api/inbounds` and `/api/outbounds` call `xray_service.load_template()`
  and then `config_service.inbound_summaries()` / `outbound_summaries()`.
  The inbound response includes `network` and `security` (from
  `streamSettings`, empty string when absent) so the frontend can label
  checkboxes, e.g. "REALITY (tcp + reality)". They return 503 when the
  template is missing (an empty list would conflate "zero inbounds exist"
  with "no template loaded").
- `/api/status` bundles `load_template()`, `xray_service.status()`, and
  `db.list_users()` into one composite response so the frontend can render
  a status bar with one HTTP call.
- `POST /api/config` accepts a raw JSON body (the template is opaque — the
  panel never validates its structure), writes it atomically via
  `xray_service.save_template()`, and calls `xray_service.sync()` to
  regenerate the config and restart Xray. A fresh install gets its first
  template this way instead of dropping a file into `config/`.

### backend/services/user_service.py — the business rules

The rules that are neither HTTP nor SQL live here:

- `ensure_uuids(username, outbound_tags, uuids)` — returns a copy of the
  uuid map with an entry for every `username@outbound` pair. Existing pairs
  keep their UUID (**stability**: configs already shared keep working);
  new pairs get a fresh `uuid4()`. Pure function, no database.
- `create_user(conn, data)` — fills server-generated facts (uuids,
  `created_at`), stores the user, returns it. The client never sends uuids
  or timestamps.
- `update_user(conn, username, data)` — fetches the existing user (returns
  None if missing), loops over the editable fields applying one rule
  ("None means keep the old value"), re-runs `ensure_uuids` so a newly
  added outbound gets its UUID, stores via `replace_user`.
- `delete_user(conn, username)` — removes; returns True/False for the
  router's 404 decision.

After every successful mutation these three functions call
`xray_service.sync(conn)`. This layer is the choke point where "the
database changed" becomes "the real system must react" — the routers
never know it happens. Failed operations (the 404 paths) skip the sync,
so a no-op request does not bounce Xray.

### backend/services/config_service.py — turning users into a config

A pure transformer: dicts in, dicts out, no files, no SQLite, no Xray.
This is what makes the milestone testable without a running server.

- `user_permissions(users)` — reduces the user list to
  `{username: {allowed_inbounds, allowed_outbounds}}` for **active users
  only**. Disabled users vanish from the config on the next sync.
- `uuids_map(users)` — merges all active users' uuid maps into one flat
  `{email: uuid}` dict, the shape the allocator wants.
- `inbound_summaries(template)` — extracts `{tag, protocol, network, security}`
  per inbound. `network` and `security` come from `streamSettings` (empty
  string when absent) so the frontend can label checkboxes.
- `outbound_tags(template)` — returns the tag strings of the outbounds for
  the allocator (which only needs tags). BLOCK is excluded because it is a
  system catch-all, not a routable exit node — no `regexp:.*@BLOCK$` rule
  is ever generated.
- `outbound_summaries(template)` — returns `[{tag, protocol}]` for the
  frontend via `/api/outbounds`.
- `clients_and_rules(users, template)` — calls the allocator, then appends
  the trailing catch-all rule `{"outboundTag": "BLOCK"}` that drops any
  traffic whose email matched no rule. The catch-all lives here (not in
  the allocator) because it is panel policy and the allocator must stay a
  verbatim copy. BLOCK is guaranteed to exist by this point because
  `build_config` auto-injects it.
- `build_config(template, users)` — the entry point: `copy.deepcopy`s the
  template, auto-injects a `{"tag": "BLOCK", "protocol": "blackhole"}`
  outbound when none exists, replaces `settings.clients` of every VLESS
  inbound (an empty list when nobody is allocated to it; non-VLESS inbounds
  untouched) and appends generated rules to `routing.rules` (auto-creating
  the `routing` section when absent, extending instead of replacing so
  pre-existing user rules survive). Returns `(config, warnings)`.

Everything else in the template is preserved exactly — the opaque-template
rule. The copy also guarantees the caller's template dict survives
untouched across syncs.

### backend/services/xray_service.py — the Xray side of the panel

The only module that touches the filesystem and the subprocess. Nothing
in it ever raises: a missing template or binary is a normal state, so each
step logs a warning and gives up — a user edit must never take the API
down.

- `load_template()` — reads `settings.TEMPLATE_PATH`; `None` when the file
  is missing or not valid JSON (both logged as warnings).
- `save_template(content)` — the write counterpart of `load_template()`.
  Writes `content` (a dict) to `settings.TEMPLATE_PATH` atomically (temp
  file + `os.replace`). Called by `POST /api/config`; the content is always
  a valid JSON-serialisable dict at this point because FastAPI rejects
  non-JSON bodies as 422.
- `write_config(config)` — writes to `settings.XRAY_CONFIG_PATH`
  atomically: dump to a `.tmp` file, then `os.replace`, so Xray can never
  read a half-written config.
- `start()` — launches `[binary, "run", "-config", path]` via
  `subprocess.Popen` with inherited stdout/stderr (Xray's own log is the
  operator's window). Skips with a warning when the binary does not exist
  (dev machines). After launching it waits 2 seconds: if Xray already
  exited, the config was bad — it logs the exit code and forgets the
  process instead of pretending Xray runs.
- `stop()` — terminate + 5s wait + kill. No-op when nothing runs.
- `restart()` — stop then start; Xray reads its config only at startup, so
  every rewrite needs a bounce (no gRPC API in v1).
- `status()` — returns `{"running": bool, "pid": int | None}` by reading
  the module-level `_process` handle. Read-only, no lock, used by
  `GET /api/status` to show process health.
- `sync(conn)` — the single entry point: load template, list users, build
  the config, log the allocator warnings, write, restart. Called by
  `user_service` after every user change and by `main` at startup. A
  malformed template (missing keys) raises `KeyError`/`TypeError` inside
  `build_config`; sync catches those, warns, and returns.

The process handle is module-level (not `app.state`) because user_service
has no access to the app object, and a `threading.Lock` guards
start/stop because sync runs in FastAPI's worker threads.

### backend/core/allocator.py — the copied allocation brain

A verbatim copy of `vless_allocator.py` from the sibling repo
`xray_multi_inout_generator` (kept in sync manually). Pure processor, no
I/O: it takes user permissions, inbound summaries, outbound tags and a
uuid map, and returns `clients_by_inbound`, `routing_rules`, `warnings`.
One `regexp:.*@TAG$` rule per outbound tag; one `{id, email}` client per
allowed (user, inbound, outbound) triple; non-VLESS inbounds and missing
uuids produce warnings. All panel policy (active-only filtering, catch-all
rule) lives in config_service, never here.

### backend/settings.py — paths the operator can override

Three module-level constants read from environment variables with
repo-root defaults:

| setting | default | meaning |
|---|---|---|
| `TEMPLATE_PATH` | `config/xray_template.json` | user-provided semi-complete config |
| `XRAY_CONFIG_PATH` | `data/xray_config.json` | filled config the panel writes |
| `XRAY_BINARY` | `xray` | executable name or absolute path |

The template lives in `config/`, a git-tracked folder whose `.gitignore`
excludes everything — the admin drops their file there and it is never
committed. Milestone 3's `POST /api/config` will replace that file via the
API.

### backend/db.py — the only place with SQL

- `connect(path)` — opens SQLite with `row_factory=sqlite3.Row`
  (dict-like rows) and `check_same_thread=False`. The flag is required
  because FastAPI runs sync endpoints in a worker-thread pool, so the
  connection created at startup (main thread) is used from other threads;
  SQLite refuses that by default. Safe because the panel is a single
  low-traffic process.
- `init_schema(conn)` — `CREATE TABLE IF NOT EXISTS users` (idempotent,
  runs on every startup).
- `seed(conn)` — inserts the demo user with `INSERT OR IGNORE`
  (idempotent; never duplicates). Its tags (`REALITY`/`XHTTP` inbounds,
  `OUTBOUND` outbound) mirror the typical template layout so the demo
  client actually matches a routing rule instead of the BLOCK catch-all.
- `list_users(conn)` / `get_user(conn, username)` — SELECTs. `get_user`
  returns None when missing.
- `create_user(conn, user)` / `replace_user(conn, user)` /
  `delete_user(conn, username)` — INSERT / full-row UPDATE / DELETE.
  `replace_user` overwrites every column on purpose: the service merges
  partial changes into a complete user first, so the SQL stays one fixed
  statement with no dynamic column list.
- `row_to_dict(row)` — converts a row to a plain dict and decodes the JSON
  text columns back into real lists/dicts. All JSON encoding/decoding
  lives inside db.py; other layers see plain Python values.

### tests/ — locking behavior down

All tests use stdlib `unittest` (no extra deps).

- `tests/test_users.py` — `_fresh_conn()` builds a throwaway database in a
  temp file so tests never touch `data/panel.db`. Three original groups:
  model validation (bad usernames/statuses rejected), uuid stability, db
  CRUD round-trips including partial update. Plus the milestone 2 wiring
  tests: `xray_service.sync` is mocked and each test asserts it fires after
  a successful create/update/delete and never after a 404.
- `tests/test_allocator.py` — the copied allocator in isolation: clients
  per inbound, one rule per outbound tag, warnings for non-VLESS inbounds
  and missing uuids.
- `tests/test_config_service.py` — a tiny fixture template proves the
  fill: clients injected, rules + BLOCK catch-all replaced, disabled users
  excluded, unused VLESS inbounds emptied, everything else preserved
  verbatim, and the caller's template dict never mutated.
- `tests/test_system.py` — tests the two new `xray_service` functions
  (`save_template` atomic write and directory creation; `status` for
  running/exited/none states), plus the four router endpoints called
  directly with mocked dependencies (503 on missing template, correct
  summaries/tags, composite status response, config write-and-sync flow).

## Life of one request: POST /api/users

1. Browser/curl sends `POST /api/users` with a JSON body.
2. uvicorn receives the TCP connection, builds an ASGI request, calls the
   FastAPI `app` object.
3. FastAPI finds the route in its (flattened) routing table and sees the
   parameter annotation `payload: UserCreate`.
4. FastAPI parses and validates the body against `UserCreate`; on failure
   it answers 422 immediately — our code never runs.
5. `get_db` dependency provides the SQLite connection from `app.state.db`.
6. The router checks for a duplicate username (409 if taken), then calls
   `user_service.create_user(conn, payload)`.
7. The service builds the full user dict: `ensure_uuids` mints one UUID
   per allowed outbound, `created_at` is stamped, then
   `db.create_user` runs the INSERT and commits.
8. The returned dict is validated against `response_model=UserOut` and
   serialized to JSON; uvicorn writes the 201 response to the socket.
9. Back in the service, `xray_service.sync(conn)` runs: the template is
   re-read, the config rebuilt with the new user's client entries, written
   to `data/xray_config.json`, and Xray is restarted. Every failure along
   the way is logged and swallowed — a broken template or missing binary
   cannot turn a user edit into a 500.

## The users table

| column | type | meaning |
|---|---|---|
| username | TEXT PK | identity; never renamed |
| status | TEXT | `active` \| `disabled` (default active) |
| expire | INTEGER | unix timestamp, NULL = none, 0 = never expires |
| allowed_inbounds | TEXT (JSON list) | inbound tags the user may use |
| allowed_outbounds | TEXT (JSON list) | outbound tags the user may use |
| uuids | TEXT (JSON object) | `"username@outbound": uuid` map — the differentiator |
| note | TEXT | free text |
| created_at | INTEGER | unix timestamp |

JSON text columns were chosen over join tables because the values are just
strings at this scale. The trigger to normalize later: a traffic counter
column written every few seconds, or frequent relational queries — see the
"optimize when it hurts" rule below.

## Concepts that were confusing (and their answers)

- **Router**: a FastAPI feature (URL -> function mapping), not uvicorn.
  Uvicorn is the server; routing is the framework's job.
- **`app` object**: a FastAPI (ASGI) application. Uvicorn runs it via the
  ASGI protocol (`app(scope, receive, send)`); it is not a uvicorn object.
- **`lifespan=lifespan`**: keyword argument; left name is FastAPI's
  parameter, right side is our function (the same spelling is coincidence).
- **`yield` in lifespan**: pause point. Above = run at startup, below =
  run at shutdown.
- **Why uvicorn, not `python main.py`**: creating the app object serves
  nothing; a server must bind the port and drive the app. `uvicorn` the
  command is just `python -m uvicorn` wearing a shortcut.
- **422 vs 400**: FastAPI answers 422 when pydantic rejects a body.
- **check_same_thread=False**: see the db.py section.

## Conventions (same as AGENTS.md — this is binding)

- Every function: docstring explaining WHAT it does and WHY it exists.
- Functions under ~30 lines, one job each. Plain dicts/lists, no clever
  abstractions.
- Dependencies must be justifiable; keep them minimal.
- Optimize when it hurts (YAGNI): JSON columns are fine until a real query
  or write pattern proves them inadequate.
