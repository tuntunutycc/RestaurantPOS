"""Startup repair: legacy dine-in table_id backfill without ghost tables."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models import Order, Table, Zone

logger = logging.getLogger(__name__)

# Accidental names from str(None) / str(null) during older backfill runs.
GHOST_TABLE_NAMES = frozenset({"none", "null"})


def _is_takeaway_order(order: Order) -> bool:
    return (getattr(order, "order_type", None) or "dine_in").strip().lower() == "takeaway"


def _table_label_from_legacy_order(order: Order) -> str | None:
    """Return a usable table label, or None when backfill must be skipped."""
    raw = getattr(order, "table_number", None)
    if raw is None:
        return None
    label = str(raw).strip()
    if not label or label.lower() in GHOST_TABLE_NAMES:
        return None
    return label


def ensure_default_zone(db: Session) -> Zone:
    default_zone = db.query(Zone).filter(Zone.name == "Main").first()
    if not default_zone:
        default_zone = Zone(name="Main")
        db.add(default_zone)
        db.commit()
        db.refresh(default_zone)
    return default_zone


def remove_ghost_none_tables(db: Session) -> int:
    """Unlink orders from and delete tables literally named None/null."""
    ghosts = (
        db.query(Table)
        .filter(Table.name.in_(("None", "none", "Null", "null", "NULL")))
        .all()
    )
    removed = 0
    for ghost in ghosts:
        linked = db.query(Order).filter(Order.table_id == ghost.id).all()
        for order in linked:
            # Restore intentional null table_id (takeaways / broken links).
            order.table_id = None
        db.delete(ghost)
        removed += 1
        logger.warning("Removed ghost table id=%s name=%r", ghost.id, ghost.name)
    if removed:
        db.commit()
    return removed


def backfill_legacy_dine_in_table_links(db: Session, default_zone: Zone | None = None) -> int:
    """
    For legacy dine-in rows with table_id NULL but a real table_number, ensure a
    Table exists and set table_id.

    Never create tables for walk-in takeaways or when table_number is NULL
    (that previously produced a table named \"None\").
    """
    zone = default_zone or ensure_default_zone(db)
    legacy_orders = (
        db.query(Order)
        .filter(Order.table_id.is_(None), Order.table_number.isnot(None))
        .all()
    )
    created_or_linked = 0
    for legacy_order in legacy_orders:
        if _is_takeaway_order(legacy_order):
            continue
        name_or_number = _table_label_from_legacy_order(legacy_order)
        if not name_or_number:
            continue
        table = db.query(Table).filter(Table.name == name_or_number).first()
        if not table:
            table = Table(
                name=name_or_number,
                zone_id=zone.id,
                status=(
                    "occupied"
                    if legacy_order.status in ("open", "dining", "pending", "completed")
                    else "available"
                ),
            )
            db.add(table)
            db.flush()
        legacy_order.table_id = table.id
        created_or_linked += 1
    if created_or_linked:
        db.commit()
    return created_or_linked


def repair_legacy_table_links(db: Session) -> None:
    """Run ghost cleanup + safe dine-in backfill (idempotent)."""
    ensure_default_zone(db)
    remove_ghost_none_tables(db)
    backfill_legacy_dine_in_table_links(db)
