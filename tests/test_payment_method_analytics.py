"""Payment method tracking at checkout and dashboard sales breakdown."""

import uuid
from datetime import datetime

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_open_order(db_session, *, total_amount: float = 1000.0):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"PM-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"PM-Item-{suffix}",
        price=total_amount,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()
    zone = Zone(name=f"PM-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"PM-Table-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    order = Order(
        table_id=table.id,
        table_number=1,
        order_type="dine_in",
        status="open",
        total_amount=total_amount,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=1,
            subtotal=total_amount,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()
    db_session.refresh(order)
    return order


def test_checkout_mobile_money_persists_payment_method(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total_amount=1500.0)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "mobile_money",
            "amount_tendered": 1500.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["payment_method"] == "mobile_money"

    db_session.refresh(order)
    assert order.payment_method == "mobile_money"
    assert order.status == "paid"


def test_checkout_rejects_invalid_payment_method(client, db_session, auth_headers):
    order = _seed_open_order(db_session)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "credit_card",
            "amount_tendered": 1000.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert res.status_code == 422, res.text


def test_checkout_accepts_mobile_money_display_alias(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total_amount=800.0)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "Mobile Money",
            "amount_tendered": 800.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert res.status_code == 200, res.text
    db_session.refresh(order)
    assert order.payment_method == "mobile_money"


def test_sales_breakdown_sums_cash_and_mobile_for_today(client, db_session, auth_headers, seed_users):
    cashier = seed_users["cashier"]

    before_res = client.get("/api/analytics/sales-breakdown", headers=auth_headers("admin"))
    assert before_res.status_code == 200, before_res.text
    before_today = before_res.json()["today"]
    cashier_before_res = client.get("/api/analytics/sales-breakdown", headers=auth_headers("cashier"))
    assert cashier_before_res.status_code == 200, cashier_before_res.text
    cashier_before_today = cashier_before_res.json()["today"]

    cash_order = _seed_open_order(db_session, total_amount=300.0)
    mobile_order = _seed_open_order(db_session, total_amount=200.0)

    for order, method in ((cash_order, "cash"), (mobile_order, "mobile_money")):
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": method,
                "amount_tendered": float(order.total_amount),
                "discount_type": None,
                "discount_value": 0,
            },
        )
        assert res.status_code == 200, res.text

    res = client.get("/api/analytics/sales-breakdown", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    today = res.json()["today"]
    assert float(today["cash"]) - float(before_today["cash"]) == 300.0
    assert float(today["mobile_money"]) - float(before_today["mobile_money"]) == 200.0
    assert float(today["total"]) - float(before_today["total"]) == 500.0
    assert float(today["total"]) == float(today["cash"]) + float(today["mobile_money"])

    month = res.json()["month"]
    assert float(month["total"]) == float(month["cash"]) + float(month["mobile_money"])

    cashier_res = client.get("/api/analytics/sales-breakdown", headers=auth_headers("cashier"))
    assert cashier_res.status_code == 200, cashier_res.text
    cashier_today = cashier_res.json()["today"]
    assert float(cashier_today["total"]) - float(cashier_before_today["total"]) == 500.0

    waiter_res = client.get("/api/analytics/sales-breakdown", headers=auth_headers("waiter"))
    assert waiter_res.status_code == 403, waiter_res.text

    db_session.refresh(cash_order)
    assert cash_order.checked_out_by_id == cashier.id
