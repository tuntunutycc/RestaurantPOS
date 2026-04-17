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

