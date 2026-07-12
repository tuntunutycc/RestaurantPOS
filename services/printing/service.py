"""Kitchen ticket and cashier receipt dispatch service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from services.printing.backends.escpos_network import send_network_ticket
from services.printing.backends.file import send_file_ticket, send_file_ticket_image
from services.printing.config import CASHIER_PRINTER_ROUTE
from services.printing.image_renderer import render_ticket_image
from services.printing.receipt import build_receipt_text
from services.printing.settings import load_printer_config
from services.printing.ticket import (
    build_escpos_raster_payload,
    build_escpos_text_payload,
    build_ticket_text,
)

logger = logging.getLogger(__name__)


async def _dispatch_payload(
    *,
    route: str,
    ticket_text: str,
    db: Session | None = None,
) -> None:
    config = load_printer_config(db)
    if config.render_mode == "image":
        image = render_ticket_image(
            ticket_text,
            paper_width_px=config.paper_width_px,
            font_path=config.font_path,
        )
        escpos_payload = build_escpos_raster_payload(image)
        if config.backend == "escpos_network":
            await asyncio.to_thread(send_network_ticket, config, route, escpos_payload)
            return
        await asyncio.to_thread(send_file_ticket_image, config, route, image)
        return

    escpos_payload = build_escpos_text_payload(ticket_text)
    if config.backend == "escpos_network":
        await asyncio.to_thread(send_network_ticket, config, route, escpos_payload)
        return
    await asyncio.to_thread(send_file_ticket, config, route, ticket_text)


async def dispatch_kitchen_ticket(
    route: str,
    item_ticket: dict[str, Any],
    *,
    order_type: str = "dine_in",
    customer_name: str | None = None,
    db: Session | None = None,
) -> None:
    """Dispatch one kitchen ticket to the configured backend for `route`."""
    ticket_text = build_ticket_text(
        route=route,
        item_name=str(item_ticket.get("item_name") or ""),
        quantity=int(item_ticket.get("quantity") or 1),
        note=item_ticket.get("note"),
        table_number=item_ticket.get("table_number"),
        order_id=int(item_ticket.get("order_id") or 0),
        created_at=str(item_ticket.get("date") or ""),
        order_type=order_type,
        customer_name=customer_name,
    )
    await _dispatch_payload(route=route, ticket_text=ticket_text, db=db)


async def dispatch_cashier_receipt(
    *,
    order_id: int,
    served_by: str | None,
    location_label: str,
    items: list[dict[str, Any]],
    subtotal: float,
    discount_amount: float,
    tax_amount: float,
    grand_total: float,
    payment_method: str | None,
    amount_tendered: float | None = None,
    change_amount: float | None = None,
    created_at: str | None = None,
    db: Session | None = None,
) -> None:
    """Dispatch one cashier receipt to the `cashier` printer endpoint."""
    receipt_text = build_receipt_text(
        order_id=order_id,
        served_by=served_by,
        location_label=location_label,
        items=items,
        subtotal=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        grand_total=grand_total,
        payment_method=payment_method,
        amount_tendered=amount_tendered,
        change_amount=change_amount,
        created_at=created_at,
    )
    await _dispatch_payload(route=CASHIER_PRINTER_ROUTE, ticket_text=receipt_text, db=db)
