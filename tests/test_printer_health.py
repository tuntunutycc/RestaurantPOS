"""Kitchen printer online probe — warn only, never blocks orders."""

from __future__ import annotations

from unittest.mock import AsyncMock

from models import Category, KitchenPrinterSettings, MenuItem, Printer
from services.printing.health import (
    RouteHealth,
    check_kitchen_printers_health,
    probe_tcp,
    warning_for_offline_routes,
)
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings


def test_file_backend_health_is_skipped_online(db_session):
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = "file"
    db_session.commit()

    results = check_kitchen_printers_health(db_session)
    assert results
    assert all(r.status == "skipped" for r in results)
    assert all(r.online for r in results)
    assert warning_for_offline_routes(results) is None


def test_probe_tcp_localhost_closed_port_offline():
    ok, detail = probe_tcp("127.0.0.1", 1, timeout_seconds=0.3)
    assert ok is False
    assert detail


def test_printers_health_endpoint_file_backend(client, db_session, auth_headers):
    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = "file"
    db_session.commit()

    res = client.get("/api/printers/health", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["backend"] == "file"
    assert body["all_online"] is True
    assert body["warning"] is None
    assert len(body["printers"]) >= 2


def test_submit_with_offline_lan_warns_but_saves(
    client, db_session, auth_headers, monkeypatch
):
    seed_kitchen_printer_settings(db_session)
    seed_default_printers(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = "escpos_network"
    db_session.commit()

    kitchen = (
        db_session.query(Printer)
        .filter(Printer.role == "kitchen", Printer.is_active.is_(True))
        .first()
    )
    assert kitchen is not None
    kitchen.host = "127.0.0.1"
    kitchen.port = 1  # unlikely open
    db_session.commit()

    cat = Category(name="Food-Health", printer_route="food")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name="Test Item",
        price=1000,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    monkeypatch.setattr(
        "routers.orders.dispatch_kitchen_ticket",
        AsyncMock(side_effect=OSError("printer down")),
    )

    try:
        res = client.post(
            "/api/orders/submit",
            headers=auth_headers("waiter"),
            json={
                "order_type": "takeaway",
                "customer_name": "Health",
                "items": [
                    {
                        "menu_item_id": item.id,
                        "quantity": 1,
                        "selected_modifiers": [],
                    }
                ],
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["id"]
        assert float(body["total_amount"]) == 1000.0
        assert body.get("warning")
        assert "offline" in body["warning"].lower() or "failed" in body["warning"].lower()
    finally:
        settings.backend = "file"
        db_session.commit()


def test_warning_for_offline_routes_message():
    msg = warning_for_offline_routes(
        [
            RouteHealth("food", False, "offline", "192.168.1.10", 9100, "refused"),
            RouteHealth("drinks", True, "online", "192.168.1.11", 9100, "ok"),
        ]
    )
    assert msg is not None
    assert "food" in msg
    assert "192.168.1.10" in msg


def test_windows_backend_without_kitchen_lan_warns_on_submit(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    """Confirmed bug: windows_printer + empty kitchen host used to silently file-print."""
    from services.printing.config import PrinterConfig

    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = "windows_printer"
    settings.render_mode = "text"
    db_session.commit()

    # Active kitchen row with NO host → previous code fell back to file quietly.
    seed_default_printers(db_session)
    kitchen = (
        db_session.query(Printer)
        .filter(Printer.role == "kitchen", Printer.is_active.is_(True))
        .first()
    )
    assert kitchen is not None
    kitchen.host = ""
    kitchen.port = 9100
    db_session.commit()

    def _fake_load(db=None):
        return PrinterConfig(
            backend="windows_printer",
            render_mode="text",
            paper_width_px=576,
            output_dir=str(tmp_path),
            routes={},  # no LAN routes
        )

    monkeypatch.setattr("services.printing.service.load_printer_config", _fake_load)
    monkeypatch.setattr("services.printing.health.load_printer_config", _fake_load)
    monkeypatch.setattr(
        "services.printing.health.resolve_printer_endpoint_for_role",
        lambda *a, **k: None,
    )

    cat = Category(name="Food-WinSilent", printer_route="food")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name="SilentFailItem",
        price=1000,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Silent",
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert float(body["total_amount"]) == 1000.0
    assert body.get("warning"), "must warn when kitchen cannot be reached"
    assert "kitchen" in body["warning"].lower() or "food" in body["warning"].lower()
    # File backup may still exist
    out = tmp_path / "food_printer_output.txt"
    assert out.exists()
    assert "SilentFailItem" in out.read_text(encoding="utf-8")

    # Restore shared DB settings so later tests are not polluted.
    settings.backend = "file"
    db_session.commit()


def test_dine_in_and_takeaway_both_write_kitchen_file(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    from services.printing.config import PrinterConfig
    from models import Table, Zone
    import uuid

    seed_kitchen_printer_settings(db_session)
    settings = db_session.query(KitchenPrinterSettings).filter_by(id=1).first()
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()

    def _fake_load(db=None):
        return PrinterConfig(
            backend="file",
            render_mode="text",
            paper_width_px=576,
            output_dir=str(tmp_path),
            routes={},
        )

    monkeypatch.setattr("services.printing.service.load_printer_config", _fake_load)
    monkeypatch.setattr("services.printing.health.load_printer_config", _fake_load)

    cat = Category(name="Food-Both", printer_route="food")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name="KitchenReachItem",
        price=1500,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(item)
    db_session.refresh(table)

    dine = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "table_id": table.id,
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert dine.status_code == 200, dine.text
    assert dine.json().get("warning") in (None, "")

    tw = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Reach",
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert tw.status_code == 200, tw.text
    assert tw.json().get("warning") in (None, "")

    text = (tmp_path / "food_printer_output.txt").read_text(encoding="utf-8")
    assert text.count("KitchenReachItem") >= 2
    assert "TAKEAWAY" in text or "ပါဆယ်" in text
