"""
Integration tests: soft-deleted menu items and deleted categories must not
break FK integrity or erase historical sales / order receipt data.
"""

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone
from routers.menu import ARCHIVED_CATEGORY_NAME


def _seed_table(db_session, suffix: str) -> Table:
    zone = Zone(name=f"SI-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"SI-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table


def test_sales_and_order_history_survive_menu_and_category_deletion(
    client, db_session, auth_headers
):
    """
    End-to-end proof:
    create category + item → order → pay → soft-delete item → delete category
    → sales reports and order receipt still show correct name, price, revenue.
    """
    suffix = uuid.uuid4().hex[:8]
    item_name = f"Integrity-Dish-{suffix}"
    category_name = f"Integrity-Cat-{suffix}"
    unit_price = 18.50
    quantity = 2
    line_subtotal = round(unit_price * quantity, 2)

    # 1–2. Create category and menu item via admin API.
    cat_res = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": category_name, "printer_route": "food"},
    )
    assert cat_res.status_code == 200, cat_res.text
    category_id = cat_res.json()["id"]

    item_res = client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json={
            "name": item_name,
            "price": unit_price,
            "category_id": category_id,
            "description": "",
            "image_url": None,
            "is_available": True,
            "is_promoted": False,
            "modifiers_config": [],
        },
    )
    assert item_res.status_code == 200, item_res.text
    menu_item_id = item_res.json()["id"]

    table = _seed_table(db_session, suffix)

    # 3. Place order (waiter) — snapshots written at sale time.
    submit = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
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
    assert submit.status_code == 200, submit.text
    order_id = submit.json()["id"]
    assert submit.json()["total_amount"] == line_subtotal

    # 4. Pay order (cashier) — becomes historical sales data.
    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "cash",
            "amount_tendered": 100.0,
            "discount_type": None,
            "discount_value": 0,
        },
    )
    assert checkout.status_code == 200, checkout.text
    paid_total = float(checkout.json()["total_amount"])
    assert paid_total >= line_subtotal

    # Baseline: order receipt before any deletion.
    pre_delete_details = client.get(
        f"/api/orders/{order_id}/details",
        headers=auth_headers("cashier"),
    )
    assert pre_delete_details.status_code == 200, pre_delete_details.text
    pre_line = pre_delete_details.json()["items"][0]
    assert pre_line["menu_item_name"] == item_name
    assert pre_line["quantity"] == quantity
    assert float(pre_line["subtotal"]) == line_subtotal

    summary_before = client.get(
        "/api/reports/summary/today",
        headers=auth_headers("admin"),
    )
    assert summary_before.status_code == 200, summary_before.text
    sales_before = float(summary_before.json()["total_sales"])

    # 5. Soft-delete menu item.
    soft_delete = client.delete(
        f"/api/menu-items/{menu_item_id}",
        headers=auth_headers("admin"),
    )
    assert soft_delete.status_code == 200, soft_delete.text

    db_session.expire_all()
    soft_item = db_session.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
    assert soft_item is not None, "Menu item row must remain (soft delete, not hard delete)"
    assert soft_item.is_deleted is True

    order_line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == order_id, OrderItem.menu_item_id == menu_item_id)
        .first()
    )
    assert order_line is not None, "OrderItem FK to menu_items must remain intact"
    assert order_line.menu_item_name_at_sale == item_name
    assert float(order_line.unit_price_at_sale) == unit_price
    assert order_line.category_name_at_sale == category_name

    # Item hidden from active menu list only.
    menu_list = client.get("/api/menu-items/", headers=auth_headers("admin"))
    assert menu_list.status_code == 200
    assert not any(m["id"] == menu_item_id for m in menu_list.json())

    # 6. Delete category (only soft-deleted items remain).
    cat_delete = client.delete(
        f"/api/categories/{category_id}",
        headers=auth_headers("admin"),
    )
    assert cat_delete.status_code == 200, cat_delete.text

    db_session.expire_all()
    category_gone = db_session.query(Category).filter(Category.id == category_id).first()
    assert category_gone is None, "Category row removed after soft-deleted items relocated"

    item_after_cat_delete = db_session.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
    assert item_after_cat_delete is not None, "Menu item with order history must not be hard-deleted"
    archived = db_session.query(Category).filter(Category.name == ARCHIVED_CATEGORY_NAME).first()
    assert archived is not None
    assert item_after_cat_delete.category_id == archived.id

    order_line_after = (
        db_session.query(OrderItem)
        .filter(OrderItem.id == order_line.id)
        .first()
    )
    assert order_line_after.menu_item_id == menu_item_id

    # 7. Assert historical sales and receipt data unchanged.
    details = client.get(
        f"/api/orders/{order_id}/details",
        headers=auth_headers("cashier"),
    )
    assert details.status_code == 200, details.text
    line = details.json()["items"][0]
    assert line["menu_item_name"] == item_name
    assert line["quantity"] == quantity
    assert float(line["subtotal"]) == line_subtotal

    summary_after = client.get(
        "/api/reports/summary/today",
        headers=auth_headers("admin"),
    )
    assert summary_after.status_code == 200, summary_after.text
    assert float(summary_after.json()["total_sales"]) >= sales_before
    assert int(summary_after.json()["total_orders"]) >= 1

    top_items = client.get("/api/reports/top-items", headers=auth_headers("admin"))
    assert top_items.status_code == 200, top_items.text
    assert any(row["item_name"] == item_name for row in top_items.json())

    category_sales = client.get("/api/reports/category-sales", headers=auth_headers("admin"))
    assert category_sales.status_code == 200, category_sales.text
    cat_row = next(
        (r for r in category_sales.json() if r["category_name"] == category_name),
        None,
    )
    assert cat_row is not None, "Category sales must use snapshot name, not archive bucket"
    assert float(cat_row["total_sales"]) >= line_subtotal
