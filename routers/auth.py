"""Authentication API: login and token."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, verify_password
from database import get_db
from models import User
from schemas import LoginRequest, LoginPinRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

ALLOWED_ROLES = {"admin", "waiter", "kitchen", "cashier"}


@router.post("/login-pin", response_model=TokenResponse)
def login_pin(body: LoginPinRequest, db: Session = Depends(get_db)):
    """
    Authenticate with 4-digit PIN. Returns JWT and user info (id, username, role).
    Used by staff (waiter, kitchen, cashier) for fast login.
    """
    user = (
        db.query(User)
        .filter(User.pin_code == body.pin_code, User.is_deleted.is_(False))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong PIN",
        )
    token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username and password. Returns JWT and user info.
    """
    user = (
        db.query(User)
        .filter(User.username == body.username, User.is_deleted.is_(False))
        .first()
    )
    if not user:
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
    token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Return current authenticated user (validates token)."""
    return UserResponse(id=user.id, username=user.username, role=user.role)
