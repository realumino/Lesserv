"""HTTP endpoints for REALITY key management.

Why a separate router: users and system each own their resource; the
REALITY keys are a third one (list + rotate), and a dedicated file keeps
main.py tiny and the endpoint table obvious. No SQL and no key logic
live here — endpoints translate between HTTP and the service layer.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.services import config_service, reality_service, xray_service

router = APIRouter(prefix="/api/reality", tags=["reality"])


def get_db(request: Request):
    """FastAPI dependency: hand the shared SQLite connection to an endpoint.

    Why duplicated from the other routers: importing it from main.py
    would be a circular import; request.app.state.db is the connection
    stored by the lifespan function.
    """
    return request.app.state.db


def _loaded_config():
    """Return the user config, or raise 404 when there is none.

    Why 404 and not 503: the config file is absent on a fresh install —
    an expected state the frontend renders as an empty section, matching
    GET /api/config's error convention.
    """
    config = xray_service.load_config()
    if config is None:
        raise HTTPException(status_code=404, detail="config not found")
    return config


@router.get("")
def get_reality_keys(conn=Depends(get_db)):
    """List every REALITY inbound with its derived public key.

    Why the private key is not returned: clients only ever need `pbk`;
    the private key is visible where it is actually used (the runtime
    config pane) and nowhere else.
    """
    return {"keys": reality_service.list_keys(conn, _loaded_config())}


@router.post("/rotate")
def rotate_all_keys(conn=Depends(get_db)):
    """Rotate the key of every REALITY inbound and resync Xray.

    Why one call for all: replacing the whole key set is the operator's
    "start over" action; doing it in one request guarantees a consistent
    single restart instead of one bounce per inbound.
    """
    config = _loaded_config()
    tags = config_service.reality_inbound_tags(config)
    if not tags:
        raise HTTPException(status_code=404, detail="no REALITY inbounds in config")
    for tag in tags:
        reality_service.rotate_key(conn, tag)
    xray_service.sync(conn)
    return {"rotated": tags}


@router.post("/{tag}/rotate")
def rotate_key(tag: str, conn=Depends(get_db)):
    """Rotate the key of one REALITY inbound and resync Xray.

    Why 404 for a non-REALITY tag: rotating a key that Xray never reads
    would silently do nothing — the operator must learn the tag does not
    exist instead of seeing success.
    """
    config = _loaded_config()
    if tag not in config_service.reality_inbound_tags(config):
        raise HTTPException(
            status_code=404, detail=f"no REALITY inbound tagged '{tag}'"
        )
    reality_service.rotate_key(conn, tag)
    xray_service.sync(conn)
    return {"inbound": tag, "public_key": reality_service.public_key(conn, tag)}
