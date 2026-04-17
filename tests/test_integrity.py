import uuid
from datetime import datetime

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_paid_order_for_table(db_session):
    suffix = uuid.uuid4().hex[:8]

    zone = Zone(name=f"I-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"I-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()

    category = Category(name=f"I-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()

    menu_item = MenuItem(
        name=f"I-Item-{suffix}",
        price=10.00,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.flush()

    order = Order(
        table_id=table.id,
        table_number=9,
        order_type="dine_in",
        status="paid",
        total_amount=10.50,
        tax_amount=0.50,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=1,
        subtotal=10.00,
        batch_number=1,
        batch_status="pending",
        item_status="served",
        selected_modifiers=[],
    )
    db_session.add(order_item)
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(order)
    db_session.refresh(order_item)
    return table, order, order_item


def test_table_delete_preserves_order_history_and_sales_summary(client, db_session, auth_headers):
    table, order, order_item = _seed_paid_order_for_table(db_session)

    delete_res = client.delete(
        f"/api/tables/{table.id}",
        headers=auth_headers("admin"),
    )
    assert delete_res.status_code == 200, delete_res.text

    # Order row and line-items must survive table deletion.
    persisted_order = db_session.query(Order).filter(Order.id == order.id).first()
    assert persisted_order is not None
    assert persisted_order.table_id is None
    assert float(persisted_order.total_amount) == 10.50
    assert float(getattr(persisted_order, "tax_amount", 0.0) or 0.0) == 0.50

    persisted_items = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    assert len(persisted_items) == 1
    assert persisted_items[0].id == order_item.id
    assert float(persisted_items[0].subtotal) == 10.00

    # Daily summary should still include detached paid order.
    summary_res = client.get(
        "/api/reports/summary/today",
        headers=auth_headers("cashier"),
    )
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert float(summary["total_sales"]) >= 10.50
    assert int(summary["total_orders"]) >= 1
