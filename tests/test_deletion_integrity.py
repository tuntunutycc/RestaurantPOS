from datetime import datetime
import uuid

from models import Category, MenuItem, Order, OrderItem, Table, User, Zone


def _seed_paid_order(db_session, *, quantity: int = 1):
    suffix = uuid.uuid4().hex[:8]

    waiter = User(
        username=f"waiter_del_{suffix}",
        role="waiter",
        password_hash="x",
        pin_code=f"{int(suffix[:4], 16) % 10000:04d}",
    )
    zone = Zone(name=f"D-Zone-{suffix}")
    db_session.add_all([waiter, zone])
    db_session.flush()

    table = Table(name=f"D-Table-{suffix}", zone_id=zone.id, status="available")
    category = Category(name=f"D-Cat-{suffix}")
    db_session.add_all([table, category])
    db_session.flush()

    menu_item = MenuItem(
        name=f"D-Item-{suffix}",
        price=12.0,
        discount_price=None,
        category_id=category.id,
        description="",
        image_url=None,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()

    line_subtotal = 12.0 * quantity
    order = Order(
        table_id=table.id,
        table_number=table.id,
        order_type="dine_in",
        status="paid",
        total_amount=line_subtotal + 0.6,
        tax_amount=0.6,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=quantity,
        subtotal=line_subtotal,
        batch_number=1,
        batch_status="pending",
        item_status="served",
        created_by_id=waiter.id,
        selected_modifiers=[],
        note=None,
        special_instructions=None,
        menu_item_name_at_sale=menu_item.name,
        unit_price_at_sale=12.0,
        category_name_at_sale=category.name,
    )
    db_session.add(order_item)
    db_session.commit()
    db_session.refresh(waiter)
    db_session.refresh(menu_item)
    db_session.refresh(order)
    db_session.refresh(order_item)
    return waiter, menu_item, order, order_item


def test_soft_delete_user_preserves_history_and_reports(client, db_session, auth_headers):
    waiter, _, order, _ = _seed_paid_order(db_session)
    archived_pin = waiter.pin_code

    delete_res = client.delete(f"/api/admin/users/{waiter.id}", headers=auth_headers("admin"))
    assert delete_res.status_code == 200, delete_res.text

    db_session.expire_all()
    archived = db_session.query(User).filter(User.id == waiter.id).first()
    assert archived is not None
    assert archived.is_deleted is True
    assert archived.pin_code is None

    list_res = client.get("/api/admin/users", headers=auth_headers("admin"))
    assert list_res.status_code == 200, list_res.text
    archived_row = next((u for u in list_res.json() if u["id"] == waiter.id), None)
    assert archived_row is not None
    assert archived_row["is_active"] is False

    dup_username = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": waiter.username, "role": "waiter", "pin_code": "4321"},
    )
    assert dup_username.status_code == 400
    assert dup_username.json()["detail"] == "Username is already taken (including by archived users)."

    reuse_pin = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": f"new_{waiter.username}", "role": "waiter", "pin_code": archived_pin},
    )
    assert reuse_pin.status_code == 200, reuse_pin.text

    details_res = client.get(f"/api/orders/{order.id}/details", headers=auth_headers("cashier"))
    assert details_res.status_code == 200, details_res.text
    details = details_res.json()
    assert details["items"][0]["waiter_name"] == "[Deleted User]"

    summary_res = client.get("/api/reports/summary/today", headers=auth_headers("admin"))
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert float(summary["total_sales"]) >= 12.6
    assert int(summary["total_orders"]) >= 1


def test_soft_delete_menu_item_preserves_history_and_reports(client, db_session, auth_headers):
    _, menu_item, _, order_item = _seed_paid_order(db_session, quantity=10_000)

    delete_res = client.delete(f"/api/menu-items/{menu_item.id}", headers=auth_headers("admin"))
    assert delete_res.status_code == 200, delete_res.text

    persisted_item = db_session.query(OrderItem).filter(OrderItem.id == order_item.id).first()
    assert persisted_item is not None
    assert persisted_item.menu_item_name_at_sale
    assert persisted_item.unit_price_at_sale is not None
    assert persisted_item.category_name_at_sale

    summary_res = client.get("/api/reports/summary/today", headers=auth_headers("admin"))
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert float(summary["total_sales"]) >= 12.6

    top_res = client.get("/api/reports/top-items", headers=auth_headers("admin"))
    assert top_res.status_code == 200, top_res.text
    top_rows = top_res.json()
    assert any(row["item_name"] == persisted_item.menu_item_name_at_sale for row in top_rows)
