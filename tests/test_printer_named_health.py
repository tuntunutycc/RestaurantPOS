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


class _FakeSpooler:
    """Minimal win32print stand-in for probe_windows_queue."""

    def __init__(self, info):
        self._info = info
        self.closed = False

    def OpenPrinter(self, name):
        return "handle"

    def GetPrinter(self, handle, level):
        assert level == 2
        return self._info

    def ClosePrinter(self, handle):
        self.closed = True


def _probe(monkeypatch, info):
    from services.printing.backends import escpos_windows as win_mod

    fake = _FakeSpooler(info)
    monkeypatch.setattr(win_mod, "win32print", fake)
    ok, message = win_mod.probe_windows_queue("POS-80")
    assert fake.closed is True
    return ok, message


def test_probe_windows_queue_ready(monkeypatch):
    ok, message = _probe(
        monkeypatch,
        {"Status": 0, "Attributes": 0, "cJobs": 0, "pPortName": "USB001"},
    )
    assert ok is True
    assert "USB001" in message
    assert "ready" in message


def test_probe_windows_queue_work_offline_attribute_is_offline(monkeypatch):
    """Unplugged USB printers keep Status=0; only the work-offline attribute is set."""
    ok, message = _probe(
        monkeypatch,
        {"Status": 0, "Attributes": 0x400, "cJobs": 0, "pPortName": "USB001"},
    )
    assert ok is False
    assert "offline" in message


def test_probe_windows_queue_status_paper_out_is_offline(monkeypatch):
    ok, message = _probe(monkeypatch, {"Status": 0x10, "Attributes": 0, "cJobs": 0})
    assert ok is False
    assert "paper out" in message


def test_probe_windows_queue_reports_stuck_jobs(monkeypatch):
    ok, message = _probe(monkeypatch, {"Status": 0, "Attributes": 0, "cJobs": 3})
    assert ok is True
    assert "3 job(s) waiting" in message


def test_aggregate_health_ignores_inactive_printers(client, db_session, auth_headers):
    _set_backend(db_session, "escpos_network")
    seed_default_printers(db_session, force=True)
    spare = Printer(name="Spare (off)", host=None, port=9100, role="other", is_active=False)
    db_session.add(spare)
    db_session.commit()
    try:
        res = client.get("/api/printers/health", headers=auth_headers("admin"))
        assert res.status_code == 200, res.text
        names = [n["name"] for n in res.json()["named_printers"]]
        assert "Spare (off)" not in names
        # A single row can still be probed on demand.
        one = client.get(f"/api/printers/{spare.id}/health", headers=auth_headers("admin"))
        assert one.status_code == 200
        assert one.json()["status"] == "offline"
    finally:
        db_session.delete(spare)
        db_session.commit()
        _set_backend(db_session, "file")


def test_print_log_handler_not_duplicated_through_symlinked_path(tmp_path, monkeypatch):
    """Repeated prints must not stack file handlers (one log line per event)."""
    import logging

    from services.printing import print_log

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(print_log, "PRINT_LOG_DIR", link)
    monkeypatch.setattr(print_log, "PRINT_LOG_FILE", link / "print.log")

    parent = logging.getLogger("services.printing")
    alias = logging.getLogger("pos.printing")
    before_parent, before_alias = list(parent.handlers), list(alias.handlers)
    try:
        for _ in range(5):
            print_log.ensure_print_file_logging()
        added = [h for h in parent.handlers if h not in before_parent]
        assert len(added) == 1
        logging.getLogger("services.printing.service").info("one-line-marker")
        added[0].flush()
        assert (link / "print.log").read_text(encoding="utf-8").count("one-line-marker") == 1
    finally:
        for handler in [h for h in parent.handlers if h not in before_parent]:
            parent.removeHandler(handler)
            handler.close()
        for handler in [h for h in alias.handlers if h not in before_alias]:
            alias.removeHandler(handler)
