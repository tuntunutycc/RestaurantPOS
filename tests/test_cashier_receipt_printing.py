"""Cashier network receipt printing at checkout."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _seed_open_order(db_session, *, total: float = 10.0):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"RCP-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"RCP-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"RCP-Cat-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"RCP-Item-{suffix}",
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
    line = OrderItem(
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
    db_session.add(line)
    db_session.commit()
    db_session.refresh(order)
    return order


def _purge_order(db_session, order_id: int) -> None:
    """Remove checkout residue so session-scoped DB does not pollute report tests."""
    db_session.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    db_session.query(Order).filter(Order.id == order_id).delete()
    db_session.commit()


def test_checkout_issue_receipt_file_backend(client, db_session, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_NAME", "Audit Cafe")
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)

    order = _seed_open_order(db_session, total=12.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 20.0,
                "discount_type": None,
                "discount_value": 0,
                "issue_receipt": True,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body.get("warning") in (None, "")
        out = Path(tmp_path) / "cashier_printer_output.txt"
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "Audit Cafe" in text
        assert f"Order: #{order.id}" in text
        assert "Grand Total:" in text
        assert "Payment:" in text
    finally:
        _purge_order(db_session, order.id)


def test_checkout_printer_connection_error_returns_warning(
    client, db_session, auth_headers, monkeypatch
):
    order = _seed_open_order(db_session, total=8.0)
    try:
        put = client.put(
            "/api/admin/kitchen-printers",
            headers=auth_headers("admin"),
            json={
                "backend": "escpos_network",
                "render_mode": "text",
                "paper_width_px": 576,
                "routes": [
                    {"route_key": "drinks", "host": "192.168.1.101", "port": 9100},
                    {"route_key": "food", "host": "192.168.1.102", "port": 9100},
                    {"route_key": "cashier", "host": "192.168.1.200", "port": 9100},
                ],
            },
        )
        assert put.status_code == 200, put.text
        assert put.json()["backend"] == "escpos_network"

        from services.printing.settings import load_printer_config

        cfg = load_printer_config(db_session)
        assert cfg.backend == "escpos_network", cfg
        assert "cashier" in cfg.routes

        def _boom(*_args, **_kwargs):
            raise ConnectionError("Connection refused")

        monkeypatch.setattr(
            "services.printing.service.send_network_ticket",
            _boom,
        )

        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "mobile_money",
                "amount_tendered": 8.0,
                "issue_receipt": True,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body["payment_method"] == "mobile_money"
        assert body["warning"] == "Receipt printer offline or unreachable"
    finally:
        _purge_order(db_session, order.id)


def test_checkout_skip_receipt_does_not_dispatch(client, db_session, auth_headers, monkeypatch):
    order = _seed_open_order(db_session, total=5.0)
    try:
        mock_dispatch = AsyncMock()
        monkeypatch.setattr(
            "routers.orders.dispatch_cashier_receipt",
            mock_dispatch,
        )
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 5.0,
                "issue_receipt": False,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body.get("warning") is None
        mock_dispatch.assert_not_called()
    finally:
        _purge_order(db_session, order.id)
