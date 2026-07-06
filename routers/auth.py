"""Authentication API: login and token."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from database import get_db
from models import User
from rbac import ALL_ROLES, PASSWORD_ROLES, PIN_ROLES, ROLE_ROOT
from schemas import (
    ChangePasswordRequest,
    LoginPinRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from services.sessions import create_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _device_id(raw: str | None) -> str:
    value = (raw or "").strip()
    return value or "unknown"


@router.post("/login-pin", response_model=TokenResponse)
def login_pin(body: LoginPinRequest, db: Session = Depends(get_db)):
    """Authenticate with 4-digit PIN (cashier, waiter, account). Single-device: new login revokes prior sessions."""
    user = (
        db.query(User)
        .filter(User.pin_code == body.pin_code, User.is_deleted.is_(False))
        .first()
    )
    if not user or user.role not in PIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong PIN",
        )
    jti = create_session(db, user, _device_id(body.device_id))
    db.commit()
    token = create_access_token(user.id, user.role, jti)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username and password (root, admin only).

    root/admin: multi-device sessions allowed.
    """
    user = (
        db.query(User)
        .filter(User.username == body.username.strip().lower(), User.is_deleted.is_(False))
        .first()
    )
    if not user or user.role not in PASSWORD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    try:
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    jti = create_session(db, user, _device_id(body.device_id))
    db.commit()
    token = create_access_token(user.id, user.role, jti)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Return current authenticated user (validates token)."""
    return UserResponse(id=user.id, username=user.username, role=user.role)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change own password (root, admin only). PIN roles receive 403."""
    if user.role not in PASSWORD_ROLES:
        raise HTTPException(status_code=403, detail="Password change not allowed for this role")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="new_password must be at least 6 characters")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current_password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"changed": True}
