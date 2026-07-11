"""Direct walk-in takeaway: table_id=NULL, waiter attribution, incentive inclusion."""

import uuid
from datetime import datetime

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_menu_item(db_session):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"WIT-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"WIT-Item-{suffix}",
        price=1000.0,
        takeaway_price=1200.0,
        category_id=category.id,
        is_available=True,
        is_promoted=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)
    return menu_item


def _seed_table(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"WIT-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"WIT-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table


def test_walk_in_takeaway_submit_null_table_assigns_created_by(client, db_session, auth_headers, seed_users):
    menu_item = _seed_menu_item(db_session)
    waiter = seed_users["waiter"]

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "table_id": None,
            "customer_name": "Walk-in",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    order_id = res.json()["id"]

    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order is not None
    assert order.table_id is None
    assert order.order_type == "takeaway"
    assert order.created_by_id == waiter.id

    line = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert line is not None
    assert line.created_by_id == waiter.id
    assert line.is_takeaway is True
    assert float(line.unit_price_at_sale) == 1200.0


def test_dine_in_without_table_id_rejected(client, db_session, auth_headers):
    menu_item = _seed_menu_item(db_session)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": False,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert res.status_code == 400, res.text
    assert "table_id is required" in res.json()["detail"]


def test_dine_in_with_table_still_requires_valid_table(client, db_session, auth_headers):
    menu_item = _seed_menu_item(db_session)
    table = _seed_table(db_session)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "table_id": table.id,
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": False,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    db_session.refresh(table)
    assert table.status == "occupied"


def test_promoted_report_includes_null_table_walk_in_order(client, db_session, auth_headers, seed_users):
    menu_item = _seed_menu_item(db_session)
    waiter = seed_users["waiter"]
    cashier = seed_users["cashier"]

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Walk-in",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    order = db_session.query(Order).filter(Order.id == order_id).first()
    order.status = "paid"
    order.checked_out_by_id = cashier.id
    order.created_at = datetime.utcnow()
    db_session.commit()

    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    row = next((r for r in res.json() if r["user_id"] == waiter.id), None)
    assert row is not None
    assert int(row["quantity"]) >= 2
    assert float(row["total_sales"]) >= 2400.0


def test_fetch_active_takeaway_order_with_null_table(client, db_session, auth_headers, seed_users):
    menu_item = _seed_menu_item(db_session)
    waiter = seed_users["waiter"]

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Ko Zaw",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    active = client.get("/api/orders/active-takeaways", headers=auth_headers("cashier"))
    assert active.status_code == 200, active.text
    match = next((o for o in active.json() if o["id"] == order_id), None)
    assert match is not None
    assert match["table_id"] is None
    assert match["order_type"] == "takeaway"
    assert match["customer_name"] == "Ko Zaw"
    assert match["waiter_name"] == waiter.username
    assert match["served_by_name"] == waiter.username

    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("cashier"))
    assert details.status_code == 200, details.text
    body = details.json()
    assert body["table_id"] is None
    assert body["order_type"] == "takeaway"
    assert body["customer_name"] == "Ko Zaw"
    assert body["waiter_name"] == waiter.username
    assert body["served_by_name"] == waiter.username
    assert len(body["items"]) == 1


def test_append_items_to_existing_takeaway_order(client, db_session, auth_headers, seed_users):
    menu_item = _seed_menu_item(db_session)
    waiter = seed_users["waiter"]

    first = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Ko Zaw",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert first.status_code == 200, first.text
    order_id = first.json()["id"]
    assert first.json()["is_new_order"] is True

    addon = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_id": order_id,
            "order_type": "takeaway",
            "customer_name": "Ko Zaw",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert addon.status_code == 200, addon.text
    assert addon.json()["id"] == order_id
    assert addon.json()["is_new_order"] is False

    lines = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.batch_number.asc())
        .all()
    )
    assert len(lines) == 2
    assert lines[0].batch_number == 1
    assert lines[1].batch_number == 2
    assert lines[1].created_by_id == waiter.id
    assert float(addon.json()["total_amount"]) == 3600.0

    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order.table_id is None


def test_cancel_takeaway_order_item_without_table(client, db_session, auth_headers):
    """Item-level cancel on walk-in takeaway (table_id=null) mirrors dine-in API."""
    menu_item = _seed_menu_item(db_session)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Ko Zaw",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert details.status_code == 200, details.text
    item_id = details.json()["items"][0]["id"]

    cancel = client.put(
        f"/api/orders/{order_id}/items/{item_id}/status",
        headers=auth_headers("waiter"),
        json={"status": "cancelled"},
    )
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["status"] == "cancelled"
    assert float(body["total_amount"]) == 0.0

    line = db_session.query(OrderItem).filter(OrderItem.id == item_id).first()
    assert line is not None
    assert line.item_status == "cancelled"

    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order.table_id is None
    assert order.status == "cancelled"

    active = client.get("/api/orders/active-takeaways", headers=auth_headers("waiter"))
    assert active.status_code == 200, active.text
    assert not any(o["id"] == order_id for o in active.json())


def test_last_takeaway_item_cancel_auto_clears_from_active_list(client, db_session, auth_headers):
    """Cancelling the only remaining item removes the takeaway from active-takeaways."""
    menu_item = _seed_menu_item(db_session)

    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Solo Item",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    before = client.get("/api/orders/active-takeaways", headers=auth_headers("waiter"))
    assert any(o["id"] == order_id for o in before.json())

    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    item_id = details.json()["items"][0]["id"]

    cancel = client.put(
        f"/api/orders/{order_id}/items/{item_id}/status",
        headers=auth_headers("waiter"),
        json={"status": "cancelled"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    after = client.get("/api/orders/active-takeaways", headers=auth_headers("waiter"))
    assert not any(o["id"] == order_id for o in after.json())
