"""E2E audit integration tests for recent POS release features."""

from __future__ import annotations

import uuid

from models import Category, MenuItem, Order, OrderItem, Printer, Table, Zone
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


def _seed_available_table_with_items(db_session, *, food_price=1000.0, drink_price=500.0):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"E2E-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"E2E-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    drinks_cat = Category(name=f"E2E-Drinks-{suffix}", printer_route="drinks")
    food_cat = Category(name=f"E2E-Food-{suffix}", printer_route="food")
    db_session.add_all([drinks_cat, food_cat])
    db_session.flush()
    drink = MenuItem(
        name=f"E2E-Drink-{suffix}",
        price=drink_price,
        category_id=drinks_cat.id,
        is_available=True,
        modifiers_config=[],
    )
    food = MenuItem(
        name=f"E2E-Food-{suffix}",
        price=food_price,
        category_id=food_cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add_all([drink, food])
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(drink)
    db_session.refresh(food)
    return table, drink, food


def test_waiter_submit_qty_from_cart_controls_marks_table_occupied(
    client, db_session, auth_headers
):
    """Cart +/- yields quantity in submit payload; dine-in table becomes occupied."""
    table, drink, food = _seed_available_table_with_items(db_session)
    assert table.status == "available"

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [
                {
                    "menu_item_id": food.id,
                    "quantity": 3,
                    "selected_modifiers": [],
                },
                {
                    "menu_item_id": drink.id,
                    "quantity": 2,
                    "selected_modifiers": [],
                },
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    order_id = body["id"]
    assert order_id

    db_session.expire_all()
    table = db_session.query(Table).filter(Table.id == table.id).first()
    assert table.status == "occupied"

    details = client.get(
        f"/api/orders/{order_id}/details",
        headers=auth_headers("waiter"),
    )
    assert details.status_code == 200, details.text
    items = details.json()["items"]
    by_name = {i["menu_item_name"]: i["quantity"] for i in items}
    assert by_name[food.name] == 3
    assert by_name[drink.name] == 2

    # Second submit to same table (addon round) — table stays occupied
    append = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [
                {
                    "menu_item_id": food.id,
                    "quantity": 1,
                    "selected_modifiers": [],
                }
            ],
        },
    )
    assert append.status_code == 200, append.text
    db_session.expire_all()
    table = db_session.query(Table).filter(Table.id == table.id).first()
    assert table.status == "occupied"
    details2 = client.get(
        f"/api/orders/{order_id}/details",
        headers=auth_headers("waiter"),
    )
    assert details2.status_code == 200
    food_qty = sum(
        i["quantity"]
        for i in details2.json()["items"]
        if i["menu_item_name"] == food.name
        and str(i.get("item_status") or "").lower() != "cancelled"
    )
    assert food_qty == 4


def test_mixed_order_routes_food_to_kitchen_and_drinks_to_bar(
    client, db_session, auth_headers, monkeypatch
):
    """Food category → kitchen printer host; drinks → bar printer host."""
    seed_kitchen_printer_settings(db_session)
    db_session.query(Printer).delete()
    db_session.commit()
    db_session.add_all(
        [
            Printer(
                name="Kitchen",
                host="10.0.0.10",
                port=9100,
                role="kitchen",
                is_active=True,
            ),
            Printer(
                name="Bar",
                host="10.0.0.20",
                port=9100,
                role="bar",
                is_active=True,
            ),
            Printer(
                name="Cashier",
                host="10.0.0.30",
                port=9100,
                role="cashier",
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    put = client.put(
        "/api/admin/kitchen-printers",
        headers=auth_headers("admin"),
        json={
            "backend": "escpos_network",
            "render_mode": "text",
            "paper_width_px": 576,
            "routes": [],
        },
    )
    assert put.status_code == 200, put.text

    captured_hosts: list[str] = []
    captured_labels: list[str] = []

    def _capture(endpoint, payload, **kwargs):
        captured_hosts.append(endpoint.host)
        captured_labels.append(kwargs.get("route_label") or "")

    monkeypatch.setattr(
        "services.printing.service.print_image_to_network",
        _capture,
    )

    table, drink, food = _seed_available_table_with_items(db_session)
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [
                {"menu_item_id": food.id, "quantity": 1, "selected_modifiers": []},
                {"menu_item_id": drink.id, "quantity": 1, "selected_modifiers": []},
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert "10.0.0.10" in captured_hosts  # kitchen
    assert "10.0.0.20" in captured_hosts  # bar
    assert "food" in captured_labels
    assert "drinks" in captured_labels


def test_split_payment_change_due_5000_mobile_3000_cash_3000(
    client, db_session, auth_headers
):
    """Canonical overpay: total 5000, mobile 3000, cash 3000 → change 1000, paid."""
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"E2E-SP-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"E2E-SP-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    cat = Category(name=f"E2E-SP-C-{suffix}", printer_route="food")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"E2E-SP-I-{suffix}",
        price=5000.0,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        table_number=table.id,
        order_type="dine_in",
        status="open",
        total_amount=5000.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=5000.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
            unit_tax_at_sale=0.0,
        )
    )
    db_session.commit()
    db_session.refresh(order)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "split",
            "mobile_money_amount": 3000.0,
            "cash_amount": 3000.0,
            "issue_receipt": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "paid"
    assert body["change_amount"] == 1000.0
    assert body["mobile_money_amount"] == 3000.0
    assert body["cash_amount"] == 2000.0
    assert body["amount_tendered"] == 3000.0

    db_session.expire_all()
    stored = db_session.query(Order).filter(Order.id == order.id).first()
    assert stored.status == "paid"
    assert stored.change_amount == 1000.0
    table = db_session.query(Table).filter(Table.id == table.id).first()
    assert table.status == "available"


def test_admin_printer_create_persists_and_delete_missing_returns_404(
    client, db_session, auth_headers
):
    seed_default_printers(db_session)

    missing = client.delete(
        "/api/printers/999999",
        headers=auth_headers("admin"),
    )
    assert missing.status_code == 404, missing.text

    create = client.post(
        "/api/printers",
        headers=auth_headers("admin"),
        json={
            "name": "Audit Counter 2",
            "host": "192.168.9.9",
            "port": 9100,
            "role": "cashier",
            "is_active": True,
        },
    )
    assert create.status_code == 200, create.text
    printer_id = create.json()["id"]
    assert create.json()["name"] == "Audit Counter 2"
    assert create.json()["host"] == "192.168.9.9"

    listing = client.get("/api/printers?role=cashier", headers=auth_headers("cashier"))
    assert listing.status_code == 200, listing.text
    assert any(p["id"] == printer_id for p in listing.json())

    db_session.expire_all()
    row = db_session.query(Printer).filter(Printer.id == printer_id).first()
    assert row is not None
    assert row.host == "192.168.9.9"
    assert row.role == "cashier"
