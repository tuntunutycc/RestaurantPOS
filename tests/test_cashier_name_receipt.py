"""Cashier display name persisted at checkout and printed on receipts."""

from __future__ import annotations

import uuid
from pathlib import Path

from models import Category, MenuItem, Order, OrderItem, Table, Zone
from services.printing.receipt import build_receipt_text


def _seed_open_order(db_session, *, total: float = 25.0):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"CN-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"CN-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"CN-Cat-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"CN-Item-{suffix}",
        price=total,
        category_id=category.id,
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
        total_amount=total,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=total,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
            unit_tax_at_sale=0.0,
        )
    )
    db_session.commit()
    db_session.refresh(order)
    return order


def _purge(db_session, order_id: int) -> None:
    db_session.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    db_session.query(Order).filter(Order.id == order_id).delete()
    db_session.commit()


def test_checkout_persists_cashier_name(client, db_session, auth_headers):
    order = _seed_open_order(db_session)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 30.0,
                "issue_receipt": False,
                "cashier_name": "  Jane Doe  ",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["cashier_name"] == "Jane Doe"
        db_session.refresh(order)
        assert order.cashier_name == "Jane Doe"
    finally:
        _purge(db_session, order.id)


def test_checkout_blank_cashier_name_stored_as_null(client, db_session, auth_headers):
    order = _seed_open_order(db_session)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 30.0,
                "issue_receipt": False,
                "cashier_name": "   ",
            },
        )
        assert res.status_code == 200, res.text
        assert res.json().get("cashier_name") in (None, "")
        db_session.refresh(order)
        assert order.cashier_name is None
    finally:
        _purge(db_session, order.id)


def test_receipt_text_includes_cashier_when_set():
    text = build_receipt_text(
        order_id=7,
        served_by="waiter1",
        cashier_name="Jane Doe",
        location_label="Table 1",
        items=[{"name": "Tea", "quantity": 1, "subtotal": 5.0}],
        subtotal=5.0,
        discount_amount=0.0,
        tax_amount=0.0,
        grand_total=5.0,
        payment_method="cash",
        created_at="2026-07-13 10:00:00",
    )
    assert "Cashier: Jane Doe" in text
    assert "Served by: waiter1" in text


def test_receipt_text_omits_cashier_when_blank():
    text = build_receipt_text(
        order_id=8,
        served_by="waiter1",
        cashier_name="  ",
        location_label="Table 1",
        items=[{"name": "Tea", "quantity": 1, "subtotal": 5.0}],
        subtotal=5.0,
        discount_amount=0.0,
        tax_amount=0.0,
        grand_total=5.0,
        payment_method="cash",
    )
    assert "Cashier:" not in text


def test_checkout_test_cashier_persists_and_receipt_includes_name(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    """Audit case: cashier_name 'Test Cashier' → DB + receipt text."""
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)

    order = _seed_open_order(db_session, total=18.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 20.0,
                "issue_receipt": True,
                "cashier_name": "Test Cashier",
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["cashier_name"] == "Test Cashier"
        db_session.refresh(order)
        assert order.cashier_name == "Test Cashier"

        out = Path(tmp_path) / "cashier_printer_output.txt"
        assert out.exists()
        receipt = out.read_text(encoding="utf-8")
        assert "Cashier: Test Cashier" in receipt

        unit = build_receipt_text(
            order_id=order.id,
            served_by="waiter1",
            cashier_name=order.cashier_name,
            location_label="Table 1",
            items=[{"name": "Item", "quantity": 1, "subtotal": 18.0}],
            subtotal=18.0,
            discount_amount=0.0,
            tax_amount=0.0,
            grand_total=18.0,
            payment_method="cash",
        )
        assert "Cashier: Test Cashier" in unit
    finally:
        _purge(db_session, order.id)
