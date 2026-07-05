import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_order_with_cancelled_item(db_session):
    # Minimal menu + table context (to keep ORM relationships consistent).
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"Main-{suffix}")
    db_session.add(cat)
    db_session.flush()

    item_ok = MenuItem(name="Rice", price=10.0, category_id=cat.id, is_available=True, modifiers_config=[])
    item_cancelled = MenuItem(name="Soup", price=5.0, category_id=cat.id, is_available=True, modifiers_config=[])
    db_session.add_all([item_ok, item_cancelled])
    db_session.flush()

    zone = Zone(name=f"Z-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()

    order = Order(
        table_id=table.id,
        table_number=1,
        order_type="dine_in",
        status="open",
        total_amount=0.0,
    )
    db_session.add(order)
    db_session.flush()

    # One normal item + one cancelled item.
    oi1 = OrderItem(
        order_id=order.id,
        menu_item_id=item_ok.id,
        quantity=1,
        subtotal=10.0,
        batch_number=1,
        batch_status="pending",
        item_status="pending",
        selected_modifiers=[],
    )
    oi2 = OrderItem(
        order_id=order.id,
        menu_item_id=item_cancelled.id,
        quantity=1,
        subtotal=5.0,
        batch_number=1,
        batch_status="pending",
        item_status="cancelled",
        selected_modifiers=[],
    )
    db_session.add_all([oi1, oi2])
    db_session.commit()
    db_session.refresh(order)
    return order


def test_checkout_excludes_cancelled_items_from_total(client, db_session, auth_headers):
    order = _seed_order_with_cancelled_item(db_session)

    # Cancelled item subtotal (5.0) must NOT be charged.
    # Tax-on-net rule then applies 5% tax on the remaining 10.0.
    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "cash",
            "amount_tendered": 20.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert float(body["tax_amount"]) == 0.5
    assert float(body["total_amount"]) == 10.5


def test_waiter_cannot_checkout_forbidden(client, db_session, auth_headers):
    order = _seed_order_with_cancelled_item(db_session)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("waiter"),
        json={
            "payment_method": "cash",
            "amount_tendered": 20.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert res.status_code == 403, res.text


def _table_status_value(table) -> str:
    return getattr(table.status, "value", table.status)


def test_table_released_when_last_item_cancelled(client, db_session, auth_headers):
    """Occupy table -> submit order -> cancel only item -> table becomes available."""
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"AR-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"AR-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"AR-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    menu_item = MenuItem(
        name=f"AR-Item-{suffix}",
        price=12.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(menu_item)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    db_session.refresh(table)
    assert _table_status_value(table) == "occupied"

    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert details.status_code == 200, details.text
    item_id = details.json()["items"][0]["id"]

    cancel = client.put(
        f"/api/orders/{order_id}/items/{item_id}/status",
        headers=auth_headers("waiter"),
        json={"status": "cancelled"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    assert float(cancel.json()["total_amount"]) == 0.0

    db_session.refresh(table)
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert _table_status_value(table) == "available"
    assert order is not None
    assert order.status == "cancelled"


def test_table_released_when_full_order_cancelled(client, db_session, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"FO-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"FO-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"FO-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    menu_item = MenuItem(
        name=f"FO-Item-{suffix}",
        price=8.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()

    order = Order(
        table_id=table.id,
        table_number=table.id,
        order_type="dine_in",
        status="open",
        total_amount=8.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=1,
            subtotal=8.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(order)

    res = client.put(
        f"/api/orders/{order.id}/status",
        headers=auth_headers("waiter"),
        json={"status": "cancelled"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    db_session.refresh(table)
    db_session.refresh(order)
    assert _table_status_value(table) == "available"
    assert order.status == "cancelled"
    assert all(oi.item_status == "cancelled" for oi in order.order_items)

