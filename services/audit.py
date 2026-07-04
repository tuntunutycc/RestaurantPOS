"""Audit log helpers for admin staff management."""

from typing import Any

from sqlalchemy.orm import Session

from models import AdminAuditLog, User

PIN_REDACTED = "[REDACTED]"


def _snapshot_user(user: User | None) -> dict[str, Any] | None:
    if not user:
        return None
    snap: dict[str, Any] = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_deleted": bool(getattr(user, "is_deleted", False)),
    }
    if getattr(user, "pin_code", None):
        snap["pin_code"] = PIN_REDACTED
    return snap


def write_admin_audit_log(
    db: Session,
    *,
    actor: User,
    action: str,
    target: User | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    pin_changed: bool = False,
    pin_set: bool = False,
) -> None:
    detail: dict[str, Any] = {}
    if before is not None:
        detail["before"] = before
    if after is not None:
        detail["after"] = after
    if pin_changed:
        detail["pin_changed"] = True
    if pin_set:
        detail["pin_set"] = True
    log = AdminAuditLog(
        actor_user_id=actor.id,
        action=action,
        target_user_id=target.id if target else None,
        detail_json=detail or None,
    )
    db.add(log)


def user_snapshot(user: User) -> dict[str, Any]:
    return _snapshot_user(user) or {}
