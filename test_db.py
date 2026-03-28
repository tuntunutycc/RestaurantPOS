"""Standalone SQLAlchemy wiring test for Restaurant POS models.

Usage:
    python test_db.py
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, sessionmaker

from models import Base, Category, MenuItem, Order, OrderItem, Table, User, Zone


TEST_DB_PATH = Path(__file__).parent / "test_pos.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"


def make_engine_and_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, Session


def create_schema(engine) -> None:
    """Create all tables for a clean test database."""
    Base.metadata.create_all(bind=engine)


def seed_dummy_data(db) -> int:
    """Seed 2 zones, 4 tables, 2 waiters, and 1 order with 3 order items."""
    zone_indoor = Zone(name="Indoor")
    zone_outdoor = Zone(name="Outdoor")
    db.add_all([zone_indoor, zone_outdoor])
    db.flush()

    t1 = Table(name="Table 1", zone_id=zone_indoor.id, status="occupied")
    t2 = Table(name="Table 2", zone_id=zone_indoor.id, status="available")
    t3 = Table(name="Table 3", zone_id=zone_outdoor.id, status="available")
    t4 = Table(name="Table 4", zone_id=zone_outdoor.id, status="available")
    db.add_all([t1, t2, t3, t4])
    db.flush()

    waiter_a = User(
        username="waiter_a",
        password_hash="dummy_hash_a",
        role="waiter",
        pin_code="1111",
    )
    waiter_b = User(
        username="waiter_b",
        password_hash="dummy_hash_b",
        role="waiter",
        pin_code="2222",
    )
    db.add_all([waiter_a, waiter_b])
    db.flush()

    category = Category(name="Test Category")
    db.add(category)
    db.flush()
    m1 = MenuItem(name="Noodles", price=10.0, category_id=category.id)
    m2 = MenuItem(name="Fried Rice", price=10.0, category_id=category.id)
    m3 = MenuItem(name="Soup", price=12.5, category_id=category.id)
    db.add_all([m1, m2, m3])
    db.flush()

    order = Order(
        table_id=t1.id,
        table_number=1,
        status="open",
        total_amount=42.5,
    )
    db.add(order)
    db.flush()

    oi1 = OrderItem(
        order_id=order.id,
        menu_item_id=m1.id,
        quantity=1,
        subtotal=10.0,
        created_by_id=waiter_a.id,
        item_status="pending",
    )
    oi2 = OrderItem(
        order_id=order.id,
        menu_item_id=m2.id,
        quantity=2,
        subtotal=20.0,
        created_by_id=waiter_b.id,
        item_status="pending",
    )
    oi3 = OrderItem(
        order_id=order.id,
        menu_item_id=m3.id,
        quantity=1,
        subtotal=12.5,
        created_by_id=waiter_a.id,
        item_status="pending",
    )
    db.add_all([oi1, oi2, oi3])
    db.commit()
    return order.id


def run_read_tests(db, order_id: int) -> None:
    """Read checks for relationships and joins."""
    print("\n[READ TEST] Zone -> Tables")
    zone = (
        db.query(Zone)
        .options(joinedload(Zone.tables))
        .filter(Zone.name == "Indoor")
        .first()
    )
    if not zone:
        raise RuntimeError("Zone 'Indoor' not found after seeding.")
    print(f"Zone: {zone.name}")
    for table in zone.tables:
        print(f"  - Table: {table.name} (status={table.status})")

    print("\n[READ TEST] Order -> Items -> Waiter(created_by)")
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise RuntimeError(f"Order id={order_id} not found after seeding.")

    print(f"Order #{order.id} (table_id={order.table_id}, status={order.status})")
    for item in order.order_items:
        waiter_name = item.created_by.username if item.created_by else "N/A"
        print(
            f"  - Item#{item.id} menu_item_id={item.menu_item_id} "
            f"qty={item.quantity} item_status={item.item_status} waiter={waiter_name}"
        )


def run_update_test(db, order_id: int) -> None:
    """Update one OrderItem status to served."""
    print("\n[UPDATE TEST] Set one OrderItem to served")
    item = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.id.asc())
        .first()
    )
    if not item:
        raise RuntimeError("No order item found for update test.")

    item.item_status = "served"
    db.commit()
    db.refresh(item)
    print(f"Updated Item#{item.id} -> item_status={item.item_status}")


def main() -> None:
    # Start from a clean file each run to make results deterministic.
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine, Session = make_engine_and_session()
    create_schema(engine)

    db = Session()
    try:
        try:
            order_id = seed_dummy_data(db)
            run_read_tests(db, order_id)
            run_update_test(db, order_id)
            print("\nOK: Database model wiring test completed successfully.")
        except IntegrityError as exc:
            db.rollback()
            print("\nINTEGRITY ERROR:")
            print(exc)
        except SQLAlchemyError as exc:
            db.rollback()
            print("\nSQLALCHEMY ERROR:")
            print(exc)
        except Exception as exc:
            db.rollback()
            print("\nUNEXPECTED ERROR:")
            print(exc)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
