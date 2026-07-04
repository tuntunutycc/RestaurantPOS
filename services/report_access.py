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


def assert_report_date_range(user: User, start: date, end: date) -> None:
    if start > end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    if user.role == ROLE_ACCOUNT:
        span = (end - start).days + 1
        if span > ACCOUNT_MAX_REPORT_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Account role is limited to {ACCOUNT_MAX_REPORT_DAYS} days per query",
            )
        oldest = datetime.utcnow().date() - timedelta(days=ACCOUNT_MAX_REPORT_DAYS - 1)
        if start < oldest:
            raise HTTPException(
                status_code=400,
                detail=f"Account role cannot view data older than {ACCOUNT_MAX_REPORT_DAYS} days",
            )


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
