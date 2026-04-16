import uuid

from models import Category, MenuItem, Table, Zone


def _seed_table_and_menu(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    menu_item = MenuItem(
        name=f"Item-{suffix}",
        price=12.5,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(menu_item)
    return table, menu_item


def test_create_order_response_contract(client, db_session, auth_headers):
    table, menu_item = _seed_table_and_menu(db_session)
    res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "customer_name": None,
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                    "selected_modifiers": [],
                    "special_instructions": None,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert set(body.keys()) == {"id", "table_number", "status", "total_amount"}
    assert isinstance(body["id"], int)
    assert body["table_number"] is None or isinstance(body["table_number"], int)
    assert isinstance(body["status"], str)
    assert isinstance(body["total_amount"], (int, float))


def test_update_order_status_response_contract(client, db_session, auth_headers):
    table, menu_item = _seed_table_and_menu(db_session)
    create_res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "customer_name": None,
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "selected_modifiers": [],
                    "special_instructions": None,
                }
            ],
        },
    )
    assert create_res.status_code == 200, create_res.text
    order_id = create_res.json()["id"]

    res = client.put(
        f"/api/orders/{order_id}/status",
        headers=auth_headers("admin"),
        json={"status": "completed"},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert set(body.keys()) == {"id", "status"}
    assert body["id"] == order_id
    assert body["status"] == "completed"


def test_update_order_status_rejects_invalid_literal_422(client, db_session, auth_headers):
    table, menu_item = _seed_table_and_menu(db_session)
    create_res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "customer_name": None,
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert create_res.status_code == 200, create_res.text
    order_id = create_res.json()["id"]

    res = client.put(
        f"/api/orders/{order_id}/status",
        headers=auth_headers("admin"),
        json={"status": "active"},
    )
    assert res.status_code == 422, res.text


def test_update_order_status_normalizes_whitespace_and_case(client, db_session, auth_headers):
    table, menu_item = _seed_table_and_menu(db_session)
    create_res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "customer_name": None,
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert create_res.status_code == 200, create_res.text
    order_id = create_res.json()["id"]

    res = client.put(
        f"/api/orders/{order_id}/status",
        headers=auth_headers("admin"),
        json={"status": "  COMPLETED  "},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "completed"

