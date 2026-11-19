"""Daily voucher numbers (specs/feature-voucher-number).

A voucher is `YYYYMMDD-NNNN`: the Myanmar date of checkout plus a sequence that
restarts at 1 every day. The next number is read from the orders that exist
(MAX + 1); the unique index `ux_orders_voucher` stops two checkouts from taking
the same number, and the checkout retries when that happens.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Order

# Myanmar Standard Time is UTC+06:30 and has no daylight saving.
VOUCHER_UTC_OFFSET = timedelta(hours=6, minutes=30)
# A number clash is retried this many times before the checkout gives up.
MAX_VOUCHER_ATTEMPTS = 5


def voucher_date_for(now_utc: datetime | None = None) -> str:
    """`YYYYMMDD` of the Myanmar calendar day that `now_utc` (naive UTC) falls in."""
    moment = now_utc if now_utc is not None else datetime.utcnow()
    return (moment + VOUCHER_UTC_OFFSET).strftime("%Y%m%d")


def format_voucher_no(voucher_date: str, seq: int) -> str:
    return f"{voucher_date}-{int(seq):04d}"


def next_voucher_seq(db: Session, voucher_date: str) -> int:
    highest = (
        db.query(func.max(Order.voucher_seq))
        .filter(Order.voucher_date == voucher_date)
        .scalar()
    )
    return int(highest or 0) + 1


def assign_voucher(db: Session, order: Order, now_utc: datetime | None = None) -> str:
    """Give `order` the next voucher of today. An order that has one keeps it."""
    if order.voucher_no is not None:
        return order.voucher_no
    voucher_date = voucher_date_for(now_utc)
    order.voucher_date = voucher_date
    order.voucher_seq = next_voucher_seq(db, voucher_date)
    return order.voucher_no  # type: ignore[return-value]
