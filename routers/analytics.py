"""Analytics API: payment-method sales breakdown."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Order, User
from rbac import ROLE_ACCOUNT, ROLE_ADMIN, ROLE_CASHIER, ROLE_ROOT
from schemas import PaymentMethodTotalsResponse, SalesBreakdownResponse

router = APIRouter(prefix="/api/analytics")

_ANALYTICS_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT, ROLE_CASHIER]
_PAID_STATUSES = ("paid", "completed")


def _month_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def _aggregate_payment_totals(
    db: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    checked_out_by_id: int | None = None,
) -> PaymentMethodTotalsResponse:
    # Prefer stored per-method amounts; fall back to legacy payment_method + total.
    cash_expr = func.coalesce(
        func.sum(
            case(
                (
                    Order.cash_amount.isnot(None),
                    Order.cash_amount,
                ),
                (func.lower(Order.payment_method) == "cash", Order.total_amount),
                else_=0.0,
            )
        ),
        0.0,
    )
    mobile_expr = func.coalesce(
        func.sum(
            case(
                (
                    Order.mobile_money_amount.isnot(None),
                    Order.mobile_money_amount,
                ),
                (func.lower(Order.payment_method) == "mobile_money", Order.total_amount),
                else_=0.0,
            )
        ),
        0.0,
    )
    tax_expr = func.coalesce(func.sum(func.coalesce(Order.tax_amount, 0.0)), 0.0)
    grand_expr = func.coalesce(func.sum(Order.total_amount), 0.0)
    q = db.query(cash_expr, mobile_expr, tax_expr, grand_expr).filter(
        Order.created_at >= start_dt,
        Order.created_at < end_dt,
        Order.status.in_(_PAID_STATUSES),
    )
    if checked_out_by_id is not None:
        q = q.filter(Order.checked_out_by_id == checked_out_by_id)

    cash_total, mobile_total, tax_total, grand_total = q.one()
    cash = float(cash_total or 0.0)
    mobile = float(mobile_total or 0.0)
    tax = float(tax_total or 0.0)
    grand = float(grand_total or 0.0)
    return PaymentMethodTotalsResponse(
        cash=round(cash, 2),
        mobile_money=round(mobile, 2),
        total=round(cash + mobile, 2),
        subtotal_revenue=round(grand - tax, 2),
        total_tax=round(tax, 2),
        grand_total_revenue=round(grand, 2),
    )


@router.get("/sales-breakdown", response_model=SalesBreakdownResponse)
def get_sales_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_ANALYTICS_ROLES)),
):
    """
    Return today and current-month paid-order totals grouped by payment method.
    Cashiers see only orders they checked out; admin/root/account see store-wide totals.
    """
    now = datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    month_start, month_end = _month_bounds_utc(now)

    scope_user_id = current_user.id if current_user.role == ROLE_CASHIER else None

    today = _aggregate_payment_totals(
        db,
        start_dt=start_of_day,
        end_dt=end_of_day,
        checked_out_by_id=scope_user_id,
    )
    month = _aggregate_payment_totals(
        db,
        start_dt=month_start,
        end_dt=month_end,
        checked_out_by_id=scope_user_id,
    )
    return SalesBreakdownResponse(today=today, month=month)
