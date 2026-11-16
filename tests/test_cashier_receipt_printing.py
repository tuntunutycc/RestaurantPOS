"""Cashier network receipt printing at checkout + dynamic printers."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

from models import Category, KitchenPrinterSettings, MenuItem, Order, OrderItem, Printer, Table, Zone
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


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
    # Bulk deletes skip the ORM cascade; SQLite reuses ids, so a later order
    # would otherwise inherit these print jobs.
    from models import PrintJob

    db_session.query(PrintJob).filter(PrintJob.order_id == order_id).delete()
    db_session.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    db_session.query(Order).filter(Order.id == order_id).delete()
    db_session.commit()


def test_checkout_issue_receipt_file_backend(client, db_session, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_NAME", "Audit Cafe")
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()

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


def test_checkout_file_backend_with_printer_id_no_host_writes_txt(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    """File backend + selected cashier printer without host still archives receipt txt."""
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_NAME", "File Test Cafe")
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()

    cashier = (
        db_session.query(Printer)
        .filter(Printer.role == "cashier", Printer.is_active.is_(True))
        .order_by(Printer.id.asc())
        .first()
    )
    assert cashier is not None
    cashier.host = None
    cashier.windows_printer_name = None
    db_session.commit()

    order = _seed_open_order(db_session, total=15.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 20.0,
                "issue_receipt": True,
                "printer_id": cashier.id,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "paid"
        assert body.get("warning") in (None, "")
        out = Path(tmp_path) / "cashier_printer_output.txt"
        assert out.exists(), "expected cashier_printer_output.txt for file-backend testing"
        text = out.read_text(encoding="utf-8")
        assert "File Test Cafe" in text
        assert f"Order: #{order.id}" in text
        assert "Grand Total:" in text
    finally:
        _purge_order(db_session, order.id)


def test_checkout_receipt_footer_shows_base_discount_tax_breakdown(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    """Receipt footer: Subtotal=base+mods, Discount=item, Tax separate, Grand=payable."""
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_NAME", "Breakdown Cafe")
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()

    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"BD-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"BD-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"BD-Cat-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name="မုန့်ဟင်းခါး",
        price=2000.0,
        discount_type="fixed",
        discount_value=200.0,
        tax_type="fixed",
        tax_value=1.8,
        category_id=category.id,
        is_available=True,
        modifiers_config=[
            {
                "group": "",
                "is_required": False,
                "options": [{"name": "ပဲကြော်", "price": 100.0}],
            }
        ],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        table_number=table.id,
        order_type="dine_in",
        status="open",
        total_amount=1901.8,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=1901.8,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[{"name": "ပဲကြော်", "price": 100.0, "quantity": 1}],
            unit_price_at_sale=2000.0,
            unit_discount_at_sale=200.0,
            unit_tax_at_sale=1.8,
            menu_item_name_at_sale="မုန့်ဟင်းခါး",
            note="နံနံပင်ရှောင်",
            special_instructions="နံနံပင်ရှောင်",
        )
    )
    db_session.commit()
    db_session.refresh(order)

    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 2000.0,
                "discount_type": None,
                "discount_value": 0,
                "issue_receipt": True,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "paid"
        text = (Path(tmp_path) / "cashier_printer_output.txt").read_text(encoding="utf-8")
        assert "Subtotal:     2100.00" in text
        assert "Discount:    -200.00" in text
        assert "Tax:          1.80" in text
        assert "Grand Total:  1901.80" in text
        assert "+ ပဲကြော်" in text
        assert "100.00" in text
        # Review #18: item line shows pre-tax amount (1900), not tax-inclusive 1901.80
        assert "    1900.00" in text
        assert "    1901.80" not in text
        # Review #24: note on printed receipt
        assert "*** Note: နံနံပင်ရှောင် ***" in text
    finally:
        _purge_order(db_session, order.id)


def test_receipt_text_includes_note_and_pre_tax_line_amount():
    """Review #24 note on receipt; #18 line amount excludes unit tax."""
    from services.printing.receipt import build_receipt_text

    text = build_receipt_text(
        order_id=99,
        served_by="waiter1",
        location_label="Table 1",
        items=[
            {
                "name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "subtotal": 1901.8,
                "unit_tax_at_sale": 1.8,
                "note": "အစပ်လျှော့",
                "selected_modifiers": [{"name": "ပဲကြော်", "price": 100.0, "quantity": 1}],
                "is_takeaway": False,
            }
        ],
        subtotal=2100.0,
        discount_amount=200.0,
        tax_amount=1.8,
        grand_total=1901.8,
        payment_method="cash",
        amount_tendered=2000.0,
        change_amount=98.2,
    )
    assert "*** Note: အစပ်လျှော့ ***" in text
    assert "+ ပဲကြော်  100.00" in text
    assert "    1900.00" in text
    assert "Tax:          1.80" in text
    assert "Grand Total:  1901.80" in text


def test_checkout_printer_connection_error_records_failed_job(
    client, db_session, auth_headers, monkeypatch
):
    seed_default_printers(db_session, force=True)
    cashier = (
        db_session.query(Printer)
        .filter(Printer.role == "cashier")
        .order_by(Printer.id.asc())
        .first()
    )
    assert cashier is not None
    cashier.host = "192.168.1.200"
    cashier.port = 9100
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

    def _boom(*_args, **_kwargs):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr("services.printing.service.send_network_ticket", _boom)
    monkeypatch.setattr("services.printing.service.print_image_to_network", _boom)

    order = _seed_open_order(db_session, total=8.0)
    try:
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
        # Checkout no longer waits for the printer: the receipt is queued and
        # the failure (with its real reason) is recorded on the print job.
        assert body["warning"] is None
        jobs = client.get(
            f"/api/orders/{order.id}/print-jobs", headers=auth_headers("cashier")
        ).json()
        assert [(j["kind"], j["print_status"]) for j in jobs] == [("receipt", "failed")]
        assert jobs[0]["error_message"] == "Connection refused"
    finally:
        _purge_order(db_session, order.id)


def test_checkout_skip_receipt_does_not_dispatch(client, db_session, auth_headers, monkeypatch):
    order = _seed_open_order(db_session, total=5.0)
    try:
        mock_dispatch = AsyncMock()
        monkeypatch.setattr("services.printing.print_jobs.dispatch_cashier_receipt", mock_dispatch)
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
        assert res.json().get("warning") is None
        mock_dispatch.assert_not_called()
    finally:
        _purge_order(db_session, order.id)


def test_list_cashier_printers_api(client, db_session, auth_headers):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    if db_session.query(Printer).filter(Printer.role == "cashier").count() < 2:
        db_session.add(
            Printer(
                name="Counter 2",
                host="192.168.1.210",
                port=9100,
                role="cashier",
                is_active=True,
            )
        )
        db_session.commit()

    res = client.get("/api/printers?role=cashier", headers=auth_headers("cashier"))
    assert res.status_code == 200, res.text
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert all(r.get("role") == "cashier" for r in rows)

    bad = client.get("/api/printers?role=food", headers=auth_headers("cashier"))
    assert bad.status_code == 400

    waiter = client.get("/api/printers?role=cashier", headers=auth_headers("waiter"))
    assert waiter.status_code == 403


def test_checkout_with_printer_id_targets_selected_printer(
    client, db_session, auth_headers, monkeypatch
):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    printer = Printer(
        name="Terminal A",
        host="10.0.0.55",
        port=9100,
        role="cashier",
        is_active=True,
    )
    db_session.add(printer)
    db_session.commit()
    db_session.refresh(printer)

    captured = {}

    def _capture(endpoint, payload, **kwargs):
        captured["host"] = endpoint.host
        captured["port"] = endpoint.port

    monkeypatch.setattr("services.printing.service.print_image_to_network", _capture)
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

    order = _seed_open_order(db_session, total=7.0)
    try:
        res = client.put(
            f"/api/orders/{order.id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 7.0,
                "issue_receipt": True,
                "printer_id": printer.id,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "paid"
        assert captured.get("host") == "10.0.0.55"
        assert captured.get("port") == 9100
    finally:
        _purge_order(db_session, order.id)


def test_checkout_invalid_printer_id_returns_400(client, db_session, auth_headers):
    order = _seed_open_order(db_session, total=6.0)
    order_id = order.id
    try:
        res = client.put(
            f"/api/orders/{order_id}/checkout",
            headers=auth_headers("cashier"),
            json={
                "payment_method": "cash",
                "amount_tendered": 6.0,
                "issue_receipt": True,
                "printer_id": 999999,
            },
        )
        assert res.status_code == 400, res.text
        db_session.expire_all()
        refreshed = db_session.query(Order).filter(Order.id == order_id).first()
        assert refreshed is not None
        assert refreshed.status != "paid"
    finally:
        _purge_order(db_session, order_id)


def test_printer_crud_create_update_delete(client, db_session, auth_headers):
    seed_default_printers(db_session, force=True)
    create = client.post(
        "/api/printers",
        headers=auth_headers("admin"),
        json={
            "name": "Bar Station",
            "host": "10.0.0.77",
            "port": 9100,
            "role": "bar",
            "is_active": True,
        },
    )
    assert create.status_code == 200, create.text
    printer_id = create.json()["id"]
    assert create.json()["role"] == "bar"

    update = client.put(
        f"/api/printers/{printer_id}",
        headers=auth_headers("admin"),
        json={"name": "Bar Station 2", "host": "10.0.0.78"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "Bar Station 2"
    assert update.json()["host"] == "10.0.0.78"

    listing = client.get("/api/printers", headers=auth_headers("admin"))
    assert listing.status_code == 200
    assert any(p["id"] == printer_id for p in listing.json())

    delete = client.delete(f"/api/printers/{printer_id}", headers=auth_headers("admin"))
    assert delete.status_code == 200, delete.text
    listing2 = client.get("/api/printers", headers=auth_headers("admin"))
    assert all(p["id"] != printer_id for p in listing2.json())


def test_seed_default_printers_creates_cashier_and_kitchen(db_session):
    db_session.query(Printer).delete()
    db_session.commit()
    seed_default_printers(db_session, force=True)
    roles = {p.role for p in db_session.query(Printer).all()}
    assert "cashier" in roles
    assert "kitchen" in roles
    # Fresh seed without drinks host should not force a bar printer
    assert db_session.query(Printer).count() == 2


def test_delete_all_printers_does_not_reseed_on_list(client, db_session, auth_headers):
    """Admin wipe must stick — GET /api/printers must not recreate defaults."""
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    assert db_session.query(Printer).count() >= 2

    for row in db_session.query(Printer).all():
        res = client.delete(f"/api/printers/{row.id}", headers=auth_headers("admin"))
        assert res.status_code == 200, res.text

    assert db_session.query(Printer).count() == 0
    listing = client.get("/api/printers", headers=auth_headers("admin"))
    assert listing.status_code == 200, listing.text
    assert listing.json() == []
    assert db_session.query(Printer).count() == 0
    # Shared in-memory DB: restore defaults for later tests
    seed_default_printers(db_session, force=True)
