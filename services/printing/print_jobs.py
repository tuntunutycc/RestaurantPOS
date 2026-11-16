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
from sqlalchemy.orm import Session

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
    attempted = error is None
    if attempted:
        payload = job.payload if isinstance(job.payload, dict) else {}
        try:
            if job.kind == KIND_KITCHEN:
                await dispatch_kitchen_ticket(
                    job.route,
                    payload.get("ticket") or {},
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
    return query.order_by(PrintJob.id.desc()).limit(FAILED_LIST_LIMIT).all()
