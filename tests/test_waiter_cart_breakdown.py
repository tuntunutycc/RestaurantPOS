"""Waiter order details price breakdown fields."""

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_taxed_order(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"WB-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"WB-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"WB-C-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"WB-I-{suffix}",
        price=1000.0,
        tax_type="percentage",
        tax_value=5.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        order_type="dine_in",
        status="open",
        total_amount=1050.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=1,
            subtotal=1050.0,
            unit_price_at_sale=1000.0,
            unit_tax_at_sale=50.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()
    db_session.refresh(order)
    return order


def test_order_details_includes_price_breakdown(client, db_session, auth_headers):
    order = _seed_taxed_order(db_session)

    res = client.get(f"/api/orders/{order.id}/details", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["breakdown_subtotal"] == 1000.0
    assert body["breakdown_discount_total"] == 0.0
    assert body["breakdown_tax_total"] == 50.0
    assert body["breakdown_grand_total"] == 1050.0
    assert body["items"][0]["unit_price_at_sale"] == 1000.0
    assert body["items"][0]["unit_tax_at_sale"] == 50.0
