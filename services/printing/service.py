"""Kitchen ticket dispatch service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from services.printing.backends.escpos_network import send_network_ticket
from services.printing.backends.file import send_file_ticket, send_file_ticket_image
from services.printing.image_renderer import render_ticket_image
from services.printing.settings import load_printer_config
from services.printing.ticket import (
    build_escpos_raster_payload,
    build_escpos_text_payload,
    build_ticket_text,
)

logger = logging.getLogger(__name__)


async def dispatch_kitchen_ticket(
    route: str,
    item_ticket: dict[str, Any],
    *,
    order_type: str = "dine_in",
    customer_name: str | None = None,
) -> None:
    """Dispatch one kitchen ticket to the configured backend for `route`."""
    config = load_printer_config()
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
