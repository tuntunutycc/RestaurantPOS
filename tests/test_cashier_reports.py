"""Cashier role: ordering inheritance, own daily sales, staff breakdown scoping."""

import uuid
from datetime import datetime

from models import Category, MenuItem, Order, OrderItem, Table, User, Zone


def _seed_open_table_and_item(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"CR-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"CR-Table-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    cat = Category(name=f"CR-Cat-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"CR-Item-{suffix}",
        price=8.0,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(item)
    return table, item


def _seed_paid_order(
    db_session,
    *,
    cashier: User,
    waiter: User,
    total: float = 11.0,
    subtotal: float = 10.0,
):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"CRP-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"CRP-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    cat = Category(name=f"CRPC-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"CRPI-{suffix}",
        price=subtotal,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        order_type="dine_in",
        status="paid",
        total_amount=total,
        checked_out_by_id=cashier.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=subtotal,
            batch_number=1,
            batch_status="pending",
            item_status="served",
            selected_modifiers=[],
            created_by_id=waiter.id,
        )
    )
    db_session.commit()
    return order


def test_cashier_can_submit_orders(client, db_session, auth_headers, seed_users):
    """FR-C1: Cashier inherits waiter submit permission; line attributed to cashier."""
    table, item = _seed_open_table_and_item(db_session)
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("cashier"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert res.status_code == 200, res.text
    order_id = res.json()["id"]

    db_session.expire_all()
    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == order_id, OrderItem.menu_item_id == item.id)
        .first()
    )
    assert line is not None
    assert line.created_by_id == seed_users["cashier"].id


def test_cashier_summary_scoped_to_own_checkout(client, db_session, auth_headers, seed_users):
    """FR-C2: Cashier today summary includes only orders they checked out."""
    cashier_a = seed_users["cashier"]
    waiter = seed_users["waiter"]

    cashier_b = User(
        username=f"cashier_b_{uuid.uuid4().hex[:6]}",
        role="cashier",
        password_hash="x",
        pin_code=f"{int(uuid.uuid4().hex[:4], 16) % 10000:04d}",
    )
    db_session.add(cashier_b)
    db_session.commit()
    db_session.refresh(cashier_b)

    _seed_paid_order(db_session, cashier=cashier_a, waiter=waiter, total=15.0, subtotal=14.0)
    _seed_paid_order(db_session, cashier=cashier_b, waiter=waiter, total=25.0, subtotal=24.0)

    res_a = client.get("/api/reports/summary/today", headers=auth_headers("cashier"))
    assert res_a.status_code == 200, res_a.text
    sales_a = float(res_a.json()["total_sales"])
    assert sales_a >= 15.0
    assert sales_a < 40.0  # must not include cashier B's 25.0 order


def test_cashier_cannot_view_order_staff_breakdown(client, auth_headers, seed_users, db_session):
    """Cashier must not access Staff Performance / waiter breakdown APIs."""
    _seed_paid_order(db_session, cashier=seed_users["cashier"], waiter=seed_users["waiter"])
    today = datetime.utcnow().date().isoformat()

    res = client.get(
        f"/api/reports/sales/by-order-staff?start_date={today}&end_date={today}",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 403, res.text


def test_cashier_cannot_view_by_cashier_breakdown(client, auth_headers, seed_users, db_session):
    """Cashier must not access per-cashier Staff Performance breakdown."""
    _seed_paid_order(db_session, cashier=seed_users["cashier"], waiter=seed_users["waiter"])
    today = datetime.utcnow().date().isoformat()

    res = client.get(
        f"/api/reports/sales/by-cashier?start_date={today}&end_date={today}",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 403, res.text


def test_waiter_order_staff_scoped_to_self(client, auth_headers, seed_users, db_session):
    _seed_paid_order(db_session, cashier=seed_users["cashier"], waiter=seed_users["waiter"])
    today = datetime.utcnow().date().isoformat()

    res = client.get(
        f"/api/reports/sales/by-order-staff?start_date={today}&end_date={today}",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) >= 1
    assert all(r["user_id"] == seed_users["waiter"].id for r in rows)
