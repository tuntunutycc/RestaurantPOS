"""Admin Print Test for named printers."""

from __future__ import annotations

from models import KitchenPrinterSettings, Printer
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


def _restore_file_backend(db_session):
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if settings:
        settings.backend = "file"
        settings.render_mode = "text"
        db_session.commit()


def test_printer_test_print_role_gate(client, db_session, auth_headers):
    seed_default_printers(db_session, force=True)
    row = db_session.query(Printer).filter(Printer.role == "cashier").first()
    assert row is not None
    denied = client.post(
        f"/api/printers/{row.id}/test-print",
        headers=auth_headers("cashier"),
    )
    assert denied.status_code == 403


def test_printer_test_print_not_found(client, auth_headers):
    res = client.post(
        "/api/printers/999999/test-print",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 404


def test_printer_test_print_file_backend_succeeds(client, db_session, auth_headers, tmp_path, monkeypatch):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    _restore_file_backend(db_session)
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))

    kitchen = db_session.query(Printer).filter(Printer.role == "kitchen").first()
    assert kitchen is not None
    res = client.post(
        f"/api/printers/{kitchen.id}/test-print",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["printer_id"] == kitchen.id
    assert body["role"] == "kitchen"
    assert body["backend"] == "file"
    assert body["target"] == "file"
    assert "TEST PRINT" in body["message"] or "Test print" in body["message"]

    out = tmp_path / "food_printer_output.txt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "TEST PRINT" in text
    assert kitchen.name in text


def test_printer_test_print_windows_cashier_uses_row_queue(
    client, db_session, auth_headers, monkeypatch
):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "windows_printer"
    settings.render_mode = "text"
    db_session.commit()

    cashier = db_session.query(Printer).filter(Printer.role == "cashier").first()
    cashier.windows_printer_name = "POSPrinter POS-80(300DPI)"
    db_session.commit()

    sent: list[tuple[str, bytes]] = []

    def _fake_send(queue: str, payload: bytes) -> None:
        sent.append((queue, payload))

    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        _fake_send,
    )
    try:
        res = client.post(
            f"/api/printers/{cashier.id}/test-print",
            headers=auth_headers("admin"),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["target"] == "windows_queue=POSPrinter POS-80(300DPI)"
        assert sent and sent[0][0] == "POSPrinter POS-80(300DPI)"
        assert sent[0][1]  # non-empty payload
    finally:
        _restore_file_backend(db_session)


def test_printer_test_print_lan_kitchen_uses_row_host(
    client, db_session, auth_headers, monkeypatch
):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "escpos_network"
    settings.render_mode = "text"
    db_session.commit()

    kitchen = db_session.query(Printer).filter(Printer.role == "kitchen").first()
    kitchen.host = "192.168.1.77"
    kitchen.port = 9100
    db_session.commit()

    sent: list[tuple[str, int]] = []

    def _fake_lan(endpoint, payload, *, timeout_seconds=5.0, route_label="printer"):
        sent.append((endpoint.host, endpoint.port))

    monkeypatch.setattr(
        "services.printing.service.print_image_to_network",
        _fake_lan,
    )
    # text mode uses send_network_ticket path when no override image — patch both
    def _fake_send_network(config, route, escpos_payload, *, timeout_seconds=None):
        endpoint = config.routes.get(route)
        if endpoint is None:
            raise RuntimeError("missing")
        sent.append((endpoint.host, endpoint.port))

    monkeypatch.setattr(
        "services.printing.service.send_network_ticket",
        _fake_send_network,
    )
    try:
        res = client.post(
            f"/api/printers/{kitchen.id}/test-print",
            headers=auth_headers("admin"),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["target"] == "lan=192.168.1.77:9100"
        assert sent and sent[0] == ("192.168.1.77", 9100)
    finally:
        _restore_file_backend(db_session)


def test_printer_test_print_windows_cashier_missing_queue_502(client, db_session, auth_headers):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session, force=True)
    settings = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    settings.backend = "windows_printer"
    db_session.commit()
    cashier = db_session.query(Printer).filter(Printer.role == "cashier").first()
    cashier.windows_printer_name = None
    db_session.commit()
    try:
        res = client.post(
            f"/api/printers/{cashier.id}/test-print",
            headers=auth_headers("admin"),
        )
        assert res.status_code == 502
        assert "Windows queue" in res.json()["detail"] or "queue" in res.json()["detail"].lower()
    finally:
        _restore_file_backend(db_session)
