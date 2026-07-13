"""Legacy table backfill must not create a ghost table named None."""

from models import Order, Table, Zone
from services.legacy_table_backfill import (
    backfill_legacy_dine_in_table_links,
    remove_ghost_none_tables,
    repair_legacy_table_links,
)


def test_takeaway_with_null_table_number_does_not_create_none_table(db_session):
    zone = Zone(name="Main-Ghost")
    db_session.add(zone)
    db_session.flush()

    order = Order(
        table_id=None,
        table_number=None,
        order_type="takeaway",
        customer_name="Walk-in",
        status="open",
        total_amount=10.0,
    )
    db_session.add(order)
    db_session.commit()

    backfill_legacy_dine_in_table_links(db_session, default_zone=zone)

    ghosts = db_session.query(Table).filter(Table.name.in_(("None", "none", "null"))).all()
    assert ghosts == []
    db_session.refresh(order)
    assert order.table_id is None


def test_remove_ghost_none_table_unlinks_orders(db_session):
    zone = Zone(name="Main-Ghost2")
    db_session.add(zone)
    db_session.flush()
    ghost = Table(name="None", zone_id=zone.id, status="available")
    db_session.add(ghost)
    db_session.flush()

    order = Order(
        table_id=ghost.id,
        table_number=None,
        order_type="takeaway",
        status="open",
        total_amount=5.0,
    )
    db_session.add(order)
    db_session.commit()

    removed = remove_ghost_none_tables(db_session)
    assert removed == 1
    assert db_session.query(Table).filter(Table.name == "None").first() is None
    db_session.refresh(order)
    assert order.table_id is None


def test_legacy_numeric_table_number_still_backfills(db_session):
    zone = Zone(name="Main-Legacy")
    db_session.add(zone)
    db_session.flush()
    order = Order(
        table_id=None,
        table_number=12,
        order_type="dine_in",
        status="open",
        total_amount=8.0,
    )
    db_session.add(order)
    db_session.commit()

    linked = backfill_legacy_dine_in_table_links(db_session, default_zone=zone)
    assert linked == 1
    table = db_session.query(Table).filter(Table.name == "12").first()
    assert table is not None
    db_session.refresh(order)
    assert order.table_id == table.id


def test_repair_legacy_table_links_idempotent(db_session):
    zone = Zone(name="Main")
    db_session.add(zone)
    db_session.flush()
    ghost = Table(name="None", zone_id=zone.id, status="available")
    db_session.add(ghost)
    db_session.add(
        Order(
            table_id=None,
            table_number=None,
            order_type="takeaway",
            status="open",
            total_amount=1.0,
        )
    )
    db_session.commit()

    repair_legacy_table_links(db_session)
    repair_legacy_table_links(db_session)
    assert db_session.query(Table).filter(Table.name == "None").first() is None
