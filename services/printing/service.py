"""Kitchen ticket and cashier receipt dispatch service."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from services.printing.backends.escpos_network import (
    CASHIER_SOCKET_TIMEOUT_SECONDS,
    print_image_to_network,
    send_network_ticket,
)
from services.printing.backends.escpos_windows import send_raw_to_windows_printer
from services.printing.backends.file import send_file_ticket, send_file_ticket_image
from services.printing.config import CASHIER_PRINTER_ROUTE, PrinterEndpoint
from services.printing.image_renderer import render_ticket_image
from services.printing.print_log import ensure_print_file_logging
from services.printing.receipt import build_receipt_text
from services.printing.routes import category_route_to_printer_role
from services.printing.settings import (
    load_printer_config,
    resolve_cashier_printer_endpoint,
    resolve_cashier_windows_printer_name,
    resolve_printer_endpoint_for_role,
)
from services.printing.ticket import (
    build_escpos_raster_payload,
    build_escpos_text_payload,
    build_ticket_text,
)

logger = logging.getLogger(__name__)


def _has_network_endpoint(
    *,
    route: str,
    config_routes: dict[str, PrinterEndpoint],
    endpoint_override: PrinterEndpoint | None,
) -> bool:
    if endpoint_override is not None and (endpoint_override.host or "").strip():
        return True
    endpoint = config_routes.get(route)
    return bool(endpoint and (endpoint.host or "").strip())


async def _dispatch_payload(
    *,
    route: str,
    ticket_text: str,
    db: Session | None = None,
    endpoint_override: PrinterEndpoint | None = None,
    windows_printer_name: str | None = None,
) -> None:
    log_path = ensure_print_file_logging()
    config = load_printer_config(db)
    if endpoint_override is not None:
        config = replace(
            config,
            routes={**config.routes, route: endpoint_override},
        )

    use_windows = (
        config.backend == "windows_printer" and route == CASHIER_PRINTER_ROUTE
    )
    # windows_printer is cashier-only. Kitchen/bar keep LAN when a host is configured
    # so enabling USB receipts does not silently disable IP kitchen printers.
    use_network = False
    if not use_windows:
        if config.backend == "escpos_network":
            use_network = True
        elif config.backend == "windows_printer":
            use_network = _has_network_endpoint(
                route=route,
                config_routes=config.routes,
                endpoint_override=endpoint_override,
            )
            if use_network:
                logger.info(
                    "windows_printer backend: using LAN for kitchen/bar route=%s",
                    route,
                )
            else:
                logger.warning(
                    "windows_printer backend: no LAN host for route=%s; "
                    "falling back to file",
                    route,
                )

    target = "file"
    if use_windows:
        target = f"windows_queue={(windows_printer_name or '').strip() or '(missing)'}"
    elif use_network:
        endpoint = endpoint_override or config.routes.get(route)
        if endpoint is not None:
            target = f"lan={endpoint.host}:{endpoint.port}"
        else:
            target = "lan=(missing endpoint)"

    logger.info(
        "Print dispatch route=%s backend=%s render_mode=%s target=%s log_file=%s",
        route,
        config.backend,
        config.render_mode,
        target,
        log_path,
    )
    logger.info(
        "Print diagnostics: font_path_override=%s paper_width_px=%s "
        "myanmar_hint=%s",
        config.font_path or "(auto: Pyidaungsu then Noto under assets/fonts)",
        config.paper_width_px,
        (
            "image mode will load Myanmar font"
            if config.render_mode == "image"
            else "text mode skips Myanmar font — expect garbled Myanmar on many printers"
        ),
    )
    if config.backend == "windows_printer" and route == CASHIER_PRINTER_ROUTE:
        if config.render_mode != "image":
            logger.warning(
                "Cashier Windows print is using render_mode=%s. "
                "Myanmar text usually needs render_mode=image. "
                "Notepad can look correct while app text-mode RAW looks wrong.",
                config.render_mode,
            )
        if not (windows_printer_name or "").strip():
            logger.error(
                "Cashier Windows print aborted: windows_printer_name is empty "
                "(set it on the cashier Printer in Admin)"
            )

    if config.render_mode == "image":
        image = render_ticket_image(
            ticket_text,
            paper_width_px=config.paper_width_px,
            font_path=config.font_path,
        )
        escpos_payload = build_escpos_raster_payload(image)
        logger.info(
            "Print image rendered route=%s size_px=%sx%s payload_bytes=%s",
            route,
            image.size[0],
            image.size[1],
            len(escpos_payload),
        )
        if use_windows:
            queue = (windows_printer_name or "").strip()
            if not queue:
                raise RuntimeError(
                    "Cashier Windows printer queue name is not configured"
                )
            try:
                await asyncio.to_thread(send_raw_to_windows_printer, queue, escpos_payload)
                logger.info("Windows RAW print succeeded route=%s queue=%s", route, queue)
            except Exception:
                logger.exception(
                    "Windows RAW print failed route=%s queue=%s", route, queue
                )
                raise
            return
        if use_network:
            try:
                if endpoint_override is not None:
                    timeout = (
                        CASHIER_SOCKET_TIMEOUT_SECONDS
                        if route == CASHIER_PRINTER_ROUTE
                        else 5.0
                    )
                    await asyncio.to_thread(
                        print_image_to_network,
                        endpoint_override,
                        escpos_payload,
                        timeout_seconds=timeout,
                        route_label=route,
                    )
                else:
                    await asyncio.to_thread(
                        send_network_ticket, config, route, escpos_payload
                    )
                logger.info("LAN print succeeded route=%s target=%s", route, target)
            except Exception:
                logger.exception("LAN print failed route=%s target=%s", route, target)
                raise
            return
        await asyncio.to_thread(send_file_ticket_image, config, route, image)
        logger.info("File image print wrote route=%s", route)
        return

    escpos_payload = build_escpos_text_payload(ticket_text)
    logger.info(
        "Print text payload route=%s bytes=%s (Myanmar may look wrong without image mode)",
        route,
        len(escpos_payload),
    )
    if use_windows:
        queue = (windows_printer_name or "").strip()
        if not queue:
            raise RuntimeError(
                "Cashier Windows printer queue name is not configured"
            )
        try:
            await asyncio.to_thread(send_raw_to_windows_printer, queue, escpos_payload)
            logger.info("Windows RAW print succeeded route=%s queue=%s", route, queue)
        except Exception:
            logger.exception("Windows RAW print failed route=%s queue=%s", route, queue)
            raise
        return
    if use_network:
        try:
            if endpoint_override is not None:
                timeout = (
                    CASHIER_SOCKET_TIMEOUT_SECONDS
                    if route == CASHIER_PRINTER_ROUTE
                    else 5.0
                )
                await asyncio.to_thread(
                    print_image_to_network,
                    endpoint_override,
                    escpos_payload,
                    timeout_seconds=timeout,
                    route_label=route,
                )
            else:
                await asyncio.to_thread(send_network_ticket, config, route, escpos_payload)
            logger.info("LAN print succeeded route=%s", route)
        except Exception:
            logger.exception("LAN print failed route=%s", route)
            raise
        return
    await asyncio.to_thread(send_file_ticket, config, route, ticket_text)
    logger.info("File text print wrote route=%s", route)


async def dispatch_kitchen_ticket(
    route: str,
    item_ticket: dict[str, Any],
    *,
    order_type: str = "dine_in",
    customer_name: str | None = None,
    db: Session | None = None,
) -> None:
    """Dispatch one kitchen ticket; `route` remains drinks|food for file labels."""
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
    endpoint_override: PrinterEndpoint | None = None
    if db is not None:
        role = category_route_to_printer_role(route)
        endpoint_override = resolve_printer_endpoint_for_role(db, role)
    await _dispatch_payload(
        route=route,
        ticket_text=ticket_text,
        db=db,
        endpoint_override=endpoint_override,
    )


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
    cash_amount: float | None = None,
    mobile_money_amount: float | None = None,
    created_at: str | None = None,
    cashier_name: str | None = None,
    printer_id: int | None = None,
    db: Session | None = None,
) -> None:
    """Dispatch one cashier receipt to the selected or default cashier printer."""
    receipt_text = build_receipt_text(
        order_id=order_id,
        served_by=served_by,
        cashier_name=cashier_name,
        location_label=location_label,
        items=items,
        subtotal=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        grand_total=grand_total,
        payment_method=payment_method,
        amount_tendered=amount_tendered,
        change_amount=change_amount,
        cash_amount=cash_amount,
        mobile_money_amount=mobile_money_amount,
        created_at=created_at,
    )
    endpoint_override: PrinterEndpoint | None = None
    windows_name: str | None = None
    if db is not None:
        config = load_printer_config(db)
        if config.backend == "windows_printer":
            windows_name = resolve_cashier_windows_printer_name(
                db, printer_id=printer_id
            )
            if printer_id is not None and windows_name is None:
                # Explicit id was requested but queue missing / inactive.
                from models import Printer

                selected = (
                    db.query(Printer)
                    .filter(
                        Printer.id == printer_id,
                        Printer.role == "cashier",
                        Printer.is_active.is_(True),
                    )
                    .first()
                )
                if selected is None:
                    raise RuntimeError(
                        f"Cashier printer id={printer_id} not found or inactive"
                    )
                raise RuntimeError(
                    f"Cashier printer id={printer_id} has no windows_printer_name"
                )
        else:
            endpoint_override = resolve_cashier_printer_endpoint(
                db, printer_id=printer_id
            )
            if printer_id is not None and endpoint_override is None:
                raise RuntimeError(
                    f"Cashier printer id={printer_id} not found or inactive"
                )
    await _dispatch_payload(
        route=CASHIER_PRINTER_ROUTE,
        ticket_text=receipt_text,
        db=db,
        endpoint_override=endpoint_override,
        windows_printer_name=windows_name,
    )
