"""The FastAPI application: starts the database and serves the API.

Run from the repo root with:
    uvicorn backend.main:app --reload

Then open http://127.0.0.1:8000/docs for interactive API docs.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import db
from backend.routers import reality, system, users
from backend.services import xray_service

DB_PATH = "data/panel.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Everything that happens between server start and server stop.

    Why this exists: FastAPI calls this once on startup and once on
    shutdown. It is the one obvious place to open the database — and to
    generate the Xray config, start Xray, and stop it again on shutdown.
    """
    conn = db.connect(DB_PATH)
    db.init_schema(conn)
    db.seed(conn)
    app.state.db = conn
    xray_service.sync(conn)
    yield
    xray_service.stop()
    conn.close()


app = FastAPI(title="Lesserv", lifespan=lifespan)
app.include_router(system.router)
app.include_router(users.router)
app.include_router(reality.router)


@app.get("/api/health")
def health():
    """Cheap check that the server is alive."""
    return {"status": "ok"}
