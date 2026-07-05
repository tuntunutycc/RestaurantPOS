"""Report access helpers: date-range policy and role checks."""

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException

from models import User
from rbac import (
    ACCOUNT_MAX_REPORT_DAYS,
    FULL_REPORT_ROLES,
    ROLE_ACCOUNT,
    ROLE_ADMIN,
    ROLE_CASHIER,
    ROLE_ROOT,
)

ACCOUNT_ACCESS_DENIED_DETAIL = (
    "Access denied. Accountant access is strictly limited to the last 90 days of financial data."
)


def account_oldest_allowed_start() -> date:
    """Earliest start_date (inclusive) for account role: today minus (90 - 1) days."""
    return datetime.utcnow().date() - timedelta(days=ACCOUNT_MAX_REPORT_DAYS - 1)


def assert_report_date_range(user: User, start: date, end: date) -> None:
    if start > end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    if user.role == ROLE_ACCOUNT:
        span = (end - start).days + 1
        if span > ACCOUNT_MAX_REPORT_DAYS:
            raise HTTPException(status_code=400, detail=ACCOUNT_ACCESS_DENIED_DETAIL)
        oldest = account_oldest_allowed_start()
        if start < oldest:
            raise HTTPException(status_code=400, detail=ACCOUNT_ACCESS_DENIED_DETAIL)


def dt_range_for_dates(start: date, end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)
    return start_dt, end_dt


def can_view_store_reports(user: User) -> bool:
    return user.role in FULL_REPORT_ROLES or user.role in (ROLE_ROOT, ROLE_ADMIN)


def can_view_staff_breakdown(user: User) -> bool:
    return user.role in (ROLE_ROOT, ROLE_ADMIN, ROLE_CASHIER)


def can_view_all_waiter_sales(user: User) -> bool:
    return user.role in (ROLE_ROOT, ROLE_ADMIN, ROLE_CASHIER)
