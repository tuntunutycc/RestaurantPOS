"""Reports API: analytics and summaries."""

from datetime import date, datetime, time, timedelta
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Category, MenuItem, Order, OrderItem, User
from schemas import (
    CancelledItemCountResponse,
    CancellationsSummaryResponse,
    CategorySalesPointResponse,
    DailySalesPointResponse,
    HourlySalesTrendResponse,
    MonthlySalesPointResponse,
    TopSellingItemResponse,
    TodaySalesSummaryResponse,
)

router = APIRouter(prefix="/api")


@router.get("/reports/summary/today", response_model=TodaySalesSummaryResponse)
def get_today_sales_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cashier"])),
):
    """
    Return today's sales summary:
    - total_sales
    - total_orders
    - average_order_value
    """
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    total_sales, total_orders = (
        db.query(
            func.coalesce(func.sum(Order.total_amount), 0.0),
            func.count(Order.id),
        )
        .filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day,
            Order.status.in_(("paid", "completed")),
        )
        .one()
    )

    total_sales = float(total_sales or 0.0)
    total_orders = int(total_orders or 0)
    average_order_value = (total_sales / total_orders) if total_orders > 0 else 0.0

    return TodaySalesSummaryResponse(
        total_sales=total_sales,
        total_orders=total_orders,
        average_order_value=average_order_value,
    )


@router.get("/reports/top-items", response_model=list[TopSellingItemResponse])
def get_top_selling_items_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cashier"])),
):
    """Return today's top 5 selling items by quantity (paid/completed orders only)."""
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    rows = (
        db.query(
            OrderItem.menu_item_id,
            func.coalesce(MenuItem.name, "").label("menu_item_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
        )
        .group_by(OrderItem.menu_item_id, MenuItem.name)
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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
):
    """
    Return daily sales totals for a date range.
    Defaults to last 30 days (inclusive) when query params are not provided.
    """
    today = datetime.utcnow().date()
    effective_end = end_date or today
    effective_start = start_date or (effective_end - timedelta(days=29))
    if effective_start > effective_end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    start_dt = datetime.combine(effective_start, time.min)
    end_dt = datetime.combine(effective_end + timedelta(days=1), time.min)

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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
):
    """
    Return monthly sales totals for a given year.
    Defaults to current UTC year when year is not provided.
    """
    target_year = year or datetime.utcnow().year
    start_dt = datetime(target_year, 1, 1)
    end_dt = datetime(target_year + 1, 1, 1)

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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
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

    rows = (
        db.query(
            func.coalesce(Category.name, "Uncategorized").label("category_name"),
            func.coalesce(func.sum(OrderItem.subtotal), 0.0).label("total_sales"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Category, Category.id == MenuItem.category_id, isouter=True)
        .filter(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(("paid", "completed")),
            OrderItem.item_status != "cancelled",
        )
        .group_by(Category.name)
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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
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

    top_rows = (
        db.query(
            func.coalesce(MenuItem.name, "").label("item_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("cancel_count"),
        )
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .filter(OrderItem.item_status == "cancelled")
        .group_by(MenuItem.name)
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
