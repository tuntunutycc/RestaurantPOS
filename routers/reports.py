"""Reports API: analytics and summaries."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Order, User
from schemas import TodaySalesSummaryResponse

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
