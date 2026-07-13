"""Split payment checkout math and persistence."""

from __future__ import annotations

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_open_order(db_session, *, total: float = 150.0):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"SPL-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"SPL-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"SPL-Cat-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"SPL-Item-{suffix}",
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


def test_split_payment_cash_and_mobile(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total=150.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "split",
                "cash_amount": 100.0,
                "mobile_money_amount": 50.0,
                "amount_tendered": 100.0,
                "issue_receipt": False,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body["payment_method"] == "split"
        assert body["cash_amount"] == 100.0
        assert body["mobile_money_amount"] == 50.0
        assert body["change_amount"] == 0.0
        db_session.expire_all()
        stored = db_session.query(Order).filter(Order.id == order.id).first()
        assert stored.cash_amount == 100.0
        assert stored.mobile_money_amount == 50.0
        assert stored.payment_method == "split"
    finally:
        _purge(db_session, order.id)


def test_split_payment_insufficient_returns_400(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total=150.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "cash_amount": 40.0,
                "mobile_money_amount": 50.0,
                "issue_receipt": False,
            },
        )
        assert res.status_code == 400, res.text
        db_session.expire_all()
        stored = db_session.query(Order).filter(Order.id == order.id).first()
        assert stored.status != "paid"
    finally:
        _purge(db_session, order.id)


def test_split_payment_overpay_change_due_5000(client, db_session, auth_headers):
    """Total 5000, Mobile 3000, Cash tendered 3000 → Change Due 1000."""
    order = _seed_open_order(db_session, total=5000.0)
    try:
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
        assert body["payment_method"] == "split"
        assert body["mobile_money_amount"] == 3000.0
        assert body["cash_amount"] == 2000.0  # applied to bill
        assert body["amount_tendered"] == 3000.0  # cash handed over
        assert body["change_amount"] == 1000.0
    finally:
        _purge(db_session, order.id)


def test_split_receipt_shows_change_due_lines(tmp_path, monkeypatch):
    from services.printing.receipt import build_receipt_text

    text = build_receipt_text(
        order_id=42,
        served_by="cashier1",
        location_label="Table A1",
        items=[{"name": "Tea", "quantity": 1, "subtotal": 5000.0}],
        subtotal=5000.0,
        discount_amount=0.0,
        tax_amount=0.0,
        grand_total=5000.0,
        payment_method="split",
        amount_tendered=3000.0,
        change_amount=1000.0,
        cash_amount=2000.0,
        mobile_money_amount=3000.0,
    )
    assert "Grand Total:  5000.00" in text
    assert "Paid via Mobile: 3000.00" in text
    assert "Tendered Cash:   3000.00" in text
    assert "Change Due:      1000.00" in text


def test_legacy_full_cash_still_sets_amount_columns(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total=80.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 100.0,
                "issue_receipt": False,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["payment_method"] == "cash"
        assert body["cash_amount"] == 80.0
        assert body["mobile_money_amount"] == 0.0
        assert body["change_amount"] == 20.0
    finally:
        _purge(db_session, order.id)


def test_split_payment_counts_in_sales_breakdown(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total=150.0)
    try:
        before = client.get(
            "/api/analytics/sales-breakdown",
            headers=auth_headers("admin"),
        ).json()
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "cash_amount": 100.0,
                "mobile_money_amount": 50.0,
                "issue_receipt": False,
            },
        )
        assert res.status_code == 200, res.text
        after = client.get(
            "/api/analytics/sales-breakdown",
            headers=auth_headers("admin"),
        ).json()
        assert float(after["today"]["cash"]) - float(before["today"]["cash"]) == 100.0
        assert (
            float(after["today"]["mobile_money"]) - float(before["today"]["mobile_money"])
            == 50.0
        )
    finally:
        _purge(db_session, order.id)
