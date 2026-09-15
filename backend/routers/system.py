"""HTTP endpoints for system info and config management.

Why a separate file: each resource (users, system) gets its own router so
main.py stays tiny. These endpoints expose config metadata (for the
frontend's checkbox lists) and allow replacing the config via the API.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from backend import db
from backend.services import config_service, xray_service

router = APIRouter(prefix="/api", tags=["system"])


def get_db(request: Request):
    """FastAPI dependency: hand the shared SQLite connection to an endpoint.

    Why this exists in every router file: importing the connection from
    main.py would be a circular import. request.app is the running FastAPI
    app whose state.db was set in the lifespan function.
    """
    return request.app.state.db


@router.get("/inbounds")
def get_inbounds():
    """Return every inbound's tag and protocol from the loaded config.

    Why 503 when there is no config: an empty list would mislead the
    frontend — "zero inbounds" and "config missing" are different states.
    """
    config = xray_service.load_config()
    if config is None:
        raise HTTPException(status_code=503, detail="config not loaded")
    return config_service.inbound_summaries(config)


@router.get("/outbounds")
def get_outbounds():
    """Return every outbound's tag and protocol from the loaded config."""
    config = xray_service.load_config()
    if config is None:
        raise HTTPException(status_code=503, detail="config not loaded")
    return config_service.outbound_summaries(config)


@router.get("/status")
def get_status(conn=Depends(get_db)):
    """Return a composite snapshot of panel health.

    Why one endpoint bundles several checks: the frontend needs all of
    these at once for its status bar; separate calls would be noisy.
    """
    config = xray_service.load_config()
    proc = xray_service.status()
    users = db.list_users(conn)
    return {
        "config_loaded": config is not None,
        "xray_running": proc["running"],
        "xray_pid": proc["pid"],
        "user_count": len(users),
    }


@router.get("/config")
def get_config():
    """Return the current user-provided Xray config JSON.

    Why: the frontend Config page shows the config before replacing it.
    404 (not 503) because "no file yet" is the expected state on a fresh
    install — the page renders an empty state, not an error.
    """
    config = xray_service.load_config()
    if config is None:
        raise HTTPException(status_code=404, detail="config not found")
    return config


@router.get("/config/runtime")
def get_runtime_config():
    """Return the runtime config Xray reads, plus when it was written.

    Why the envelope: the Config tab shows the user config and the runtime
    config side by side; the timestamp reveals a file that predates the
    last change (a skipped or failed sync). 404 because before the first
    successful sync the file simply does not exist.
    """
    config = xray_service.load_runtime_config()
    if config is None:
        raise HTTPException(status_code=404, detail="runtime config not found")
    return {"config": config, "generated_at": xray_service.runtime_mtime()}


@router.post("/config")
def post_config(payload: dict = Body(...), conn=Depends(get_db)):
    """Replace the Xray config with the posted JSON body and resync Xray.

    Why the body is a plain dict (not a pydantic model): the config is
    opaque — the panel never validates or interprets its structure. Any
    valid JSON object is accepted. FastAPI rejects non-JSON bodies as 422.
    """
    xray_service.save_config(payload)
    xray_service.sync(conn)
    return {"message": "config updated"}
