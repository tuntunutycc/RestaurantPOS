"""scripts/clear_sales.py: delete sales only, keep staff / menu / tables / printers.

Spec: specs/feature-payment-kpay-mmqr (FR-KM7)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
from auth import hash_password
from models import (
    AdminAuditLog,
    Base,
    Category,
    KitchenPrinterSettings,
    MenuItem,
    Order,
    OrderItem,
    PredefinedInstruction,
    Printer,
    PrintJob,
    Table,
    TableStatus,
    User,
    UserSession,
    Zone,
)
from scripts import clear_sales as script

KEPT_MODELS = (
    User, UserSession, Category, MenuItem, Zone, Table, Printer,
    KitchenPrinterSettings, PredefinedInstruction, AdminAuditLog,
)


@pytest.fixture()
def shop(tmp_path):
    """A small shop in its own SQLite file: staff, menu, tables, printers and two orders."""
    db_path = tmp_path / "shop.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    admin = User(username="admin", role="admin", password_hash=hash_password("admin123"))
    cashier = User(username="cashier1", role="cashier", password_hash=hash_password("x"), pin_code="2222")
    zone = Zone(name="Main")
    db.add_all([admin, cashier, zone])
    db.flush()
    free_table = Table(name="T1", zone_id=zone.id, status=TableStatus.available)
    busy_table = Table(name="T2", zone_id=zone.id, status=TableStatus.occupied)
    category = Category(name="Food", printer_route="food")
    db.add_all([free_table, busy_table, category])
    db.flush()
    item = MenuItem(name="Mohinga", price=3500.0, category_id=category.id, is_available=True, modifiers_config=[])
    db.add_all(
        [
            item,
            Printer(name="Kitchen", host="192.168.1.50", port=9100, role="kitchen", is_active=True),
            KitchenPrinterSettings(id=1, backend="escpos_network", render_mode="image", paper_width_px=576),
            PredefinedInstruction(**_instruction_fields()),
            UserSession(**_session_fields(cashier.id)),
            AdminAuditLog(actor_user_id=admin.id, target_user_id=cashier.id, action="create_user"),
        ]
    )
    db.flush()
    paid = Order(
        table_id=free_table.id, order_type="dine_in", status="paid", total_amount=7000.0,
        payment_method="kpay", kpay_amount=7000.0, checked_out_by_id=cashier.id,
    )
    open_order = Order(table_id=busy_table.id, order_type="dine_in", status="open", total_amount=3500.0)
    db.add_all([paid, open_order])
    db.flush()
    lines = [
        OrderItem(order_id=paid.id, menu_item_id=item.id, quantity=2, subtotal=7000.0, selected_modifiers=[]),
        OrderItem(order_id=open_order.id, menu_item_id=item.id, quantity=1, subtotal=3500.0, selected_modifiers=[]),
    ]
    db.add_all(lines)
    db.flush()
    db.add_all(
        [
            PrintJob(order_id=paid.id, order_item_id=lines[0].id, kind="kitchen", route="food", payload={}, print_status="printed"),
            PrintJob(order_id=paid.id, kind="receipt", route="cashier", payload={}, print_status="failed"),
            PrintJob(order_id=open_order.id, order_item_id=lines[1].id, kind="kitchen", route="food", payload={}, print_status="pending"),
        ]
    )
    db.commit()
    try:
        yield {"db": db, "url": url, "path": db_path, "Session": Session, "item_id": item.id}
    finally:
        db.close()
        engine.dispose()


def _instruction_fields() -> dict:
    columns = {c.name for c in PredefinedInstruction.__table__.columns}
    fields = {"text": "No chilli", "label": "No chilli", "name": "No chilli"}
    return {key: value for key, value in fields.items() if key in columns}


def _session_fields(user_id: int) -> dict:
    columns = {c.name for c in UserSession.__table__.columns}
    fields = {
        "user_id": user_id, "jti": "jti-1", "device_id": "tablet-1",
        "expires_at": datetime(2030, 1, 1), "created_at": datetime(2026, 1, 1),
    }
    return {key: value for key, value in fields.items() if key in columns}


def _snapshot(db, models) -> dict[str, list[tuple]]:
    """Every row of the given tables, to prove nothing in them changed."""
    db.expire_all()
    return {
        model.__tablename__: [tuple(row) for row in db.execute(model.__table__.select().order_by(*model.__table__.primary_key.columns))]
        for model in models
    }


def _sales_rows(db) -> tuple[int, int, int]:
    db.expire_all()
    return db.query(Order).count(), db.query(OrderItem).count(), db.query(PrintJob).count()


def _use_shop_database(monkeypatch, shop, url: str | None = None):
    monkeypatch.setattr(database, "DATABASE_URL", url or shop["url"])
    monkeypatch.setattr(database, "SessionLocal", shop["Session"])


def test_count_reports_what_would_be_deleted_and_changes_nothing(shop):
    db = shop["db"]
    assert script.count_sales(db) == {"print_jobs": 3, "order_items": 2, "orders": 2, "tables_to_free": 1}
    assert _sales_rows(db) == (2, 2, 3)


def test_clear_deletes_sales_and_keeps_the_setup(shop):
    db = shop["db"]
    # Tables are compared apart: their status is meant to change.
    kept_models = tuple(model for model in KEPT_MODELS if model is not Table)
    before = _snapshot(db, kept_models)
    assert all(before[name] for name in before), "fixture must have a row in every kept table"

    deleted = script.clear_sales(db)

    assert deleted == {"print_jobs": 3, "order_items": 2, "orders": 2, "tables_to_free": 1}
    assert _sales_rows(db) == (0, 0, 0)
    assert _snapshot(db, kept_models) == before
    tables = db.query(Table).order_by(Table.id).all()
    assert [(t.name, t.status) for t in tables] == [("T1", TableStatus.available), ("T2", TableStatus.available)]
    assert script.count_sales(db) == {"print_jobs": 0, "order_items": 0, "orders": 0, "tables_to_free": 0}


def test_order_numbers_start_again_from_one(shop):
    db = shop["db"]
    script.clear_sales(db)
    order = Order(order_type="takeaway", status="open", total_amount=0.0)
    db.add(order)
    db.flush()
    line = OrderItem(order_id=order.id, menu_item_id=shop["item_id"], quantity=1, subtotal=0.0, selected_modifiers=[])
    db.add(line)
    db.commit()
    assert (order.id, line.id) == (1, 1)


def test_clearing_twice_is_harmless(shop):
    db = shop["db"]
    script.clear_sales(db)
    assert script.clear_sales(db) == {"print_jobs": 0, "order_items": 0, "orders": 0, "tables_to_free": 0}


def test_backup_is_a_full_copy_made_before_deleting(shop):
    backup = script.backup_sqlite(shop["url"], now=datetime(2026, 11, 18, 14, 30, 5))
    assert backup == shop["path"].with_name("shop.db.backup-20261118-143005")
    script.clear_sales(shop["db"])

    con = sqlite3.connect(backup)
    try:
        assert con.execute("SELECT COUNT(*) FROM orders").fetchone() == (2,)
        assert con.execute("SELECT COUNT(*) FROM order_items").fetchone() == (2,)
        assert con.execute("SELECT kpay_amount FROM orders WHERE status = 'paid'").fetchone() == (7000.0,)
    finally:
        con.close()


def test_backup_never_overwrites_an_existing_backup(shop):
    now = datetime(2026, 11, 18, 14, 30, 5)
    first = script.backup_sqlite(shop["url"], now=now)
    size = first.stat().st_size
    with pytest.raises(FileExistsError):
        script.backup_sqlite(shop["url"], now=now)
    assert first.stat().st_size == size


def test_backup_of_a_missing_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        script.backup_sqlite(f"sqlite:///{tmp_path / 'nope.db'}")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("url", ["postgresql://user:pw@host/pos", "sqlite://", "sqlite:///:memory:"])
def test_backup_is_not_possible_for_other_databases(url):
    assert script.backup_sqlite(url) is None


def test_command_without_yes_only_shows_counts(shop, monkeypatch, capsys):
    _use_shop_database(monkeypatch, shop)
    assert script.main([]) == 0
    out = capsys.readouterr().out
    assert "nothing changed" in out and "orders:        2" in out
    assert _sales_rows(shop["db"]) == (2, 2, 3)
    assert [p.name for p in shop["path"].parent.iterdir()] == ["shop.db"]


def test_command_with_yes_backs_up_then_deletes(shop, monkeypatch, capsys):
    _use_shop_database(monkeypatch, shop)
    assert script.main(["--yes"]) == 0
    out = capsys.readouterr().out
    assert "Backup written:" in out and "Deleted:" in out
    assert _sales_rows(shop["db"]) == (0, 0, 0)

    (backup,) = [p for p in shop["path"].parent.iterdir() if ".backup-" in p.name]
    con = sqlite3.connect(backup)
    try:
        assert con.execute("SELECT COUNT(*) FROM orders").fetchone() == (2,)
    finally:
        con.close()
    assert shop["db"].query(User).count() == 2
    assert shop["db"].query(MenuItem).count() == 1


def test_command_refuses_when_it_cannot_back_up(shop, monkeypatch, capsys):
    _use_shop_database(monkeypatch, shop, url="postgresql://user:pw@host/pos")
    assert script.main(["--yes"]) == 1
    assert "no automatic backup" in capsys.readouterr().err
    assert _sales_rows(shop["db"]) == (2, 2, 3)


def test_command_refuses_when_the_backup_fails(shop, monkeypatch, capsys):
    _use_shop_database(monkeypatch, shop)

    def disk_full(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(script, "backup_sqlite", disk_full)
    assert script.main(["--yes"]) == 1
    assert "nothing deleted" in capsys.readouterr().err
    assert _sales_rows(shop["db"]) == (2, 2, 3)


def test_command_with_no_backup_deletes_without_a_copy(shop, monkeypatch):
    _use_shop_database(monkeypatch, shop, url="postgresql://user:pw@host/pos")
    assert script.main(["--yes", "--no-backup"]) == 0
    assert _sales_rows(shop["db"]) == (0, 0, 0)
    assert [p.name for p in shop["path"].parent.iterdir()] == ["shop.db"]


def test_a_failure_part_way_deletes_nothing(shop, monkeypatch):
    db = shop["db"]
    real_execute = db.execute

    def fail_on_table_update(statement, *args, **kwargs):
        if str(statement).lstrip().upper().startswith("UPDATE TABLES"):
            raise RuntimeError("disk full")
        return real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", fail_on_table_update)
    with pytest.raises(RuntimeError):
        script.clear_sales(db)
    monkeypatch.undo()
    assert _sales_rows(db) == (2, 2, 3)
    assert db.query(Table).filter(Table.status == TableStatus.occupied).count() == 1


def test_command_stops_when_the_database_file_is_missing_and_creates_nothing(shop, monkeypatch, capsys):
    """A wrong working folder must not create an empty pos.db and report "0 orders"."""
    missing = shop["path"].parent / "elsewhere" / "pos.db"
    missing.parent.mkdir()
    _use_shop_database(monkeypatch, shop, url=f"sqlite:///{missing}")
    for argv in ([], ["--yes"], ["--yes", "--no-backup"]):
        assert script.main(argv) == 1
        assert "Database file not found" in capsys.readouterr().err
    assert list(missing.parent.iterdir()) == []
    assert _sales_rows(shop["db"]) == (2, 2, 3)


def test_relative_database_path_is_shown_in_full(shop, monkeypatch, capsys):
    monkeypatch.chdir(shop["path"].parent)
    _use_shop_database(monkeypatch, shop, url="sqlite:///./shop.db")
    assert script.main([]) == 0
    assert f"Database: {shop['path'].resolve()}" in capsys.readouterr().out
