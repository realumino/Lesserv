"""HTTP endpoints for system info and config management.

Why a separate file: each resource (users, system) gets its own router so
main.py stays tiny. These endpoints expose template metadata (for the
frontend's checkbox lists) and allow replacing the template via the API.
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
    """Return every inbound's tag and protocol from the loaded template.

    Why 503 when there is no template: an empty list would mislead the
    frontend — "zero inbounds" and "template missing" are different states.
    """
    template = xray_service.load_template()
    if template is None:
        raise HTTPException(status_code=503, detail="template not loaded")
    return config_service.inbound_summaries(template)


@router.get("/outbounds")
def get_outbounds():
    """Return every outbound's tag and protocol from the loaded template."""
    template = xray_service.load_template()
    if template is None:
        raise HTTPException(status_code=503, detail="template not loaded")
    return config_service.outbound_summaries(template)


@router.get("/status")
def get_status(conn=Depends(get_db)):
    """Return a composite snapshot of panel health.

    Why one endpoint bundles several checks: the frontend needs all of
    these at once for its status bar; separate calls would be noisy.
    """
    template = xray_service.load_template()
    proc = xray_service.status()
    users = db.list_users(conn)
    return {
        "template_loaded": template is not None,
        "xray_running": proc["running"],
        "xray_pid": proc["pid"],
        "user_count": len(users),
    }


@router.get("/config")
def get_config():
    """Return the current Xray template JSON.

    Why: the frontend Config page shows the template before replacing it.
    404 (not 503) because "no file yet" is the expected state on a fresh
    install — the page renders an empty state, not an error.
    """
    template = xray_service.load_template()
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    return template


@router.post("/config")
def post_config(payload: dict = Body(...), conn=Depends(get_db)):
    """Replace the Xray template with the posted JSON body and resync Xray.

    Why the body is a plain dict (not a pydantic model): the template is
    opaque — the panel never validates or interprets its structure. Any
    valid JSON object is accepted. FastAPI rejects non-JSON bodies as 422.
    """
    xray_service.save_template(payload)
    xray_service.sync(conn)
    return {"message": "config updated"}