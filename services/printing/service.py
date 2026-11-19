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
from services.printing.config import (
    CASHIER_PRINTER_ROUTE,
    ROLE_TO_LEGACY_ROUTE,
    PrinterEndpoint,
)
from services.printing.image_renderer import render_ticket_image
from services.printing.print_log import ensure_print_file_logging
from services.printing.print_queue import file_key, get_print_queue, lan_key, windows_key
from services.printing.receipt import build_receipt_text, shop_name
from services.printing.routes import category_route_to_printer_role
from services.printing.settings import (
    load_printer_config,
    load_receipt_texts,
    resolve_cashier_printer_endpoint,
    resolve_cashier_windows_printer_name,
    resolve_printer_endpoint_for_role,
)
from services.printing.ticket import (
    build_batch_ticket_text,
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
    kitchen_file_fallback = False
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
                kitchen_file_fallback = True
                logger.error(
                    "windows_printer backend: no LAN host for kitchen/bar route=%s; "
                    "refusing silent success — will write file backup then signal failure",
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

    # Always archive cashier receipt text to cashier_printer_output.txt, even when
    # Windows/LAN also prints (kitchen file backend already writes food/drinks txt).
    cashier_text_archived = False
    if route == CASHIER_PRINTER_ROUTE:
        await asyncio.to_thread(send_file_ticket, config, route, ticket_text)
        cashier_text_archived = True
        logger.info("Cashier receipt text archived to file route=%s", route)

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
        if kitchen_file_fallback:
            raise RuntimeError(
                f"Kitchen route '{route}' has no LAN host under windows_printer; "
                "ticket saved to file only (not sent to kitchen printer). "
                "Set host:port on the kitchen/bar Printer in Admin."
            )
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
    if not cashier_text_archived:
        await asyncio.to_thread(send_file_ticket, config, route, ticket_text)
        logger.info("File text print wrote route=%s", route)
    else:
        logger.info("File text print wrote route=%s (archive already written)", route)
    if kitchen_file_fallback:
        raise RuntimeError(
            f"Kitchen route '{route}' has no LAN host under windows_printer; "
            "ticket saved to file only (not sent to kitchen printer). "
            "Set host:port on the kitchen/bar Printer in Admin."
        )


async def dispatch_kitchen_ticket(
    route: str,
    item_ticket: dict[str, Any],
    *,
    order_type: str = "dine_in",
    customer_name: str | None = None,
    db: Session | None = None,
) -> None:
    """Dispatch a kitchen ticket.

    Preferred payload (one slip per line; modifiers under that line):
      ``{ item_name, quantity, note?, selected_modifiers?, is_takeaway?,
          table_number, order_id, date }``

    Optional combined multi-item payload still accepted (tests / tools):
      ``{ items: [{item_name, quantity, note?, selected_modifiers?}, ...],
          table_number, order_id, date, batch_number? }``
    """
    items = item_ticket.get("items")
    if isinstance(items, list) and items:
        ticket_text = build_batch_ticket_text(
            route=route,
            items=items,
            table_number=item_ticket.get("table_number"),
            order_id=int(item_ticket.get("order_id") or 0),
            created_at=str(item_ticket.get("date") or ""),
            order_type=order_type,
            customer_name=customer_name,
            batch_number=(
                int(item_ticket["batch_number"])
                if item_ticket.get("batch_number") is not None
                else None
            ),
            copy_number=item_ticket.get("copy_number"),
            copy_total=item_ticket.get("copy_total"),
        )
    else:
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
            selected_modifiers=item_ticket.get("selected_modifiers") or [],
            is_takeaway=bool(item_ticket.get("is_takeaway")),
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
    kpay_amount: float | None = None,
    mmqr_amount: float | None = None,
    voucher_no: str | None = None,
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
        kpay_amount=kpay_amount,
        mmqr_amount=mmqr_amount,
        mobile_money_amount=mobile_money_amount,
        created_at=created_at,
        voucher_no=voucher_no,
        # Read at print time: a re-print / retry shows the current texts.
        texts=load_receipt_texts(db),
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
                # Selected cashier row may have no LAN host (common for file
                # backend / printer-not-plugged-in testing). Only fail hard when
                # the row is missing, or network backend needs a host.
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
                if config.backend == "escpos_network":
                    raise RuntimeError(
                        f"Cashier printer id={printer_id} has no host:port "
                        "(required for escpos_network)"
                    )
    await _dispatch_payload(
        route=CASHIER_PRINTER_ROUTE,
        ticket_text=receipt_text,
        db=db,
        endpoint_override=endpoint_override,
        windows_printer_name=windows_name,
    )


def _test_print_route_for_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized in ROLE_TO_LEGACY_ROUTE:
        return ROLE_TO_LEGACY_ROUTE[normalized]
    return "other" if normalized == "other" else "food"


def build_printer_test_ticket_text(
    *, printer_name: str, role: str, db: Session | None = None
) -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"{'=' * 32}\n"
        f"  TEST PRINT\n"
        f"  {load_receipt_texts(db).shop_name or shop_name()}\n"
        f"{'=' * 32}\n"
        f"Printer: {printer_name}\n"
        f"Role: {role}\n"
        f"Time: {now}\n"
        f"{'=' * 32}\n"
    )


async def dispatch_printer_test(*, printer_id: int, db: Session) -> dict[str, Any]:
    """Send a short test slip to the named printer row. Raises on failure."""
    from models import Printer

    row = db.query(Printer).filter(Printer.id == printer_id).first()
    if row is None:
        raise LookupError(f"Printer id={printer_id} not found")

    config = load_printer_config(db)
    role = (row.role or "").strip().lower()
    route = _test_print_route_for_role(role)
    ticket_text = build_printer_test_ticket_text(printer_name=row.name, role=role, db=db)

    windows_name: str | None = None
    endpoint_override: PrinterEndpoint | None = None
    host = (row.host or "").strip()

    if role == "cashier" and config.backend == "windows_printer":
        windows_name = (row.windows_printer_name or "").strip() or None
        if not windows_name:
            raise RuntimeError(
                f"Cashier printer '{row.name}' has no Windows queue name — "
                "set it in Admin before Print Test"
            )
        target = f"windows_queue={windows_name}"
        queue_key = windows_key(windows_name)
    elif config.backend == "file":
        # File mode never sends to LAN/Windows even if host/queue fields are filled.
        target = "file"
        queue_key = file_key(route)
    elif host:
        endpoint_override = PrinterEndpoint(host=host, port=int(row.port or 9100))
        target = f"lan={endpoint_override.host}:{endpoint_override.port}"
        queue_key = lan_key(endpoint_override.host, endpoint_override.port)
    elif config.backend == "escpos_network":
        raise RuntimeError(
            f"Printer '{row.name}' has no host:port (required for LAN print mode)"
        )
    else:
        # windows_printer + kitchen/bar/other row without a host. Refuse here:
        # falling through would print on another row's (or the .env) LAN host
        # for the same route and still report this row as the target.
        raise RuntimeError(
            f"Printer '{row.name}' ({role}) has no LAN host:port. Under Windows "
            "print mode only cashier printers use a Windows queue; kitchen/bar/"
            "other printers need IP:port."
        )

    # Same per-printer queue as live slips, so a test cannot collide with them.
    await get_print_queue().run(
        queue_key,
        lambda: _dispatch_payload(
            route=route,
            ticket_text=ticket_text,
            db=db,
            endpoint_override=endpoint_override,
            windows_printer_name=windows_name,
        ),
    )
    return {
        "ok": True,
        "printer_id": int(row.id),
        "printer_name": row.name,
        "role": role,
        "backend": config.backend,
        "target": target,
        "message": f"Test print sent to {row.name} ({target})",
    }
