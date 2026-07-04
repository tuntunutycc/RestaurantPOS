"""Menu item soft delete and active-order guard tests."""

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone

ACTIVE_ORDER_MSG = "Cannot delete menu item. It is currently part of an active order."


def _seed_category(db_session):
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"MSD-Cat-{suffix}")
    db_session.add(cat)
    db_session.flush()
    return cat


def test_soft_delete_menu_item_without_active_orders(client, auth_headers, db_session):
    cat = _seed_category(db_session)
    suffix = uuid.uuid4().hex[:8]
    item = MenuItem(
        name=f"MSD-Item-{suffix}",
        price=12.0,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()

    res = client.delete(f"/api/menu-items/{item.id}", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    assert res.json()["deleted"] is True

    db_session.refresh(item)
    assert item.is_deleted is True
    assert item.is_available is False
    assert item.deleted_at is not None

    listed = client.get("/api/menu-items/", headers=auth_headers("admin"))
    assert listed.status_code == 200
    assert not any(m["id"] == item.id for m in listed.json())


def test_soft_delete_blocked_when_on_active_order(client, auth_headers, db_session):
    cat = _seed_category(db_session)
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"MSD-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"MSD-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    item = MenuItem(
        name=f"MSD-Active-{suffix}",
        price=9.0,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        order_type="dine_in",
        status="open",
        total_amount=9.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=9.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()

    res = client.delete(f"/api/menu-items/{item.id}", headers=auth_headers("admin"))
    assert res.status_code == 400, res.text
    assert res.json()["detail"] == ACTIVE_ORDER_MSG

    db_session.refresh(item)
    assert item.is_deleted is False


def test_soft_delete_allowed_after_order_paid(client, auth_headers, db_session):
    cat = _seed_category(db_session)
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"MSD-PZ-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"MSD-PT-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    item = MenuItem(
        name=f"MSD-Paid-{suffix}",
        price=11.0,
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
        total_amount=11.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=11.0,
            batch_number=1,
            batch_status="pending",
            item_status="served",
            selected_modifiers=[],
            menu_item_name_at_sale=item.name,
            unit_price_at_sale=item.price,
            category_name_at_sale=cat.name,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/menu-items/{item.id}", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    db_session.refresh(item)
    assert item.is_deleted is True
