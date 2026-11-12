"""Windows cashier receipt printing (RAW spooler) — mocked win32print path."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

from models import Category, KitchenPrinterSettings, MenuItem, Order, OrderItem, Printer, Table, Zone
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


def _seed_open_order(db_session, *, total: float = 25.5):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"WIN-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"WIN-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"WIN-Cat-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"WIN-Item-{suffix}",
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
    db_session.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    db_session.query(Order).filter(Order.id == order_id).delete()
    db_session.commit()


def _set_windows_backend(db_session) -> None:
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "windows_printer"
    settings.render_mode = "text"
    db_session.commit()


def _restore_file_backend(db_session) -> None:
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()


def test_windows_printers_list_unavailable_without_pywin32(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "routers.kitchen_printers.windows_printing_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "routers.kitchen_printers.list_windows_printers",
        lambda: [],
    )
    res = client.get("/api/admin/windows-printers", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is False
    assert body["printers"] == []
    assert "pywin32" in (body.get("message") or "").lower()


def test_windows_printers_list_role_gate(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "routers.kitchen_printers.windows_printing_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "routers.kitchen_printers.list_windows_printers",
        lambda: ["POSPrinter POS-80(300DPI)"],
    )
    ok = client.get("/api/admin/windows-printers", headers=auth_headers("admin"))
    assert ok.status_code == 200
    assert ok.json()["available"] is True
    assert ok.json()["printers"][0]["name"] == "POSPrinter POS-80(300DPI)"

    denied = client.get("/api/admin/windows-printers", headers=auth_headers("cashier"))
    assert denied.status_code == 403


def test_printer_crud_persists_windows_printer_name(client, db_session, auth_headers):
    seed_default_printers(db_session)
    create = client.post(
        "/api/printers",
        headers=auth_headers("admin"),
        json={
            "name": "Win Cashier",
            "role": "cashier",
            "host": None,
            "port": 9100,
            "windows_printer_name": "  POSPrinter POS-80(300DPI)  ",
            "is_active": True,
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["windows_printer_name"] == "POSPrinter POS-80(300DPI)"
    printer_id = body["id"]

    listing = client.get("/api/printers?role=cashier", headers=auth_headers("cashier"))
    assert listing.status_code == 200
    row = next(p for p in listing.json() if p["id"] == printer_id)
    assert row["windows_printer_name"] == "POSPrinter POS-80(300DPI)"

    clear = client.put(
        f"/api/printers/{printer_id}",
        headers=auth_headers("admin"),
        json={"windows_printer_name": None},
    )
    assert clear.status_code == 200
    assert clear.json()["windows_printer_name"] is None

    client.delete(f"/api/printers/{printer_id}", headers=auth_headers("admin"))


def test_checkout_windows_backend_sends_raw_receipt(
    client, db_session, auth_headers, monkeypatch
):
    _set_windows_backend(db_session)
    seed_default_printers(db_session)
    cashier = (
        db_session.query(Printer)
        .filter(Printer.role == "cashier", Printer.is_active.is_(True))
        .order_by(Printer.id.asc())
        .first()
    )
    assert cashier is not None
    cashier.windows_printer_name = "POSPrinter POS-80(300DPI)"
    db_session.commit()

    sent: list[tuple[str, bytes]] = []

    def _fake_send(name: str, payload: bytes) -> None:
        sent.append((name, payload))

    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        _fake_send,
    )

    order = _seed_open_order(db_session, total=40.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 50.0,
                "discount_type": None,
                "discount_value": 0,
                "issue_receipt": True,
                "printer_id": cashier.id,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body.get("warning") in (None, "")
        assert len(sent) == 1
        assert sent[0][0] == "POSPrinter POS-80(300DPI)"
        text = sent[0][1].decode("utf-8", errors="ignore")
        assert "Grand Total:" in text
        assert "40.00" in text or "40" in text
        assert "Change:" in text or "change" in text.lower()
    finally:
        _purge_order(db_session, order.id)
        _restore_file_backend(db_session)


def test_checkout_windows_missing_queue_soft_fails(
    client, db_session, auth_headers, monkeypatch
):
    _set_windows_backend(db_session)
    seed_default_printers(db_session)
    for row in db_session.query(Printer).filter(Printer.role == "cashier").all():
        row.windows_printer_name = None
    db_session.commit()

    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        MagicMock(side_effect=AssertionError("should not send")),
    )

    order = _seed_open_order(db_session, total=15.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 20.0,
                "issue_receipt": True,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body.get("warning")
    finally:
        _purge_order(db_session, order.id)
        _restore_file_backend(db_session)


def test_kitchen_ticket_windows_backend_falls_back_to_file_without_lan_host(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    _set_windows_backend(db_session)
    seed_default_printers(db_session)
    for row in db_session.query(Printer).filter(Printer.role == "kitchen").all():
        row.host = None
    db_session.commit()
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("PRINTER_FOOD_HOST", raising=False)
    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        MagicMock(side_effect=AssertionError("kitchen must not use Windows RAW")),
    )

    import asyncio

    from services.printing.service import dispatch_kitchen_ticket

    try:
        asyncio.run(
            dispatch_kitchen_ticket(
                "food",
                {
                    "item_name": "Test Mohinga",
                    "quantity": 1,
                    "note": None,
                    "table_number": 1,
                    "order_id": 99,
                    "date": "2026-11-05",
                },
                db=db_session,
            )
        )
        out = Path(tmp_path) / "food_printer_output.txt"
        assert out.exists()
        assert "Test Mohinga" in out.read_text(encoding="utf-8")
    finally:
        _restore_file_backend(db_session)


def test_kitchen_ticket_windows_backend_keeps_lan_when_host_set(
    client, db_session, auth_headers, monkeypatch
):
    _set_windows_backend(db_session)
    seed_default_printers(db_session)
    kitchen = (
        db_session.query(Printer)
        .filter(Printer.role == "kitchen", Printer.is_active.is_(True))
        .order_by(Printer.id.asc())
        .first()
    )
    assert kitchen is not None
    kitchen.host = "192.168.1.50"
    kitchen.port = 9100
    db_session.commit()

    sent: list[tuple[str, int]] = []

    def _fake_print_image_to_network(endpoint, payload, *, timeout_seconds=5.0, route_label="printer"):
        sent.append((endpoint.host, int(endpoint.port)))

    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        MagicMock(side_effect=AssertionError("kitchen must not use Windows RAW")),
    )
    monkeypatch.setattr(
        "services.printing.service.print_image_to_network",
        _fake_print_image_to_network,
    )

    import asyncio

    from services.printing.service import dispatch_kitchen_ticket

    try:
        asyncio.run(
            dispatch_kitchen_ticket(
                "food",
                {
                    "item_name": "LAN Kitchen Item",
                    "quantity": 2,
                    "note": None,
                    "table_number": 3,
                    "order_id": 42,
                    "date": "2026-11-05",
                },
                db=db_session,
            )
        )
        assert sent == [("192.168.1.50", 9100)]
    finally:
        _restore_file_backend(db_session)


def test_windows_print_error_messages_are_actionable(monkeypatch):
    from services.printing.backends import escpos_windows as win_mod

    class FakeWin32:
        PRINTER_ENUM_LOCAL = 1
        PRINTER_ENUM_CONNECTIONS = 2

        @staticmethod
        def OpenPrinter(name):
            raise OSError("The printer is offline")

    monkeypatch.setattr(win_mod, "win32print", FakeWin32)
    try:
        win_mod.send_raw_to_windows_printer("POSPrinter POS-80(300DPI)", b"test")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "offline" in msg or "disconnected" in msg
        assert "posprinter" in msg.lower()


def test_put_kitchen_printers_accepts_windows_backend(client, db_session, auth_headers):
    seed_kitchen_printer_settings(db_session)
    try:
        res = client.put(
            "/api/admin/kitchen-printers",
            headers=auth_headers("admin"),
            json={
                "backend": "windows_printer",
                "render_mode": "text",
                "paper_width_px": 576,
                "routes": [],
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["backend"] == "windows_printer"
        get_res = client.get("/api/admin/kitchen-printers", headers=auth_headers("admin"))
        assert get_res.json()["backend"] == "windows_printer"
    finally:
        _restore_file_backend(db_session)
