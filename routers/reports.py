"""Reports API: analytics and summaries."""

from datetime import date, datetime, time, timedelta
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Category, MenuItem, Order, OrderItem, User
from routers.menu import ARCHIVED_CATEGORY_NAME
from rbac import (
    ROLE_ACCOUNT,
    ROLE_CASHIER,
    ROLE_ROOT,
    ROLE_ADMIN,
    ROLE_WAITER,
)
from schemas import (
    CancelledItemCountResponse,
    CancellationsSummaryResponse,
    CategorySalesPointResponse,
    DailySalesPointResponse,
    HourlySalesTrendResponse,
    MonthlySalesPointResponse,
    PromotedStaffSalesResponse,
    SalesPeriodReportResponse,
    StaffSalesPointResponse,
    TopSellingItemResponse,
    TodaySalesSummaryResponse,
)
from services.report_access import (
    ACCOUNT_ACCESS_DENIED_DETAIL,
    account_oldest_allowed_start,
    assert_report_date_range,
    dt_range_for_dates,
)

router = APIRouter(prefix="/api")
DELETED_ITEM_LABEL = "[Deleted Item]"
DELETED_CATEGORY_LABEL = "[Deleted Category]"


def _historical_item_name_expr():
    """Prefer sale-time snapshot; live MenuItem name is fallback for legacy rows."""
    return func.coalesce(
        OrderItem.menu_item_name_at_sale,
        MenuItem.name,
        DELETED_ITEM_LABEL,
    )


def _historical_category_name_expr():
    """Prefer sale-time snapshot; ignore system archive bucket as live category name."""
    return func.coalesce(
        OrderItem.category_name_at_sale,
        case((Category.name == ARCHIVED_CATEGORY_NAME, None), else_=Category.name),
        DELETED_CATEGORY_LABEL,
    )


_DASHBOARD_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT]
_SUMMARY_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT, ROLE_CASHIER]
_PAID_STATUSES = ("paid", "completed")


def _parse_sales_period_bounds(period: str, date_value: str) -> tuple[date, date, str]:
    """Return (start_date, end_date, normalized_date_echo) for daily/monthly."""
    normalized_period = (period or "").strip().lower()
    raw = (date_value or "").strip()
    if normalized_period == "daily":
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="date must be YYYY-MM-DD for period=daily",
            ) from exc
        return day, day, day.isoformat()
    if normalized_period == "monthly":
        try:
            parsed = datetime.strptime(raw, "%Y-%m")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="date must be YYYY-MM for period=monthly",
            ) from exc
        year, month = parsed.year, parsed.month
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end, f"{year:04d}-{month:02d}"
    raise HTTPException(status_code=400, detail="period must be 'daily' or 'monthly'")


@router.get("/reports/sales", response_model=SalesPeriodReportResponse)
def get_sales_period_report(
    period: str = Query(..., description="daily or monthly"),
    report_date: str = Query(
        ...,
        alias="date",
        description="YYYY-MM-DD (daily) or YYYY-MM (monthly)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """
    Aggregate paid-order sales for one day or one calendar month.
    subtotal_revenue is tax-exclusive (grand_total − tax); grand_total_revenue is tax-inclusive.
    """
    start_day, end_day, date_echo = _parse_sales_period_bounds(period, report_date)
    assert_report_date_range(current_user, start_day, end_day)
    start_dt, end_dt = dt_range_for_dates(start_day, end_day)

    cash_expr = func.coalesce(
        func.sum(
            case(
                (Order.cash_amount.isnot(None), Order.cash_amount),
                (func.lower(Order.payment_method) == "cash", Order.total_amount),
                else_=0.0,
            )
        ),
        0.0,
    )
    mobile_expr = func.coalesce(
        func.sum(
            case(
                (Order.mobile_money_amount.isnot(None), Order.mobile_money_amount),
                (func.lower(Order.payment_method) == "mobile_money", Order.total_amount),
                else_=0.0,
            )
        ),
        0.0,
    )
    tax_expr = func.coalesce(func.sum(func.coalesce(Order.tax_amount, 0.0)), 0.0)
    grand_expr = func.coalesce(func.sum(Order.total_amount), 0.0)

    row = (
        db.query(
            func.count(Order.id),
            grand_expr,
            tax_expr,
            cash_expr,
            mobile_expr,
        )
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(_PAID_STATUSES),
        )
        .one()
    )
    total_orders = int(row[0] or 0)
    grand_total = round(float(row[1] or 0.0), 2)
    total_tax = round(float(row[2] or 0.0), 2)
    total_cash = round(float(row[3] or 0.0), 2)
    total_mobile = round(float(row[4] or 0.0), 2)
    subtotal_revenue = round(grand_total - total_tax, 2)

    return SalesPeriodReportResponse(
        period="monthly" if (period or "").strip().lower() == "monthly" else "daily",
        date=date_echo,
        total_orders=total_orders,
        subtotal_revenue=subtotal_revenue,
        total_tax=total_tax,
        grand_total_revenue=grand_total,
        total_cash=total_cash,
        total_mobile=total_mobile,
    )


@router.get("/reports/summary/today", response_model=TodaySalesSummaryResponse)
def get_today_sales_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_SUMMARY_ROLES)),
):
    """
    Return today's sales summary:
    - total_sales
    - total_orders
    - average_order_value
    """
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    q = db.query(
        func.coalesce(func.sum(Order.total_amount), 0.0),
        func.count(Order.id),
        func.coalesce(func.sum(func.coalesce(Order.tax_amount, 0.0)), 0.0),
    ).filter(
        Order.created_at >= start_of_day,
        Order.created_at < end_of_day,
        Order.status.in_(("paid", "completed")),
    )
    if current_user.role == ROLE_CASHIER:
        q = q.filter(Order.checked_out_by_id == current_user.id)

    total_sales, total_orders, total_tax = q.one()

    total_sales = float(total_sales or 0.0)
    total_orders = int(total_orders or 0)
    total_tax = float(total_tax or 0.0)
    subtotal_revenue = round(total_sales - total_tax, 2)
    average_order_value = (total_sales / total_orders) if total_orders > 0 else 0.0

    return TodaySalesSummaryResponse(
        total_sales=total_sales,
        total_orders=total_orders,
        average_order_value=average_order_value,
        subtotal_revenue=subtotal_revenue,
        total_tax=round(total_tax, 2),
        grand_total_revenue=round(total_sales, 2),
    )


@router.get("/reports/top-items", response_model=list[TopSellingItemResponse])
def get_top_selling_items_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """Return today's top 5 selling items by quantity (paid/completed orders only)."""
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    rows = (
        db.query(
            OrderItem.menu_item_id,
            _historical_item_name_expr().label("menu_item_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id, isouter=True)
        .filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
        )
        .group_by(OrderItem.menu_item_id, _historical_item_name_expr())
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    return [
        TopSellingItemResponse(
            item_name=str(row.menu_item_name or ""),
            quantity_sold=int(row.quantity_sold or 0),
        )
        for row in rows
    ]


@router.get("/reports/hourly-trend", response_model=list[HourlySalesTrendResponse])
def get_hourly_sales_trend_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """Return today's hourly sales totals from paid/completed orders."""
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    rows = (
        db.query(
            func.extract("hour", Order.created_at).label("hour_of_day"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total_sales"),
        )
        .filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day,
            Order.status.in_(("paid", "completed")),
        )
        .group_by(func.extract("hour", Order.created_at))
        .order_by(func.extract("hour", Order.created_at).asc())
        .all()
    )

    return [
        HourlySalesTrendResponse(
            hour=f"{int(row.hour_of_day):02d}:00",
            total=float(row.total_sales or 0.0),
        )
        for row in rows
    ]


@router.get("/reports/daily-sales", response_model=list[DailySalesPointResponse])
def get_daily_sales_history(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """
    Return daily sales totals for a date range.
    Defaults to last 30 days (inclusive) when query params are not provided.
    """
    today = datetime.utcnow().date()
    effective_end = end_date or today
    effective_start = start_date or (effective_end - timedelta(days=29))
    assert_report_date_range(current_user, effective_start, effective_end)

    start_dt, end_dt = dt_range_for_dates(effective_start, effective_end)

    rows = (
        db.query(
            func.date(Order.created_at).label("day_date"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total"),
        )
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at).asc())
        .all()
    )

    return [
        DailySalesPointResponse(
            date=str(row.day_date),
            total=float(row.total or 0.0),
        )
        for row in rows
    ]


@router.get("/reports/monthly-sales", response_model=list[MonthlySalesPointResponse])
def get_monthly_sales_history(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """
    Return monthly sales totals for a given year.
    Defaults to current UTC year when year is not provided.
    """
    target_year = year or datetime.utcnow().year
    start_dt = datetime(target_year, 1, 1)
    end_dt = datetime(target_year + 1, 1, 1)
    if current_user.role == ROLE_ACCOUNT:
        oldest = account_oldest_allowed_start()
        if date(target_year, 12, 31) < oldest:
            raise HTTPException(status_code=400, detail=ACCOUNT_ACCESS_DENIED_DETAIL)
        oldest_dt = datetime.combine(oldest, time.min)
        if start_dt < oldest_dt:
            start_dt = oldest_dt

    rows = (
        db.query(
            func.extract("month", Order.created_at).label("month_num"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total"),
        )
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
        )
        .group_by(func.extract("month", Order.created_at))
        .order_by(func.extract("month", Order.created_at).asc())
        .all()
    )

    return [
        MonthlySalesPointResponse(
            month=calendar.month_abbr[int(row.month_num)],
            total=float(row.total or 0.0),
        )
        for row in rows
    ]


@router.get("/reports/category-sales", response_model=list[CategorySalesPointResponse])
def get_category_sales_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """
    Return category-level sales totals for the current month (UTC).
    Includes paid/completed orders only.
    """
    now = datetime.utcnow()
    start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end_dt = datetime(now.year + 1, 1, 1)
    else:
        end_dt = datetime(now.year, now.month + 1, 1)

    category_name = _historical_category_name_expr()
    rows = (
        db.query(
            category_name.label("category_name"),
            func.coalesce(func.sum(OrderItem.subtotal), 0.0).label("total_sales"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id, isouter=True)
        .join(Category, Category.id == MenuItem.category_id, isouter=True)
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
        )
        .group_by(category_name)
        .order_by(func.sum(OrderItem.subtotal).desc())
        .all()
    )

    return [
        CategorySalesPointResponse(
            category_name=str(row.category_name or "Uncategorized"),
            total_sales=float(row.total_sales or 0.0),
        )
        for row in rows
    ]


@router.get("/reports/cancellations", response_model=CancellationsSummaryResponse)
def get_cancellations_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_DASHBOARD_ROLES)),
):
    """
    Return cancellation analytics:
    - total_cancelled_items (summed by quantity)
    - total_lost_revenue (summed by subtotal)
    - top_cancelled_items (highest cancelled quantities by item)
    """
    total_cancelled_items, total_lost_revenue = (
        db.query(
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.subtotal), 0.0),
        )
        .filter(OrderItem.item_status == "cancelled")
        .one()
    )

    item_name = _historical_item_name_expr()
    top_rows = (
        db.query(
            item_name.label("item_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("cancel_count"),
        )
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id, isouter=True)
        .filter(OrderItem.item_status == "cancelled")
        .group_by(item_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    return CancellationsSummaryResponse(
        total_cancelled_items=int(total_cancelled_items or 0),
        total_lost_revenue=float(total_lost_revenue or 0.0),
        top_cancelled_items=[
            CancelledItemCountResponse(
                item_name=str(row.item_name or ""),
                count=int(row.cancel_count or 0),
            )
            for row in top_rows
        ],
    )


_STAFF_REPORT_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT]
_ORDER_STAFF_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_WAITER]


@router.get("/reports/sales/by-cashier", response_model=list[StaffSalesPointResponse])
def get_sales_by_cashier(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_STAFF_REPORT_ROLES)),
):
    """Per-cashier checkout totals (uses Order.checked_out_by_id)."""
    today = datetime.utcnow().date()
    effective_end = end_date or today
    effective_start = start_date or effective_end
    assert_report_date_range(current_user, effective_start, effective_end)
    start_dt, end_dt = dt_range_for_dates(effective_start, effective_end)

    q = (
        db.query(
            User.id.label("user_id"),
            User.username.label("username"),
            User.role.label("role"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total_sales"),
            func.count(Order.id).label("order_count"),
        )
        .join(Order, Order.checked_out_by_id == User.id)
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
            User.is_deleted.is_(False),
        )
        .group_by(User.id, User.username, User.role)
        .order_by(func.sum(Order.total_amount).desc())
    )

    rows = q.all()
    return [
        StaffSalesPointResponse(
            user_id=int(row.user_id),
            username=str(row.username),
            role=str(row.role),
            total_sales=float(row.total_sales or 0.0),
            order_count=int(row.order_count or 0),
        )
        for row in rows
    ]


@router.get("/reports/sales/by-order-staff", response_model=list[StaffSalesPointResponse])
def get_sales_by_order_staff(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_ORDER_STAFF_ROLES)),
):
    """Per-staff order item sales (uses OrderItem.created_by_id)."""
    today = datetime.utcnow().date()
    effective_end = end_date or today
    effective_start = start_date or effective_end
    if current_user.role == ROLE_ACCOUNT:
        raise HTTPException(status_code=403, detail="Account role cannot view staff order breakdown")
    assert_report_date_range(current_user, effective_start, effective_end)
    start_dt, end_dt = dt_range_for_dates(effective_start, effective_end)

    q = (
        db.query(
            User.id.label("user_id"),
            User.username.label("username"),
            User.role.label("role"),
            func.coalesce(func.sum(OrderItem.subtotal), 0.0).label("total_sales"),
            func.count(OrderItem.id).label("order_count"),
        )
        .join(OrderItem, OrderItem.created_by_id == User.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
            User.is_deleted.is_(False),
        )
        .group_by(User.id, User.username, User.role)
        .order_by(func.sum(OrderItem.subtotal).desc())
    )
    if current_user.role == ROLE_WAITER:
        q = q.filter(User.id == current_user.id)

    rows = q.all()
    return [
        StaffSalesPointResponse(
            user_id=int(row.user_id),
            username=str(row.username),
            role=str(row.role),
            total_sales=float(row.total_sales or 0.0),
            order_count=int(row.order_count or 0),
        )
        for row in rows
    ]


_PROMOTED_REPORT_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_WAITER]


@router.get("/reports/sales/promoted-by-waiter", response_model=list[PromotedStaffSalesResponse])
def get_promoted_sales_by_waiter(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_PROMOTED_REPORT_ROLES)),
):
    """Per-staff promoted menu item sales (OrderItem lines for MenuItem.is_promoted)."""
    today = datetime.utcnow().date()
    effective_end = end_date or today
    effective_start = start_date or effective_end
    assert_report_date_range(current_user, effective_start, effective_end)
    start_dt, end_dt = dt_range_for_dates(effective_start, effective_end)

    q = (
        db.query(
            User.id.label("user_id"),
            User.username.label("username"),
            User.role.label("role"),
            func.coalesce(func.sum(OrderItem.subtotal), 0.0).label("total_sales"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
            func.count(OrderItem.id).label("line_count"),
        )
        .join(OrderItem, OrderItem.created_by_id == User.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .filter(
            MenuItem.is_promoted.is_(True),
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
            User.is_deleted.is_(False),
        )
        .group_by(User.id, User.username, User.role)
        .order_by(func.sum(OrderItem.subtotal).desc())
    )
    if current_user.role == ROLE_WAITER:
        q = q.filter(User.id == current_user.id)

    rows = q.all()
    return [
        PromotedStaffSalesResponse(
            user_id=int(row.user_id),
            username=str(row.username),
            role=str(row.role),
            total_sales=float(row.total_sales or 0.0),
            quantity=int(row.quantity or 0),
            line_count=int(row.line_count or 0),
        )
        for row in rows
    ]
