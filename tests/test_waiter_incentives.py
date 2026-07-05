"""Promoted menu items and waiter incentive reporting."""

import uuid
from datetime import datetime

from models import Category, MenuItem, Order, OrderItem, Table, User, Zone


def _seed_paid_promoted_line(
    db_session,
    *,
    item: MenuItem,
    waiter: User,
    cashier: User,
    quantity: int = 2,
    unit_price: float = 15.0,
):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"WI-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"WI-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    subtotal = unit_price * quantity
    order = Order(
        table_id=table.id,
        order_type="dine_in",
        status="paid",
        total_amount=subtotal,
        checked_out_by_id=cashier.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=quantity,
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


def test_toggle_promoted_flips_flag(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"WI-C-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"WI-I-{suffix}",
        price=10.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=False,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = client.put(
        f"/api/menu-items/{item.id}/toggle-promoted",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_promoted"] is True

    db_session.expire_all()
    row = db_session.query(MenuItem).filter(MenuItem.id == item.id).first()
    assert row.is_promoted is True


def test_create_menu_item_with_is_promoted(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:8]
    cat = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": f"WI-CC-{suffix}", "printer_route": "food"},
    )
    assert cat.status_code == 200
    category_id = cat.json()["id"]

    res = client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json={
            "name": f"WI-New-{suffix}",
            "price": 9.0,
            "category_id": category_id,
            "is_promoted": True,
            "modifiers_config": [],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_promoted"] is True


def test_promoted_report_attributes_waiter(client, auth_headers, db_session, seed_users):
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"WI-R-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"WI-P-{suffix}",
        price=15.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    _seed_paid_promoted_line(
        db_session,
        item=item,
        waiter=seed_users["waiter"],
        cashier=seed_users["cashier"],
        quantity=2,
        unit_price=15.0,
    )

    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    row = next((r for r in res.json() if r["user_id"] == seed_users["waiter"].id), None)
    assert row is not None
    assert int(row["quantity"]) >= 2
    assert float(row["total_sales"]) >= 30.0


def test_promoted_report_excludes_non_promoted_items(client, auth_headers, db_session, seed_users):
    suffix = uuid.uuid4().hex[:8]
    waiter = User(
        username=f"wi_waiter_{suffix}",
        role="waiter",
        password_hash="x",
        pin_code=f"{int(suffix[:4], 16) % 10000:04d}",
    )
    db_session.add(waiter)
    db_session.flush()

    cat = Category(name=f"WI-X-{suffix}")
    db_session.add(cat)
    db_session.flush()
    promoted = MenuItem(
        name=f"WI-PR-{suffix}",
        price=5.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=True,
        modifiers_config=[],
    )
    regular = MenuItem(
        name=f"WI-RG-{suffix}",
        price=50.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=False,
        modifiers_config=[],
    )
    db_session.add_all([promoted, regular])
    db_session.commit()

    _seed_paid_promoted_line(
        db_session,
        item=promoted,
        waiter=waiter,
        cashier=seed_users["cashier"],
        quantity=1,
        unit_price=5.0,
    )
    _seed_paid_promoted_line(
        db_session,
        item=regular,
        waiter=waiter,
        cashier=seed_users["cashier"],
        quantity=1,
        unit_price=50.0,
    )

    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("root"),
    )
    assert res.status_code == 200, res.text
    row = next((r for r in res.json() if r["user_id"] == waiter.id), None)
    assert row is not None
    assert int(row["quantity"]) == 1
    assert float(row["total_sales"]) == 5.0


def test_cashier_cannot_access_promoted_report(client, auth_headers):
    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 403


def test_account_cannot_access_promoted_report(client, auth_headers):
    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 403


def test_waiter_promoted_report_scoped_to_self(client, auth_headers, db_session, seed_users):
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"WI-W-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"WI-WI-{suffix}",
        price=12.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    _seed_paid_promoted_line(
        db_session,
        item=item,
        waiter=seed_users["waiter"],
        cashier=seed_users["cashier"],
        quantity=1,
        unit_price=12.0,
    )

    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["user_id"] == seed_users["waiter"].id
