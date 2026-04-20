import uuid

from models import Order, Table, Zone


def _seed_zone_and_table(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"TM-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"TM-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(zone)
    db_session.refresh(table)
    return zone, table


def test_admin_can_delete_empty_table(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] is True
    assert body["table_id"] == table.id

    assert db_session.query(Table).filter(Table.id == table.id).first() is None


def test_table_with_active_order_cannot_be_deleted(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)
    order = Order(
        table_id=table.id,
        table_number=1,
        order_type="dine_in",
        status="open",
        total_amount=10.0,
    )
    db_session.add(order)
    db_session.commit()

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 400, res.text
    detail = (res.json() or {}).get("detail", "")
    assert "non-finalized orders" in detail
    assert db_session.query(Table).filter(Table.id == table.id).first() is not None


def test_non_admin_cannot_delete_table(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 403, res.text
    assert db_session.query(Table).filter(Table.id == table.id).first() is not None


def test_delete_detaches_finalized_orders_history(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)
    finalized_order = Order(
        table_id=table.id,
        table_number=7,
        order_type="dine_in",
        status="paid",
        total_amount=25.0,
    )
    db_session.add(finalized_order)
    db_session.commit()
    db_session.refresh(finalized_order)

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text

    db_session.refresh(finalized_order)
    assert finalized_order.table_id is None
    assert finalized_order.total_amount == 25.0


def test_table_with_completed_order_is_blocked_as_non_finalized(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)
    order = Order(
        table_id=table.id,
        table_number=8,
        order_type="dine_in",
        status="completed",
        total_amount=20.0,
    )
    db_session.add(order)
    db_session.commit()

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 400, res.text
    detail = (res.json() or {}).get("detail", "")
    assert "Only paid or cancelled orders" in detail
    assert db_session.query(Table).filter(Table.id == table.id).first() is not None


def test_cancelled_order_allows_table_delete_and_detach(client, db_session, auth_headers):
    _, table = _seed_zone_and_table(db_session)
    cancelled_order = Order(
        table_id=table.id,
        table_number=10,
        order_type="dine_in",
        status="cancelled",
        total_amount=0.0,
    )
    db_session.add(cancelled_order)
    db_session.commit()
    db_session.refresh(cancelled_order)

    res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text

    db_session.refresh(cancelled_order)
    assert cancelled_order.table_id is None
