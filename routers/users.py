"""Admin API: user management (CRUD + soft delete)."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, require_roles
from database import get_db
from models import User
from schemas import UserAdminResponse, UserCreateRequest

router = APIRouter(prefix="/api", tags=["admin-users"])


@router.get("/admin/users", response_model=list[UserAdminResponse])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_roles(["admin"]))):
    return (
        db.query(User)
        .filter(User.is_deleted.is_(False))
        .order_by(User.id.asc())
        .all()
    )


@router.post("/admin/users", response_model=UserAdminResponse)
def create_user(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    normalized_username = body.username.strip().lower()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="username is required")

    if db.query(User).filter(User.username == normalized_username, User.is_deleted.is_(False)).first():
        raise HTTPException(status_code=400, detail="username already exists")
    if db.query(User).filter(User.pin_code == body.pin_code, User.is_deleted.is_(False)).first():
        raise HTTPException(status_code=400, detail="pin_code already exists")

    # Store a password hash so password-login keeps working for admins.
    # Staff login uses PIN, not password, but having a hash is still required by the model.
    password_seed = body.pin_code if body.role == "admin" else "changeme"

    user = User(
        username=normalized_username,
        role=body.role,
        pin_code=body.pin_code,
        password_hash=hash_password(password_seed),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username or pin_code already exists")
    db.refresh(user)
    return user


@router.put("/admin/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    normalized_username = body.username.strip().lower()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="username is required")

    # Uniqueness checks (ignore current user id)
    if db.query(User).filter(
        User.username == normalized_username,
        User.id != user_id,
        User.is_deleted.is_(False),
    ).first():
        raise HTTPException(status_code=400, detail="username already exists")
    if db.query(User).filter(
        User.pin_code == body.pin_code,
        User.id != user_id,
        User.is_deleted.is_(False),
    ).first():
        raise HTTPException(status_code=400, detail="pin_code already exists")

    user.username = normalized_username
    user.role = body.role
    user.pin_code = body.pin_code
    # Password changes are intentionally not part of this UI/API (PIN login for staff).
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username or pin_code already exists")
    db.refresh(user)
    return user


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(["admin"])),
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_admin.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.is_deleted.is_(False)).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    db.commit()
    return {"deleted": True, "user_id": user_id}

