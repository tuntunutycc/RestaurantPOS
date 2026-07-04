"""One-time root setup API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import create_access_token, hash_password
from database import get_db
from models import User
from rbac import ROLE_ROOT
from schemas import RootSetupRequest, SetupStatusResponse, TokenResponse, UserResponse
from services.sessions import create_session

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _root_exists(db: Session) -> bool:
    return (
        db.query(User)
        .filter(User.role == ROLE_ROOT, User.is_deleted.is_(False))
        .first()
        is not None
    )


@router.get("/status", response_model=SetupStatusResponse)
def setup_status(db: Session = Depends(get_db)):
    return SetupStatusResponse(needs_setup=not _root_exists(db))


@router.post("/root", response_model=TokenResponse)
def setup_root(body: RootSetupRequest, db: Session = Depends(get_db)):
    if _root_exists(db):
        raise HTTPException(status_code=403, detail="Root account already exists")

    username = body.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    user = User(
        username=username,
        role=ROLE_ROOT,
        password_hash=hash_password(body.password),
        pin_code=None,
    )
    db.add(user)
    try:
        db.flush()
        jti = create_session(db, user, "setup-device")
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username already exists")

    token = create_access_token(user.id, user.role, jti)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )
