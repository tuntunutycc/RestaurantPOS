"""Daily paid-order history query + Excel (.xlsx) export."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from models import Order, OrderItem

_PAID_STATUSES = ("paid", "completed")


def parse_history_date(raw: str) -> date:
    return datetime.strptime((raw or "").strip(), "%Y-%m-%d").date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    return start, end


def _item_status(oi: OrderItem) -> str:
    return str(getattr(oi, "item_status", getattr(oi, "status", "pending")) or "pending").strip().lower()


def active_lines(order: Order) -> list[OrderItem]:
    return [
        oi
        for oi in (order.order_items or [])
        if _item_status(oi) != "cancelled"
    ]


def query_daily_paid_orders(db: Session, day: date) -> list[Order]:
    start, end = day_bounds(day)
    return (
        db.query(Order)
        .options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))
        .filter(
            Order.status.in_(_PAID_STATUSES),
            Order.created_at >= start,
            Order.created_at < end,
        )
        .order_by(Order.created_at.asc(), Order.id.asc())
        .all()
    )


def line_item_detail_text(oi: OrderItem) -> str:
    name = (
        getattr(oi, "menu_item_name_at_sale", None)
        or getattr(getattr(oi, "menu_item", None), "name", None)
        or "[Deleted Item]"
    )
    parts = [str(name)]
    if bool(getattr(oi, "is_takeaway", False)):
        parts[0] = f"{parts[0]} (ပါဆယ်)"
    for raw in getattr(oi, "selected_modifiers", None) or []:
        if not isinstance(raw, dict):
            continue
        mod_name = str(raw.get("name") or "").strip()
        if not mod_name:
            continue
        try:
            qty = int(raw.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        if qty < 1:
            qty = 1
        parts.append(f"+ {mod_name}" if qty == 1 else f"+ {mod_name} x{qty}")
    note = (getattr(oi, "note", None) or getattr(oi, "special_instructions", None) or "").strip()
    if note:
        parts.append(f"Note: {note}")
    return " | ".join(parts)


def build_daily_history_xlsx(orders: Iterable[Order], day: date) -> bytes:
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover - env missing dependency
        raise RuntimeError(
            "Excel export requires openpyxl. Install with: pip install openpyxl"
        ) from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Orders"
    ws.append(["Order ID", "Time", "Item Details", "Qty", "Total Price"])

    for order in orders:
        created = getattr(order, "created_at", None)
        time_label = (
            created.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(created, datetime)
            else ""
        )
        lines = active_lines(order)
        if not lines:
            ws.append(
                [
                    int(order.id),
                    time_label,
                    "(no active items)",
                    0,
                    float(getattr(order, "total_amount", 0.0) or 0.0),
                ]
            )
            continue
        for oi in lines:
            ws.append(
                [
                    int(order.id),
                    time_label,
                    line_item_detail_text(oi),
                    int(getattr(oi, "quantity", 1) or 1),
                    float(getattr(oi, "subtotal", 0.0) or 0.0),
                ]
            )

    ws.append([])
    ws.append(["Report date", day.isoformat()])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
