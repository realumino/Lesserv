"""The FastAPI application: starts the database and serves the API.

Run from the repo root with:
    uvicorn backend.main:app --reload

Then open http://127.0.0.1:8000/docs for interactive API docs.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import db

DB_PATH = "data/panel.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Everything that happens between server start and server stop.

    Why this exists: FastAPI calls this once on startup and once on
    shutdown. It is the one obvious place to open the database — and,
    in later milestones, to start Xray.
    """
    conn = db.connect(DB_PATH)
    db.init_schema(conn)
    db.seed(conn)
    app.state.db = conn
    yield
    conn.close()


app = FastAPI(title="Lesserv", lifespan=lifespan)


@app.get("/api/health")
def health():
    """Cheap check that the server is alive."""
    return {"status": "ok"}


@app.get("/api/users")
def get_users():
    """List all users from the database."""
    return db.list_users(app.state.db)
