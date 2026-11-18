#!/usr/bin/env python3
"""
Clear sales only. Staff, menu, tables and printers are kept.

Deletes: orders, order lines, print jobs. Every table becomes "available".
Keeps:   users and sessions, menu items and categories, zones and tables,
         printers and print settings, predefined instructions, admin audit log.

Usage (stop the server first):
  python scripts/clear_sales.py          # only shows what would be deleted
  python scripts/clear_sales.py --yes    # backs up the SQLite file, then deletes

With --yes a SQLite database is first copied next to itself as
<name>.backup-YYYYmmdd-HHMMSS. Other databases have no automatic backup and
need --no-backup to confirm you made your own.

See specs/feature-payment-kpay-mmqr (FR-KM7).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Allow `python scripts/clear_sales.py` without setting PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, inspect, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from models import Order, OrderItem, PrintJob, Table, TableStatus  # noqa: E402

# Children first, so foreign keys never point at a deleted row.
SALES_MODELS = (PrintJob, OrderItem, Order)


def _existing_tables(db: Session) -> set[str]:
    return set(inspect(db.get_bind()).get_table_names())


def count_sales(db: Session) -> dict[str, int]:
    """Rows this script would delete, per table, plus tables that would be freed."""
    existing = _existing_tables(db)
    counts: dict[str, int] = {}
    for model in SALES_MODELS:
        name = model.__tablename__
        counts[name] = (
            int(db.execute(select(func.count()).select_from(model.__table__)).scalar() or 0)
            if name in existing
            else 0
        )
    counts["tables_to_free"] = (
        int(
            db.execute(
                select(func.count())
                .select_from(Table.__table__)
                .where(Table.status != TableStatus.available)
            ).scalar()
            or 0
        )
        if Table.__tablename__ in existing
        else 0
    )
    return counts


def clear_sales(db: Session) -> dict[str, int]:
    """Delete all sales in one transaction. Returns what was deleted."""
    existing = _existing_tables(db)
    deleted = count_sales(db)
    try:
        for model in SALES_MODELS:
            if model.__tablename__ in existing:
                db.execute(model.__table__.delete())
        if Table.__tablename__ in existing:
            db.execute(Table.__table__.update().values(status=TableStatus.available))
        # Only present when a table was created with AUTOINCREMENT; without it
        # SQLite already restarts numbering once the table is empty.
        if "sqlite_sequence" in existing:
            for model in SALES_MODELS:
                db.execute(
                    text("DELETE FROM sqlite_sequence WHERE name = :name"),
                    {"name": model.__tablename__},
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    # Rows were deleted with bulk statements; drop any stale objects the session still holds.
    db.expunge_all()
    return deleted


def sqlite_file(database_url: str) -> Path | None:
    """The SQLite database file a URL points at (relative paths use the current folder)."""
    if not database_url.startswith("sqlite"):
        return None
    raw = database_url.split("///", 1)[1] if "///" in database_url else ""
    if not raw or raw == ":memory:":
        return None
    return Path(raw).resolve()


def backup_sqlite(database_url: str, *, now: datetime | None = None) -> Path | None:
    """Copy a SQLite database file next to itself. None when not a SQLite file."""
    source = sqlite_file(database_url)
    if source is None:
        return None
    if not source.is_file():
        raise FileNotFoundError(f"Database file not found: {source}")
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = source.with_name(f"{source.name}.backup-{stamp}")
    if target.exists():
        raise FileExistsError(f"Backup already exists: {target}")
    # sqlite3's backup API copies a consistent snapshot even if the file is in use.
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def _print_counts(counts: dict[str, int]) -> None:
    print(f"  orders:        {counts['orders']}")
    print(f"  order lines:   {counts['order_items']}")
    print(f"  print jobs:    {counts['print_jobs']}")
    print(f"  tables to set available: {counts['tables_to_free']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clear sales; keep staff, menu, tables and printers.")
    parser.add_argument("--yes", action="store_true", help="Actually delete (default: only show counts).")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the automatic backup (required for non-SQLite databases).",
    )
    args = parser.parse_args(argv)

    from database import DATABASE_URL, SessionLocal

    # Connecting to a SQLite file that is not there creates an empty one, and the
    # script would then report "0 orders". A relative DATABASE_URL (the default
    # `./pos.db`) depends on the folder the command is run from.
    database_file = sqlite_file(DATABASE_URL)
    if database_file is not None and not database_file.is_file():
        print(
            f"Database file not found: {database_file}\n"
            "Run this from the project folder (where pos.db is), or set DATABASE_URL.",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        counts = count_sales(db)
        print(f"Database: {database_file or DATABASE_URL}")
        if not args.yes:
            print("Would delete (nothing changed; run again with --yes to delete):")
            _print_counts(counts)
            print("Kept: staff, menu, zones/tables, printers and settings.")
            return 0

        if not args.no_backup:
            try:
                backup = backup_sqlite(DATABASE_URL)
            except (OSError, sqlite3.Error) as exc:
                print(f"Backup failed, nothing deleted: {exc}", file=sys.stderr)
                return 1
            if backup is None:
                print(
                    "This is not a SQLite file, so no automatic backup can be made.\n"
                    "Make your own backup, then run again with --yes --no-backup.",
                    file=sys.stderr,
                )
                return 1
            print(f"Backup written: {backup}")

        deleted = clear_sales(db)
        print("Deleted:")
        _print_counts(deleted)
        print("Kept: staff, menu, zones/tables, printers and settings.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
