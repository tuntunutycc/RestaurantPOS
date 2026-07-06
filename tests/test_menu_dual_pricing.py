import uuid

from models import Category, MenuItem, OrderItem, Table, Zone


def _seed_table(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table


def _seed_category_and_item(db_session, *, price: float, takeaway_price=None):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"Item-{suffix}",
        price=price,
        takeaway_price=takeaway_price,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)
    return menu_item


def _submit_line(client, auth_headers, menu_item_id, *, is_takeaway: bool, table_id=None, order_type="dine_in"):
    payload = {
        "order_type": order_type,
        "items": [
            {
                "menu_item_id": menu_item_id,
                "quantity": 1,
                "is_takeaway": is_takeaway,
                "selected_modifiers": [],
            }
        ],
    }
    if table_id is not None:
        payload["table_id"] = table_id
    return client.post("/api/orders/submit", headers=auth_headers("waiter"), json=payload)


def test_create_menu_item_with_takeaway_price(client, db_session, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    res = client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json={
            "name": f"Bento-{suffix}",
            "price": 5000.0,
            "takeaway_price": 5500.0,
            "category_id": category.id,
            "modifiers_config": [],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["price"] == 5000.0
    assert body["takeaway_price"] == 5500.0

    persisted = db_session.query(MenuItem).filter(MenuItem.id == body["id"]).first()
    assert persisted is not None
    assert persisted.takeaway_price == 5500.0


def test_dine_in_order_uses_regular_price(client, db_session, auth_headers):
    table = _seed_table(db_session)
    menu_item = _seed_category_and_item(db_session, price=1000.0, takeaway_price=1200.0)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=False,
        table_id=table.id,
        order_type="dine_in",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is False
    assert float(line.unit_price_at_sale) == 1000.0
    assert float(line.subtotal) == 1000.0


def test_takeaway_line_uses_takeaway_price(client, db_session, auth_headers):
    menu_item = _seed_category_and_item(db_session, price=1000.0, takeaway_price=1200.0)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=True,
        order_type="takeaway",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is True
    assert float(line.unit_price_at_sale) == 1200.0
    assert float(line.subtotal) == 1200.0


def test_takeaway_line_falls_back_to_regular_price_without_takeaway_price(client, db_session, auth_headers):
    menu_item = _seed_category_and_item(db_session, price=800.0, takeaway_price=None)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=True,
        order_type="takeaway",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is True
    assert float(line.unit_price_at_sale) == 800.0
    assert float(line.subtotal) == 800.0
