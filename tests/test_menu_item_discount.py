"""Per-item menu discount with tax applied after discount (standard POS math)."""

import uuid

from models import Category, MenuItem, OrderItem


def _seed_category(db_session):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"DISC-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    return category


def _table_id(client, db_session, auth_headers):
    from models import Table, Zone

    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"DISC-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"DISC-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table.id


def test_item_10pct_discount_5pct_tax_tax_on_discounted_price(client, db_session, auth_headers):
    """10% discount on 1000 → 900; 5% tax on 900 → 45; final 945."""
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"DiscTax-{uuid.uuid4().hex[:6]}",
        price=1000.0,
        discount_type="percentage",
        discount_value=10.0,
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
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "is_takeaway": False, "selected_modifiers": []}],
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["total_amount"] == 945.0
    order_id = submit.json()["id"]

    line = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert float(line.unit_price_at_sale) == 1000.0
    assert float(line.unit_discount_at_sale) == 100.0
    assert float(line.unit_tax_at_sale) == 45.0
    assert float(line.subtotal) == 945.0

    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert details.status_code == 200, details.text
    body = details.json()
    assert body["breakdown_subtotal"] == 1000.0
    assert body["breakdown_discount_total"] == 100.0
    assert body["breakdown_tax_total"] == 45.0
    assert body["breakdown_grand_total"] == 945.0
    assert body["breakdown_grand_total"] == body["breakdown_subtotal"] - body["breakdown_discount_total"] + body["breakdown_tax_total"]

    item = body["items"][0]
    assert item["unit_price_at_sale"] == 1000.0
    assert item["unit_discount_at_sale"] == 100.0
    assert item["unit_tax_at_sale"] == 45.0


def test_fixed_discount_and_percentage_tax(client, db_session, auth_headers):
    """Base 2000, fixed discount 200, 5% tax on 1800 → 90; final 1890."""
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"FixDisc-{uuid.uuid4().hex[:6]}",
        price=2000.0,
        discount_type="fixed",
        discount_value=200.0,
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
    # per unit: 2000 - 200 + 90 = 1890 × 2 = 3780
    assert submit.json()["total_amount"] == 3780.0

    order_id = submit.json()["id"]
    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    body = details.json()
    assert body["breakdown_subtotal"] == 4000.0
    assert body["breakdown_discount_total"] == 400.0
    assert body["breakdown_tax_total"] == 180.0
    assert body["breakdown_grand_total"] == 3780.0
    assert body["breakdown_grand_total"] == body["breakdown_subtotal"] - body["breakdown_discount_total"] + body["breakdown_tax_total"]


def test_legacy_discount_price_migrated_to_fixed_discount(client, db_session, auth_headers):
    """Legacy discount_price=800 on price=1000 → fixed discount 200."""
    category = _seed_category(db_session)
    menu_item = MenuItem(
        name=f"Legacy-{uuid.uuid4().hex[:6]}",
        price=1000.0,
        discount_price=800.0,
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
    line = db_session.query(OrderItem).filter(OrderItem.order_id == submit.json()["id"]).first()
    assert float(line.unit_price_at_sale) == 1000.0
    assert float(line.unit_discount_at_sale) == 200.0
    assert float(line.subtotal) == 800.0
