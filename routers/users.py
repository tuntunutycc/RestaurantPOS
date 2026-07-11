"""Admin API: staff user management (CRUD + soft delete)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, require_roles
from database import get_db
from models import User
from rbac import (
    ADMIN_MANAGEABLE_ROLES,
    ADMIN_PANEL_ROLES,
    PIN_ROLES,
    ROLE_ADMIN,
    ROLE_ROOT,
)
from schemas import UserAdminResponse, UserCreateRequest
from services.audit import user_snapshot, write_admin_audit_log

router = APIRouter(prefix="/api", tags=["admin-users"])

_USERNAME_TAKEN_MSG = "Username is already taken (including by archived users)."
_PIN_TAKEN_MSG = "PIN code is already in use by an active user."


def _normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="username is required")
    return normalized


def _validate_staff_body(body: UserCreateRequest) -> None:
    if body.role not in ADMIN_MANAGEABLE_ROLES:
        raise HTTPException(status_code=400, detail="invalid staff role")
    if body.role in PIN_ROLES:
        if not body.pin_code:
            raise HTTPException(status_code=400, detail="pin_code is required for cashier/waiter/account")
    if body.password:
        raise HTTPException(
            status_code=400,
            detail="password is not allowed for staff roles; use PIN for cashier/waiter/account",
        )


def _reject_privileged_roles_via_staff_api(body: UserCreateRequest, actor: User) -> None:
    """Block admin/root creation or assignment through the staff user API."""
    if body.role not in (ROLE_ADMIN, ROLE_ROOT):
        return
    if actor.role == ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Admins cannot create admin or root users")
    raise HTTPException(
        status_code=403,
        detail="Admin and root accounts cannot be created via /api/admin/users; use /api/root/admins",
    )


def _assert_username_available(db: Session, username: str, *, exclude_user_id: int | None = None) -> None:
    q = db.query(User).filter(User.username == username)
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    if q.first():
        raise HTTPException(status_code=400, detail=_USERNAME_TAKEN_MSG)


def _assert_pin_available(db: Session, pin_code: str | None, *, exclude_user_id: int | None = None) -> None:
    if not pin_code:
        return
    q = db.query(User).filter(User.pin_code == pin_code, User.is_deleted.is_(False))
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    if q.first():
        raise HTTPException(status_code=400, detail=_PIN_TAKEN_MSG)


@router.get("/admin/users", response_model=list[UserAdminResponse])
def list_users(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """List floor staff (cashier, waiter, account), including soft-deleted rows."""
    q = db.query(User).filter(User.role.in_(tuple(ADMIN_MANAGEABLE_ROLES)))
    q = q.order_by(User.is_deleted.asc(), User.id.asc())
    return q.all()


@router.post("/admin/users", response_model=UserAdminResponse)
def create_user(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    if actor.role == ROLE_ADMIN and body.role not in ADMIN_MANAGEABLE_ROLES:
        raise HTTPException(status_code=403, detail="Admins cannot create admin or root users")

    _reject_privileged_roles_via_staff_api(body, actor)
    _validate_staff_body(body)
    username = _normalize_username(body.username)
    _assert_username_available(db, username)
    _assert_pin_available(db, body.pin_code)

    password_seed = "changeme"

    user = User(
        username=username,
        role=body.role,
        pin_code=body.pin_code if body.role in PIN_ROLES else None,
        password_hash=hash_password(password_seed),
    )
    db.add(user)
    try:
        db.flush()
        if actor.role == ROLE_ADMIN:
            write_admin_audit_log(
                db,
                actor=actor,
                action="admin_create_staff",
                target=user,
                after=user_snapshot(user),
                pin_set=bool(body.pin_code),
            )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_USERNAME_TAKEN_MSG)
    return user


@router.put("/admin/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if actor.role == ROLE_ADMIN:
        if user.role not in ADMIN_MANAGEABLE_ROLES:
            raise HTTPException(status_code=403, detail="Admins cannot edit admin or root users")
        if body.role not in ADMIN_MANAGEABLE_ROLES:
            raise HTTPException(status_code=403, detail="Admins cannot assign admin or root role")

    _reject_privileged_roles_via_staff_api(body, actor)
    _validate_staff_body(body)
    username = _normalize_username(body.username)
    before = user_snapshot(user)
    old_pin = user.pin_code

    _assert_username_available(db, username, exclude_user_id=user_id)
    _assert_pin_available(db, body.pin_code, exclude_user_id=user_id)

    user.username = username
    user.role = body.role
    user.pin_code = body.pin_code if body.role in PIN_ROLES else None

    try:
        if actor.role == ROLE_ADMIN:
            write_admin_audit_log(
                db,
                actor=actor,
                action="admin_update_staff",
                target=user,
                before=before,
                after=user_snapshot(user),
                pin_changed=body.pin_code != old_pin,
            )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_USERNAME_TAKEN_MSG)
    return user


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if actor.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if actor.role == ROLE_ADMIN:
        if user.role not in ADMIN_MANAGEABLE_ROLES:
            raise HTTPException(status_code=403, detail="Admins cannot delete admin or root users")

    before = user_snapshot(user)
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.pin_code = None
    if actor.role == ROLE_ADMIN:
        write_admin_audit_log(
            db,
            actor=actor,
            action="admin_delete_staff",
            target=user,
            before=before,
            after=user_snapshot(user),
        )
    db.commit()
    return {"deleted": True, "user_id": user_id}
