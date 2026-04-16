import uuid

from models import Category, MenuItem, Order, Table, Zone


def _seed_decimal_menu_and_table(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"M-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"M-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"M-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    item = MenuItem(
        name=f"M-Item-{suffix}",
        price=3.33,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(item)
    return table, item


def _submit_one_batch(client, headers, table_id, menu_item_id, quantity):
    return client.post(
        "/api/orders/submit",
        headers=headers,
        json={
            "table_id": table_id,
            "order_type": "dine_in",
            "items": [
                {
                    "menu_item_id": menu_item_id,
                    "quantity": quantity,
                    "selected_modifiers": [],
                }
            ],
        },
    )


def test_submit_order_decimal_total_stable_3_33_times_3(client, db_session, auth_headers):
    table, item = _seed_decimal_menu_and_table(db_session)
    res = _submit_one_batch(client, auth_headers("waiter"), table.id, item.id, 3)
    assert res.status_code == 200, res.text
    body = res.json()

    # 3.33 * 3 must be 9.99 exactly at contract boundary.
    assert body["total_amount"] == 9.99
    assert f"{body['total_amount']:.2f}" == "9.99"


def test_submit_add_on_batches_decimal_total_stable(client, db_session, auth_headers):
    table, item = _seed_decimal_menu_and_table(db_session)
    headers = auth_headers("waiter")

    first = _submit_one_batch(client, headers, table.id, item.id, 3)
    assert first.status_code == 200, first.text
    assert first.json()["total_amount"] == 9.99

    second = _submit_one_batch(client, headers, table.id, item.id, 1)
    assert second.status_code == 200, second.text
    # 9.99 + 3.33 = 13.32
    assert second.json()["total_amount"] == 13.32
    assert f"{second.json()['total_amount']:.2f}" == "13.32"


def test_checkout_decimal_change_amount_stable(client, db_session, auth_headers):
    table, item = _seed_decimal_menu_and_table(db_session)
    headers_waiter = auth_headers("waiter")
    headers_cashier = auth_headers("cashier")

    submit = _submit_one_batch(client, headers_waiter, table.id, item.id, 3)
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]
    assert submit.json()["total_amount"] == 9.99

    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=headers_cashier,
        json={
            "payment_method": "cash",
            "amount_tendered": 10.00,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["total_amount"] == 9.99
    assert body["change_amount"] == 0.01
    assert f"{body['change_amount']:.2f}" == "0.01"


def test_checkout_excludes_cancelled_decimal_line_item(client, db_session, auth_headers):
    table, item = _seed_decimal_menu_and_table(db_session)
    headers_waiter = auth_headers("waiter")
    headers_cashier = auth_headers("cashier")

    submit = _submit_one_batch(client, headers_waiter, table.id, item.id, 3)  # 9.99
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]

    details = client.get(
        f"/api/orders/{order_id}/details",
        headers=headers_waiter,
    )
    assert details.status_code == 200, details.text
    items = details.json().get("items") or []
    assert items, "Expected at least one order item"
    item_id = items[0]["id"]

    cancel = client.put(
        f"/api/orders/{order_id}/items/{item_id}/status",
        headers=headers_waiter,
        json={"status": "cancelled"},
    )
    assert cancel.status_code == 200, cancel.text

    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=headers_cashier,
        json={
            "payment_method": "cash",
            "amount_tendered": 1.00,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["total_amount"] == 0.00
    assert body["change_amount"] == 1.00

