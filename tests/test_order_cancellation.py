"""Whole-order cancellation via POST /api/orders/{order_id}/cancel."""

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_dine_in_order(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"OC-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"OC-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"OC-C-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"OC-I-{suffix}",
        price=15.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        table_number=1,
        order_type="dine_in",
        status="open",
        total_amount=30.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=2,
            subtotal=30.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()
    db_session.refresh(order)
    db_session.refresh(table)
    return order, table, menu_item


def test_cancel_order_frees_table_and_sets_status(client, db_session, auth_headers):
    order, table, _ = _seed_dine_in_order(db_session)
    assert table.status == "occupied"

    res = client.post(
        f"/api/orders/{order.id}/cancel",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == order.id
    assert body["status"] == "cancelled"

    db_session.refresh(order)
    db_session.refresh(table)
    assert order.status == "cancelled"
    assert table.status == "available"

    lines = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    assert lines
    assert all(line.item_status == "cancelled" for line in lines)


def test_cancel_takeaway_order_without_table(client, db_session, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"OC-TW-C-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"OC-TW-I-{suffix}",
        price=10.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()
    order = Order(
        table_id=None,
        order_type="takeaway",
        customer_name="Ko Zaw",
        status="open",
        total_amount=10.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=1,
            subtotal=10.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            is_takeaway=True,
            selected_modifiers=[],
        )
    )
    db_session.commit()
    db_session.refresh(order)

    res = client.post(
        f"/api/orders/{order.id}/cancel",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    db_session.refresh(order)
    assert order.table_id is None
    assert order.status == "cancelled"


def test_cancel_paid_order_rejected(client, db_session, auth_headers):
    order, _, _ = _seed_dine_in_order(db_session)
    order.status = "paid"
    db_session.commit()

    res = client.post(
        f"/api/orders/{order.id}/cancel",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 400, res.text
