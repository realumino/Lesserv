"""HTTP endpoints for user management.

Why a separate file: main.py stays tiny and each resource (users, later
system/config) gets its own file — the pattern grows with the project.
No SQL and no business rules live here; endpoints translate between HTTP
and the service layer.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from backend import db
from backend.models import UserCreate, UserOut, UserUpdate
from backend.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


def get_db(request: Request):
    """FastAPI dependency: hand the shared SQLite connection to an endpoint.

    Why not import the connection from main.py: that would be a circular
    import (main imports this router, the router would import main).
    `request.app` is the running FastAPI app whose `state.db` was set in
    the lifespan function — the same "bag" we put it in at startup.
    """
    return request.app.state.db


@router.get("", response_model=list[UserOut])
def list_users(conn=Depends(get_db)):
    """Return every user."""
    return db.list_users(conn)


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, conn=Depends(get_db)):
    """Create a user; 409 when the username is already taken."""
    if db.get_user(conn, payload.username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    return user_service.create_user(conn, payload)


@router.get("/{username}", response_model=UserOut)
def get_user(username: str, conn=Depends(get_db)):
    """Return one user; 404 when missing."""
    user = db.get_user(conn, username)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.put("/{username}", response_model=UserOut)
def update_user(username: str, payload: UserUpdate, conn=Depends(get_db)):
    """Partially update a user (None fields stay unchanged); 404 when missing."""
    user = user_service.update_user(conn, username, payload)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.delete("/{username}", status_code=204)
def delete_user(username: str, conn=Depends(get_db)):
    """Delete a user; 404 when missing. 204 means success with no body."""
    if not user_service.delete_user(conn, username):
        raise HTTPException(status_code=404, detail="user not found")
