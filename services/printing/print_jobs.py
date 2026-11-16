"""Stored print jobs: create, queue, send, retry.

One ``PrintJob`` row per slip. Sending goes through the existing
``dispatch_kitchen_ticket`` / ``dispatch_cashier_receipt`` so rendering and
printer backends are unchanged; this module only adds ordering (the per-printer
queue) and a durable result (``print_status`` / ``error_message``).

Spec: specs/feature-print-queue/requirements.md
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, object_session

from models import Order, OrderItem, PrintJob
from services.printing.config import CASHIER_PRINTER_ROUTE
from services.printing.print_log import get_print_logger
from services.printing.print_queue import (
    file_key,
    get_print_queue,
    lan_key,
    unresolved_key,
    windows_key,
)
from services.printing.routes import category_route_to_printer_role
from services.printing.service import dispatch_cashier_receipt, dispatch_kitchen_ticket
from services.printing.settings import (
    load_printer_config,
    resolve_cashier_printer_endpoint,
    resolve_cashier_windows_printer_name,
    resolve_printer_endpoint_for_role,
)

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PRINTED = "printed"
STATUS_FAILED = "failed"

KIND_KITCHEN = "kitchen"
KIND_RECEIPT = "receipt"

PRINT_JOB_EVENT = "print_job_updated"
INTERRUPTED_MESSAGE = "Server restarted before this slip was printed"
SKIPPED_PREFIX = "Skipped:"
ALL_ITEMS_CANCELLED_MESSAGE = f"{SKIPPED_PREFIX} all items were cancelled"
SLIP_MODE_COMBINED = "combined"
COMBINED_LABEL_ITEMS = 3
ERROR_MESSAGE_MAX = 1000
FAILED_LIST_LIMIT = 200

Notifier = Callable[[str, dict], Awaitable[None]]

_notifier: Notifier | None = None
_session_factory: Callable[[], Session] | None = None


def configure(
    *,
    notifier: Notifier | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> None:
    """Set the WebSocket broadcaster and the session factory used by workers."""
    global _notifier, _session_factory
    _notifier = notifier
    _session_factory = session_factory


def _new_session() -> Session:
    if _session_factory is not None:
        return _session_factory()
    from database import SessionLocal

    return SessionLocal()


# —— Creating jobs ——


def create_kitchen_job(
    db: Session,
    *,
    order_id: int,
    order_item_id: int | None,
    route: str,
    ticket: dict[str, Any],
    order_type: str,
    customer_name: str | None,
) -> PrintJob:
    """Add (not commit) one pending kitchen slip. ``ticket`` is the dispatch payload."""
    job = PrintJob(
        order_id=order_id,
        order_item_id=order_item_id,
        kind=KIND_KITCHEN,
        route=route,
        payload={
            "ticket": ticket,
            "order_type": order_type,
            "customer_name": customer_name,
        },
        print_status=STATUS_PENDING,
    )
    db.add(job)
    return job


def create_kitchen_jobs_for_batch(
    db: Session,
    *,
    slip_mode: str,
    order_id: int,
    lines: list[tuple[str, dict[str, Any], int]],
    table_number: Any,
    date: str,
    batch_number: int | None,
    order_type: str,
    customer_name: str | None,
    copies: int = 1,
) -> list[PrintJob]:
    """Add (not commit) the kitchen slips of one submit.

    ``lines``: (printer route, item payload, order line id) in submission order.
    ``per_item`` → one slip per line. ``combined`` → one slip per printer route
    listing that route's lines, printed ``copies`` times; each copy is its own
    job so a failed copy is retried alone (specs/feature-kitchen-slip-mode).
    """
    meta = {"table_number": table_number, "order_id": order_id, "date": date}
    if slip_mode != SLIP_MODE_COMBINED:
        return [
            create_kitchen_job(
                db,
                order_id=order_id,
                order_item_id=line_id,
                route=route,
                ticket={**item, **meta},
                order_type=order_type,
                customer_name=customer_name,
            )
            for route, item, line_id in lines
        ]

    by_route: dict[str, list[dict[str, Any]]] = {}
    for route, item, line_id in lines:
        by_route.setdefault(route, []).append({**item, "order_item_id": line_id})
    copy_total = max(int(copies or 1), 1)
    jobs: list[PrintJob] = []
    for route, items in by_route.items():
        for copy_number in range(1, copy_total + 1):
            ticket: dict[str, Any] = {"items": items, **meta, "batch_number": batch_number}
            if copy_total > 1:
                ticket["copy_number"] = copy_number
                ticket["copy_total"] = copy_total
            jobs.append(
                create_kitchen_job(
                    db,
                    order_id=order_id,
                    order_item_id=None,
                    route=route,
                    ticket=ticket,
                    order_type=order_type,
                    customer_name=customer_name,
                )
            )
    return jobs


def create_receipt_job(
    db: Session,
    *,
    order_id: int,
    printer_id: int | None,
    receipt: dict[str, Any],
) -> PrintJob:
    """Add (not commit) one pending receipt. ``receipt`` = dispatch_cashier_receipt kwargs."""
    job = PrintJob(
        order_id=order_id,
        order_item_id=None,
        kind=KIND_RECEIPT,
        route=CASHIER_PRINTER_ROUTE,
        printer_id=printer_id,
        payload=receipt,
        print_status=STATUS_PENDING,
    )
    db.add(job)
    return job


# —— Combined slips (one slip, several order lines) ——


def _combined_items(job: PrintJob) -> list[dict[str, Any]] | None:
    """The lines of a combined kitchen slip, or None for any other job."""
    if job.kind != KIND_KITCHEN:
        return None
    payload = job.payload if isinstance(job.payload, dict) else {}
    ticket = payload.get("ticket")
    items = ticket.get("items") if isinstance(ticket, dict) else None
    if not isinstance(items, list) or not items:
        return None
    return [item for item in items if isinstance(item, dict)]


def _active_items(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop lines whose order line was cancelled or no longer exists."""
    line_ids = [
        int(item["order_item_id"]) for item in items if item.get("order_item_id") is not None
    ]
    if not line_ids:
        return list(items)
    rows = (
        db.query(OrderItem.id, OrderItem.item_status)
        .filter(OrderItem.id.in_(line_ids))
        .all()
    )
    active = {
        int(line_id)
        for line_id, status in rows
        if str(getattr(status, "value", status) or "").strip().lower() != "cancelled"
    }
    return [
        item
        for item in items
        if item.get("order_item_id") is None or int(item["order_item_id"]) in active
    ]


def _kitchen_ticket_to_send(db: Session, job: PrintJob) -> dict[str, Any] | None:
    """Ticket payload for dispatch; None when a combined slip has no line left."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    ticket = payload.get("ticket") if isinstance(payload.get("ticket"), dict) else {}
    items = _combined_items(job)
    if items is None:
        return ticket
    remaining = _active_items(db, items)
    if not remaining:
        return None
    return {**ticket, "items": remaining}


def _combined_label(items: list[dict[str, Any]]) -> str:
    shown = [
        f"{item.get('item_name') or 'Item'} x{int(item.get('quantity') or 1)}"
        for item in items[:COMBINED_LABEL_ITEMS]
    ]
    more = len(items) - len(shown)
    return ", ".join(shown) + (f" +{more} more" if more > 0 else "")


# —— Presentation ——


def job_to_dict(job: PrintJob) -> dict[str, Any]:
    """Fields of ``schemas.PrintJobResponse`` (also the WebSocket payload)."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    if job.kind == KIND_RECEIPT:
        item_label = "Receipt"
        location = payload.get("location_label")
        # The receipt stores the bare table name ("5"); kitchen slips say "Table 5".
        order_type = str(getattr(job.order, "order_type", "") or "").strip().lower()
        if location and order_type != "takeaway":
            text = str(location)
            location = text if text.lower().startswith("table") else f"Table {text}"
    else:
        ticket = payload.get("ticket") if isinstance(payload.get("ticket"), dict) else {}
        combined = _combined_items(job)
        if combined is not None:
            # Show what a reprint would contain: cancelled lines are left out.
            session = object_session(job)
            remaining = _active_items(session, combined) if session is not None else combined
            item_label = _combined_label(remaining or combined)
            copy_total = int(ticket.get("copy_total") or 1)
            if copy_total > 1:
                item_label += f" (copy {int(ticket.get('copy_number') or 1)}/{copy_total})"
        else:
            name = str(ticket.get("item_name") or "Kitchen slip")
            item_label = f"{name} x{int(ticket.get('quantity') or 1)}"
        table_number = ticket.get("table_number")
        if str(payload.get("order_type") or "").strip().lower() == "takeaway":
            location = payload.get("customer_name") or table_number or "Takeaway"
        else:
            location = f"Table {table_number}" if table_number is not None else None
    return {
        "id": job.id,
        "order_id": job.order_id,
        "order_item_id": job.order_item_id,
        "kind": job.kind,
        "route": job.route,
        "print_status": job.print_status,
        "error_message": job.error_message,
        "attempts": int(job.attempts or 0),
        "item_label": item_label,
        "location_label": str(location) if location is not None else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "printed_at": job.printed_at,
    }


def _event_payload(job: PrintJob) -> dict[str, Any]:
    data = job_to_dict(job)
    for field in ("created_at", "updated_at", "printed_at"):
        value = data[field]
        data[field] = value.isoformat() if value is not None else None
    return data


# —— Sending ——


def _skip_reason(db: Session, job: PrintJob) -> str | None:
    """Why a kitchen slip must not be printed any more, if so."""
    if job.kind != KIND_KITCHEN:
        return None
    order = db.get(Order, job.order_id)
    if order is None:
        return f"{SKIPPED_PREFIX} order no longer exists"
    if str(order.status or "").strip().lower() == "cancelled":
        return f"{SKIPPED_PREFIX} order was cancelled"
    if job.order_item_id is not None:
        item = db.get(OrderItem, job.order_item_id)
        if item is None:
            return f"{SKIPPED_PREFIX} order line no longer exists"
        status = getattr(item.item_status, "value", item.item_status)
        if str(status or "").strip().lower() == "cancelled":
            return f"{SKIPPED_PREFIX} item was cancelled"
    combined = _combined_items(job)
    if combined is not None and not _active_items(db, combined):
        return ALL_ITEMS_CANCELLED_MESSAGE
    return None


def print_target_key(db: Session, job: PrintJob) -> str:
    """Which printer's queue this job belongs to. Never raises."""
    route = job.route
    try:
        config = load_printer_config(db)
        if route == CASHIER_PRINTER_ROUTE:
            if config.backend == "windows_printer":
                name = resolve_cashier_windows_printer_name(db, printer_id=job.printer_id)
                return windows_key(name) if name else unresolved_key(route)
            endpoint = resolve_cashier_printer_endpoint(db, printer_id=job.printer_id)
        else:
            endpoint = resolve_printer_endpoint_for_role(
                db, category_route_to_printer_role(route)
            )
        if config.backend == "file":
            return file_key(route)
        endpoint = endpoint or config.routes.get(route)
        if endpoint is not None and (endpoint.host or "").strip():
            return lan_key(endpoint.host, endpoint.port)
    except Exception:
        logger.exception("Could not resolve print target job_id=%s route=%s", job.id, route)
    return unresolved_key(route)


async def execute_print_job(db: Session, job_id: int) -> dict[str, Any] | None:
    """Send one pending job and store the outcome. Returns the event payload.

    Never raises for a printer failure: that becomes ``print_status='failed'``.
    """
    job = db.get(PrintJob, job_id)
    if job is None or job.print_status != STATUS_PENDING:
        return None

    error = _skip_reason(db, job)
    ticket: dict[str, Any] | None = None
    if error is None and job.kind == KIND_KITCHEN:
        # A combined slip is sent without the lines cancelled since submit.
        ticket = _kitchen_ticket_to_send(db, job)
        if ticket is None:
            error = ALL_ITEMS_CANCELLED_MESSAGE
    attempted = error is None
    if attempted:
        payload = job.payload if isinstance(job.payload, dict) else {}
        try:
            if job.kind == KIND_KITCHEN:
                await dispatch_kitchen_ticket(
                    job.route,
                    ticket or {},
                    order_type=payload.get("order_type") or "dine_in",
                    customer_name=payload.get("customer_name"),
                    db=db,
                )
            else:
                await dispatch_cashier_receipt(
                    **payload, printer_id=job.printer_id, db=db
                )
        except Exception as exc:
            error = str(exc).strip() or exc.__class__.__name__
            # A DB error inside dispatch would leave the session unusable.
            db.rollback()

    job = db.get(PrintJob, job_id)
    if job is None:
        return None
    if attempted:
        job.attempts = int(job.attempts or 0) + 1
    if error is None:
        job.print_status = STATUS_PRINTED
        job.error_message = None
        job.printed_at = datetime.utcnow()
    else:
        job.print_status = STATUS_FAILED
        job.error_message = error[:ERROR_MESSAGE_MAX]
        get_print_logger().error(
            "Print job failed job_id=%s order_id=%s kind=%s route=%s attempts=%s: %s",
            job.id,
            job.order_id,
            job.kind,
            job.route,
            job.attempts,
            error,
        )
    db.commit()
    return _event_payload(job)


async def run_print_job(job_id: int, *, db: Session | None = None) -> None:
    """Queue entry point: send the job, then tell connected screens.

    Workers pass no session and get their own; the in-request fallback passes
    the request session.
    """
    session = db if db is not None else _new_session()
    event: dict[str, Any] | None = None
    try:
        event = await execute_print_job(session, job_id)
    except Exception:
        logger.exception("Print job crashed job_id=%s", job_id)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        if db is None:
            session.close()
    if event is not None and _notifier is not None:
        try:
            await _notifier(PRINT_JOB_EVENT, event)
        except Exception:
            logger.exception("Could not broadcast %s job_id=%s", PRINT_JOB_EVENT, job_id)


async def enqueue_print_jobs(db: Session, job_ids: list[int]) -> None:
    """Hand committed pending jobs to the per-printer queues.

    If the queue is not running, send them here one after another instead of
    dropping them.
    """
    queue = get_print_queue()
    if not queue.running:
        for job_id in job_ids:
            await run_print_job(job_id, db=db)
        return
    for job_id in job_ids:
        job = db.get(PrintJob, job_id)
        if job is None:
            continue
        queue.submit(print_target_key(db, job), partial(run_print_job, job_id))


# —— Retry / startup / listing ——


def requeue_failed_jobs(
    db: Session, order_id: int, *, include_receipts: bool
) -> tuple[list[int], int]:
    """Flip this order's failed jobs back to pending. Returns (requeued ids, skipped).

    The flip is conditional on the row still being ``failed``, so two retry
    requests cannot queue the same slip twice.
    """
    failed = (
        db.query(PrintJob)
        .filter(PrintJob.order_id == order_id, PrintJob.print_status == STATUS_FAILED)
        .order_by(PrintJob.id.asc())
        .all()
    )
    requeued: list[int] = []
    skipped = 0
    for job in failed:
        if job.kind == KIND_RECEIPT and not include_receipts:
            skipped += 1
            continue
        if _skip_reason(db, job) is not None:
            skipped += 1
            continue
        changed = (
            db.query(PrintJob)
            .filter(PrintJob.id == job.id, PrintJob.print_status == STATUS_FAILED)
            .update(
                {
                    PrintJob.print_status: STATUS_PENDING,
                    PrintJob.error_message: None,
                    PrintJob.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if changed:
            requeued.append(job.id)
    db.commit()
    return requeued, skipped


def mark_interrupted_jobs_failed(db: Session) -> int:
    """Startup: the in-memory queue is gone, so pending jobs will never be sent."""
    count = (
        db.query(PrintJob)
        .filter(PrintJob.print_status == STATUS_PENDING)
        .update(
            {
                PrintJob.print_status: STATUS_FAILED,
                PrintJob.error_message: INTERRUPTED_MESSAGE,
                PrintJob.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if count:
        logger.warning("Marked %s interrupted print job(s) as failed", count)
    return int(count or 0)


def list_order_jobs(db: Session, order_id: int) -> list[PrintJob]:
    return (
        db.query(PrintJob)
        .filter(PrintJob.order_id == order_id)
        .order_by(PrintJob.id.asc())
        .all()
    )


def list_failed_jobs(
    db: Session, *, hours: int, include_receipts: bool
) -> list[PrintJob]:
    """Recent failed slips that can still be retried (cancelled lines excluded)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = (
        db.query(PrintJob)
        .join(Order, Order.id == PrintJob.order_id)
        .outerjoin(OrderItem, OrderItem.id == PrintJob.order_item_id)
        .filter(
            PrintJob.print_status == STATUS_FAILED,
            PrintJob.created_at >= cutoff,
            or_(
                PrintJob.kind != KIND_KITCHEN,
                and_(
                    Order.status != "cancelled",
                    or_(
                        PrintJob.order_item_id.is_(None),
                        and_(
                            OrderItem.id.isnot(None),
                            OrderItem.item_status != "cancelled",
                        ),
                    ),
                ),
            ),
        )
    )
    if not include_receipts:
        query = query.filter(PrintJob.kind == KIND_KITCHEN)
    jobs = query.order_by(PrintJob.id.desc()).limit(FAILED_LIST_LIMIT).all()
    # A combined slip is tied to several lines; hide it once all are cancelled.
    visible: list[PrintJob] = []
    for job in jobs:
        combined = _combined_items(job)
        if combined is not None and not _active_items(db, combined):
            continue
        visible.append(job)
    return visible
