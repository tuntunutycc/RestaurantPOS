"""User session management for device-aware JWT auth."""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from models import User, UserSession
from rbac import SINGLE_DEVICE_ROLES


def revoke_user_sessions(db: Session, user_id: int) -> None:
    """Revoke all active sessions for a user."""
    now = datetime.utcnow()
    (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .update({UserSession.revoked_at: now}, synchronize_session=False)
    )


def create_session(db: Session, user: User, device_id: str) -> str:
    """
    Create a new session for the user. For single-device roles, revoke prior sessions first.
    Returns the new session jti.
    """
    if user.role in SINGLE_DEVICE_ROLES:
        revoke_user_sessions(db, user.id)

    jti = uuid.uuid4().hex
    session = UserSession(
        user_id=user.id,
        jti=jti,
        device_id=device_id or "unknown",
    )
    db.add(session)
    db.flush()
    return jti


def get_active_session(db: Session, jti: str) -> UserSession | None:
    return (
        db.query(UserSession)
        .filter(
            UserSession.jti == jti,
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
