import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_table_menu_order(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"RBAC-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"RBAC-Table-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"RBAC-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    menu_item = MenuItem(
        name=f"RBAC-Item-{suffix}",
        price=9.5,
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
        total_amount=9.5,
    )
    db_session.add(order)
    db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=1,
        subtotal=9.5,
        batch_number=1,
        batch_status="pending",
        item_status="pending",
        selected_modifiers=[],
    )
    db_session.add(order_item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(menu_item)
    db_session.refresh(order)
    db_session.refresh(order_item)
    return table, menu_item, order, order_item


def test_kitchen_forbidden_on_order_views(client, db_session, auth_headers):
    table, _, order, _ = _seed_table_menu_order(db_session)
    headers = auth_headers("kitchen")

    res_list = client.get("/api/orders/", headers=headers)
    assert res_list.status_code == 403, res_list.text

    res_takeaways = client.get("/api/orders/active-takeaways", headers=headers)
    assert res_takeaways.status_code == 403, res_takeaways.text

    res_tables = client.get("/api/orders/tables", headers=headers)
    assert res_tables.status_code == 403, res_tables.text

    res_by_table = client.get(f"/api/orders/active-by-table/{table.id}", headers=headers)
    assert res_by_table.status_code == 403, res_by_table.text

    res_details = client.get(f"/api/orders/{order.id}/details", headers=headers)
    assert res_details.status_code == 403, res_details.text


def test_kitchen_forbidden_on_order_mutations(client, db_session, auth_headers):
    table, menu_item, order, order_item = _seed_table_menu_order(db_session)
    headers = auth_headers("kitchen")

    res_create = client.post(
        "/api/orders/",
        headers=headers,
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert res_create.status_code == 403, res_create.text

    res_submit = client.post(
        "/api/orders/submit",
        headers=headers,
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert res_submit.status_code == 403, res_submit.text

    res_status = client.put(
        f"/api/orders/{order.id}/status",
        headers=headers,
        json={"status": "completed"},
    )
    assert res_status.status_code == 403, res_status.text

    res_item_status = client.put(
        f"/api/orders/{order.id}/items/{order_item.id}/status",
        headers=headers,
        json={"status": "served"},
    )
    assert res_item_status.status_code == 403, res_item_status.text


def test_waiter_cannot_checkout_but_can_submit(client, db_session, auth_headers):
    table, menu_item, order, _ = _seed_table_menu_order(db_session)
    waiter_headers = auth_headers("waiter")

    # Waiter is allowed to submit/create items.
    res_submit = client.post(
        "/api/orders/submit",
        headers=waiter_headers,
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": menu_item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert res_submit.status_code == 200, res_submit.text

    # Waiter is forbidden for payment endpoints.
    res_checkout_put = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=waiter_headers,
        json={"payment_method": "cash", "amount_tendered": 100, "discount_type": None, "discount_value": 0},
    )
    assert res_checkout_put.status_code == 403, res_checkout_put.text

    res_checkout_post = client.post(
        f"/api/orders/{order.id}/checkout",
        headers=waiter_headers,
        json={"payment_method": "cash", "amount_tendered": 100, "discount_type": None, "discount_value": 0},
    )
    assert res_checkout_post.status_code == 403, res_checkout_post.text


def test_cashier_and_admin_can_checkout(client, db_session, auth_headers):
    _, _, order, _ = _seed_table_menu_order(db_session)

    cashier_res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100, "discount_type": None, "discount_value": 0},
    )
    assert cashier_res.status_code == 200, cashier_res.text

    # Create a second order so admin checkout isn't blocked by already-paid status assumptions.
    _, _, second_order, _ = _seed_table_menu_order(db_session)
    admin_res = client.put(
        f"/api/orders/{second_order.id}/checkout",
        headers=auth_headers("admin"),
        json={"payment_method": "cash", "amount_tendered": 100, "discount_type": None, "discount_value": 0},
    )
    assert admin_res.status_code == 200, admin_res.text

