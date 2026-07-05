"""Root API: admin account management and audit logs."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, require_roles
from database import get_db
from models import AdminAuditLog, User
from rbac import ROLE_ADMIN, ROLE_ROOT
from schemas import (
    AdminAuditLogResponse,
    ResetPasswordRequest,
    RootAdminCreateRequest,
    UserAdminResponse,
)
from services.audit import user_snapshot, write_admin_audit_log

router = APIRouter(prefix="/api/root", tags=["root"])


def _normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="username is required")
    return normalized


@router.get("/admins", response_model=list[UserAdminResponse])
def list_admins(
    db: Session = Depends(get_db),
    _root: User = Depends(require_roles([ROLE_ROOT])),
):
    return (
        db.query(User)
        .filter(User.role == ROLE_ADMIN, User.is_deleted.is_(False))
        .order_by(User.id.asc())
        .all()
    )


@router.post("/admins", response_model=UserAdminResponse)
def create_admin(
    body: RootAdminCreateRequest,
    db: Session = Depends(get_db),
    root: User = Depends(require_roles([ROLE_ROOT])),
):
    username = _normalize_username(body.username)
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    if db.query(User).filter(User.username == username, User.is_deleted.is_(False)).first():
        raise HTTPException(status_code=400, detail="username already exists")

    user = User(
        username=username,
        role=ROLE_ADMIN,
        password_hash=hash_password(body.password),
        pin_code=None,
    )
    db.add(user)
    try:
        db.flush()
        write_admin_audit_log(
            db,
            actor=root,
            action="root_create_admin",
            target=user,
            after=user_snapshot(user),
        )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username already exists")
    return user


@router.put("/admins/{user_id}", response_model=UserAdminResponse)
def update_admin(
    user_id: int,
    body: RootAdminCreateRequest,
    db: Session = Depends(get_db),
    root: User = Depends(require_roles([ROLE_ROOT])),
):
    user = db.query(User).filter(
        User.id == user_id, User.role == ROLE_ADMIN, User.is_deleted.is_(False)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin not found")

    username = _normalize_username(body.username)
    before = user_snapshot(user)

    if db.query(User).filter(
        User.username == username, User.id != user_id, User.is_deleted.is_(False)
    ).first():
        raise HTTPException(status_code=400, detail="username already exists")

    user.username = username
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="password must be at least 6 characters")
        user.password_hash = hash_password(body.password)
    user.pin_code = None

    try:
        write_admin_audit_log(
            db,
            actor=root,
            action="root_update_admin",
            target=user,
            before=before,
            after=user_snapshot(user),
        )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username already exists")
    return user


@router.delete("/admins/{user_id}")
def delete_admin(
    user_id: int,
    db: Session = Depends(get_db),
    root: User = Depends(require_roles([ROLE_ROOT])),
):
    user = db.query(User).filter(
        User.id == user_id, User.role == ROLE_ADMIN, User.is_deleted.is_(False)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin not found")

    before = user_snapshot(user)
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.pin_code = None
    write_admin_audit_log(
        db,
        actor=root,
        action="root_delete_admin",
        target=user,
        before=before,
        after=user_snapshot(user),
    )
    db.commit()
    return {"deleted": True, "user_id": user_id}


@router.post("/admins/{user_id}/reset-password")
def reset_admin_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    root: User = Depends(require_roles([ROLE_ROOT])),
):
    user = db.query(User).filter(
        User.id == user_id, User.role == ROLE_ADMIN, User.is_deleted.is_(False)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin not found")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    user.password_hash = hash_password(body.new_password)
    write_admin_audit_log(
        db,
        actor=root,
        action="root_reset_admin_password",
        target=user,
    )
    db.commit()
    return {"reset": True, "user_id": user_id}


@router.get("/audit-logs", response_model=list[AdminAuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db),
    _root: User = Depends(require_roles([ROLE_ROOT])),
    action: str | None = Query(default=None, description="Filter by action code"),
    start_date: date | None = Query(default=None, description="Inclusive start date (UTC)"),
    end_date: date | None = Query(default=None, description="Inclusive end date (UTC)"),
    limit: int = Query(default=100, ge=1, le=500),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    q = db.query(AdminAuditLog)
    if action:
        q = q.filter(AdminAuditLog.action == action.strip())
    if start_date:
        start_dt = datetime.combine(start_date, time.min)
        q = q.filter(AdminAuditLog.created_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date + timedelta(days=1), time.min)
        q = q.filter(AdminAuditLog.created_at < end_dt)

    rows = q.order_by(AdminAuditLog.created_at.desc()).limit(limit).all()
    result = []
    for row in rows:
        actor_name = row.actor.username if row.actor else None
        target_name = row.target.username if row.target else None
        result.append(
            AdminAuditLogResponse(
                id=row.id,
                actor_user_id=row.actor_user_id,
                actor_username=actor_name,
                action=row.action,
                target_user_id=row.target_user_id,
                target_username=target_name,
                detail_json=row.detail_json,
                created_at=row.created_at,
            )
        )
    return result
