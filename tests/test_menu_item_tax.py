"""Per-item tax on menu items (dine-in vs takeaway base)."""

import uuid

from models import Category, MenuItem, OrderItem


def _seed_category(db_session):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"TAX-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    return category


def test_menu_item_no_tax_dine_in(client, db_session, auth_headers):
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"NoTax-{uuid.uuid4().hex[:6]}",
        price=1000.0,
        tax_type="none",
        tax_value=0.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "table_id": _table_id(client, db_session, auth_headers),
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "is_takeaway": False, "selected_modifiers": []}],
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["total_amount"] == 1000.0
    order_id = submit.json()["id"]

    line = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert float(line.unit_tax_at_sale or 0) == 0.0
    assert float(line.subtotal) == 1000.0

    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 1000.0, "discount_type": None, "discount_value": 0},
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert float(body["tax_amount"]) == 0.0
    assert float(body["total_amount"]) == 1000.0


def test_menu_item_percentage_tax_dine_in(client, db_session, auth_headers):
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"PctTax-{uuid.uuid4().hex[:6]}",
        price=1000.0,
        tax_type="percentage",
        tax_value=5.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "table_id": _table_id(client, db_session, auth_headers),
            "items": [{"menu_item_id": menu_item.id, "quantity": 2, "is_takeaway": False, "selected_modifiers": []}],
        },
    )
    assert submit.status_code == 200, submit.text
    # base 1000 + 5% tax 50 = 1050 per unit × 2 = 2100
    assert submit.json()["total_amount"] == 2100.0
    order_id = submit.json()["id"]

    line = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert float(line.unit_tax_at_sale) == 50.0
    assert float(line.subtotal) == 2100.0

    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 2100.0, "discount_type": None, "discount_value": 0},
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert float(body["tax_amount"]) == 100.0
    assert float(body["total_amount"]) == 2100.0


def test_menu_item_fixed_tax_takeaway_price(client, db_session, auth_headers):
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"FixTax-{uuid.uuid4().hex[:6]}",
        price=1500.0,
        takeaway_price=2000.0,
        tax_type="fixed",
        tax_value=500.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Tax TW",
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "is_takeaway": True, "selected_modifiers": []}],
        },
    )
    assert submit.status_code == 200, submit.text
    # takeaway base 2000 + fixed tax 500 = 2500
    assert submit.json()["total_amount"] == 2500.0
    order_id = submit.json()["id"]

    line = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert float(line.unit_price_at_sale) == 2000.0
    assert float(line.unit_tax_at_sale) == 500.0
    assert float(line.subtotal) == 2500.0

    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 2500.0, "discount_type": None, "discount_value": 0},
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert float(body["tax_amount"]) == 500.0
    assert float(body["total_amount"]) == 2500.0


def _table_id(client, db_session, auth_headers):
    from models import Table, Zone

    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"TAX-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"TAX-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table.id
