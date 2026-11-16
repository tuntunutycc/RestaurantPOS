"""Per-printer health probe (Check button) + richer health payload."""

from __future__ import annotations

from models import KitchenPrinterSettings, Printer
from services.printing.health import check_named_printer_health
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


def _set_backend(db_session, backend: str):
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = backend
    settings.render_mode = "text"
    db_session.commit()


def test_named_health_file_backend_skipped(client, db_session, auth_headers):
    _set_backend(db_session, "file")
    seed_default_printers(db_session, force=True)
    row = db_session.query(Printer).filter(Printer.role == "cashier").first()
    res = client.get(f"/api/printers/{row.id}/health", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "skipped"
    assert body["online"] is True
    assert body["backend"] == "file"
    assert "File backend" in body["message"]


def test_named_health_windows_missing_queue_offline(client, db_session, auth_headers):
    _set_backend(db_session, "windows_printer")
    seed_default_printers(db_session, force=True)
    cashier = db_session.query(Printer).filter(Printer.role == "cashier").first()
    cashier.windows_printer_name = None
    db_session.commit()
    res = client.get(f"/api/printers/{cashier.id}/health", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "offline"
    assert body["online"] is False
    assert "queue" in body["message"].lower()


def test_named_health_windows_queue_probe_mocked(client, db_session, auth_headers, monkeypatch):
    _set_backend(db_session, "windows_printer")
    seed_default_printers(db_session, force=True)
    cashier = db_session.query(Printer).filter(Printer.role == "cashier").first()
    cashier.windows_printer_name = "POSPrinter POS-80"
    db_session.commit()

    monkeypatch.setattr(
        "services.printing.health.probe_windows_queue",
        lambda name: (True, f"Windows queue '{name}' OK (ready)"),
    )
    res = client.get(f"/api/printers/{cashier.id}/health", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["online"] is True
    assert body["status"] == "online"
    assert body["target"] == "windows_queue=POSPrinter POS-80"


def test_named_health_lan_unreachable(client, db_session, auth_headers):
    _set_backend(db_session, "escpos_network")
    seed_default_printers(db_session, force=True)
    kitchen = db_session.query(Printer).filter(Printer.role == "kitchen").first()
    kitchen.host = "127.0.0.1"
    kitchen.port = 1
    db_session.commit()
    res = client.get(f"/api/printers/{kitchen.id}/health", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "offline"
    assert body["online"] is False
    assert "127.0.0.1" in (body["target"] or "")


def test_named_health_role_gate(client, db_session, auth_headers):
    _set_backend(db_session, "file")
    seed_default_printers(db_session, force=True)
    row = db_session.query(Printer).first()
    denied = client.get(f"/api/printers/{row.id}/health", headers=auth_headers("cashier"))
    assert denied.status_code == 403


def test_named_health_not_found(client, auth_headers):
    res = client.get("/api/printers/999999/health", headers=auth_headers("admin"))
    assert res.status_code == 404


def test_aggregate_health_includes_named_for_admin(client, db_session, auth_headers):
    _set_backend(db_session, "file")
    seed_default_printers(db_session, force=True)
    admin = client.get("/api/printers/health", headers=auth_headers("admin"))
    assert admin.status_code == 200
    assert isinstance(admin.json().get("named_printers"), list)
    assert len(admin.json()["named_printers"]) >= 1

    waiter = client.get("/api/printers/health", headers=auth_headers("waiter"))
    assert waiter.status_code == 200
    assert waiter.json().get("named_printers") == []


def test_check_named_printer_health_helper_raises_missing(db_session):
    try:
        check_named_printer_health(db_session, 999999)
        assert False, "expected LookupError"
    except LookupError:
        pass
