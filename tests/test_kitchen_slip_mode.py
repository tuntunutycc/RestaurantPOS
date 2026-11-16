"""Kitchen slip mode: one slip per item or one combined slip per printer route.

Spec: specs/feature-kitchen-slip-mode/requirements.md
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from models import (
    Category,
    KitchenPrinterSettings,
    MenuItem,
    Order,
    OrderItem,
    PrintJob,
    Table,
    Zone,
)
from services.printing import print_jobs
from services.printing.settings import load_kitchen_slip_mode, seed_kitchen_printer_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_URL = "/api/admin/kitchen-printers"


# —— helpers ——


def _settings_row(db_session) -> KitchenPrinterSettings:
    seed_kitchen_printer_settings(db_session)
    return (
        db_session.query(KitchenPrinterSettings)
        .filter(KitchenPrinterSettings.id == 1)
        .first()
    )


def _store(db_session, *, mode: str, backend: str = "file") -> None:
    row = _settings_row(db_session)
    row.kitchen_slip_mode = mode
    row.backend = backend
    row.render_mode = "text"
    db_session.commit()


@pytest.fixture()
def slip_mode(db_session):
    """Set the mode for a test; always back to per_item afterwards (shared DB)."""
    _store(db_session, mode="per_item")
    yield lambda mode: _store(db_session, mode=mode)
    _store(db_session, mode="per_item")


class _Printer:
    def __init__(self):
        self.fail_with: Exception | None = None
        self.calls: list[dict] = []

    async def kitchen(self, route, ticket, **kwargs):
        self.calls.append({"route": route, "ticket": ticket, **kwargs})
        if self.fail_with is not None:
            raise self.fail_with


@pytest.fixture()
def printer(monkeypatch):
    fake = _Printer()
    monkeypatch.setattr("services.printing.print_jobs.dispatch_kitchen_ticket", fake.kitchen)
    return fake


@pytest.fixture()
def slip_texts(monkeypatch):
    """Real ticket rendering; only the final send to the printer is captured."""
    sent: list[tuple[str, str]] = []

    async def capture(*, route, ticket_text, **kwargs):
        sent.append((route, ticket_text))

    monkeypatch.setattr("services.printing.service._dispatch_payload", capture)
    return sent


def _seed_menu(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"SM-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"SM-T-{suffix}", zone_id=zone.id, status="available")
    drinks = Category(name=f"SM-Drinks-{suffix}", printer_route="drinks")
    food = Category(name=f"SM-Food-{suffix}", printer_route="food")
    db_session.add_all([table, drinks, food])
    db_session.flush()
    tea = MenuItem(
        name=f"Tea-{suffix}", price=1500.0, category_id=drinks.id,
        is_available=True, modifiers_config=[],
    )
    mohinga = MenuItem(
        name=f"Mohinga-{suffix}", price=3500.0, category_id=food.id,
        is_available=True, modifiers_config=[],
    )
    rice = MenuItem(
        name=f"Rice-{suffix}", price=2000.0, category_id=food.id,
        is_available=True, modifiers_config=[],
    )
    db_session.add_all([tea, mohinga, rice])
    db_session.commit()
    for obj in (table, tea, mohinga, rice):
        db_session.refresh(obj)
    return table, tea, mohinga, rice


def _submit(client, headers, table_id, lines):
    """lines: (menu_item_id, quantity) or a full item dict."""
    items = [
        line
        if isinstance(line, dict)
        else {"menu_item_id": line[0], "quantity": line[1], "selected_modifiers": []}
        for line in lines
    ]
    return client.post(
        "/api/orders/submit",
        headers=headers,
        json={"table_id": table_id, "order_type": "dine_in", "items": items},
    )


def _jobs(db_session, order_id: int) -> list[PrintJob]:
    db_session.expire_all()
    return (
        db_session.query(PrintJob)
        .filter(PrintJob.order_id == order_id)
        .order_by(PrintJob.id.asc())
        .all()
    )


def _lines(db_session, order_id: int) -> list[OrderItem]:
    db_session.expire_all()
    return (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.id.asc())
        .all()
    )


def _cancel(db_session, *line_ids: int) -> None:
    for line_id in line_ids:
        db_session.query(OrderItem).filter(OrderItem.id == line_id).first().item_status = "cancelled"
    db_session.commit()


def _put(client, headers, **fields):
    body = {"backend": "file", "render_mode": "text", "paper_width_px": 576, "routes": []}
    body.update(fields)
    return client.put(SETTINGS_URL, headers=headers, json=body)


# —— setting: contract + roles ——


def test_setting_defaults_to_per_item(client, db_session, auth_headers, slip_mode):
    res = client.get(SETTINGS_URL, headers=auth_headers("admin"))
    assert res.status_code == 200
    assert res.json()["kitchen_slip_mode"] == "per_item"
    assert load_kitchen_slip_mode(db_session) == "per_item"


def test_admin_can_switch_mode_and_it_persists(client, db_session, auth_headers, slip_mode):
    admin = auth_headers("admin")
    res = _put(client, admin, kitchen_slip_mode="combined")
    assert res.status_code == 200, res.text
    assert res.json()["kitchen_slip_mode"] == "combined"
    assert client.get(SETTINGS_URL, headers=admin).json()["kitchen_slip_mode"] == "combined"
    db_session.expire_all()
    assert load_kitchen_slip_mode(db_session) == "combined"

    back = _put(client, admin, kitchen_slip_mode="per_item")
    assert back.json()["kitchen_slip_mode"] == "per_item"


def test_put_without_mode_keeps_the_stored_mode(client, db_session, auth_headers, slip_mode):
    """Older clients send only backend/render/paper; that must not reset the mode."""
    slip_mode("combined")
    res = _put(client, auth_headers("admin"), paper_width_px=384)
    assert res.status_code == 200, res.text
    assert res.json()["kitchen_slip_mode"] == "combined"
    assert res.json()["paper_width_px"] == 384
    _put(client, auth_headers("admin"), paper_width_px=576)


@pytest.mark.parametrize("bad", ["both", "", "PER_ITEM", 1, "combined "])
def test_put_rejects_unknown_mode(client, db_session, auth_headers, slip_mode, bad):
    slip_mode("combined")
    res = _put(client, auth_headers("admin"), kitchen_slip_mode=bad)
    assert res.status_code == 422, res.text
    db_session.expire_all()
    assert load_kitchen_slip_mode(db_session) == "combined"


def test_only_admin_roles_can_change_the_mode(client, db_session, auth_headers, slip_mode):
    assert client.put(SETTINGS_URL, json={"backend": "file"}).status_code == 401
    for role in ("waiter", "cashier", "account"):
        res = _put(client, auth_headers(role), kitchen_slip_mode="combined")
        assert res.status_code == 403, (role, res.text)
        assert client.get(SETTINGS_URL, headers=auth_headers(role)).status_code == 403, role
    db_session.expire_all()
    assert load_kitchen_slip_mode(db_session) == "per_item"
    for role in ("admin", "root"):
        assert _put(client, auth_headers(role), kitchen_slip_mode="combined").status_code == 200


def test_unknown_stored_value_falls_back_to_per_item(
    client, db_session, auth_headers, slip_mode, printer
):
    row = _settings_row(db_session)
    row.kitchen_slip_mode = "something-else"
    db_session.commit()

    assert load_kitchen_slip_mode(db_session) == "per_item"
    assert client.get(SETTINGS_URL, headers=auth_headers("admin")).json()["kitchen_slip_mode"] == "per_item"
    table, tea, mohinga, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1), (mohinga.id, 1)]).json()["id"]
    assert len(_jobs(db_session, order_id)) == 2


# —— submit ——


def test_per_item_mode_prints_one_slip_per_line(client, db_session, auth_headers, slip_mode, printer):
    table, tea, mohinga, rice = _seed_menu(db_session)
    res = _submit(
        client, auth_headers("waiter"), table.id, [(mohinga.id, 2), (tea.id, 1), (rice.id, 1)]
    )
    assert res.status_code == 200, res.text

    jobs = _jobs(db_session, res.json()["id"])
    lines = _lines(db_session, res.json()["id"])
    assert [j.route for j in jobs] == ["food", "drinks", "food"]
    assert [j.order_item_id for j in jobs] == [line.id for line in lines]
    assert all("items" not in j.payload["ticket"] for j in jobs)
    assert [c["ticket"]["item_name"] for c in printer.calls] == [mohinga.name, tea.name, rice.name]


def test_combined_mode_prints_one_slip_per_printer_route(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    table, tea, mohinga, rice = _seed_menu(db_session)
    res = _submit(
        client, auth_headers("waiter"), table.id, [(mohinga.id, 2), (tea.id, 1), (rice.id, 1)]
    )
    assert res.status_code == 200, res.text
    body = res.json()

    jobs = _jobs(db_session, body["id"])
    lines = _lines(db_session, body["id"])
    # Food slip first (first route in the order), then the drinks slip.
    assert [(j.route, j.order_item_id, j.print_status) for j in jobs] == [
        ("food", None, "printed"),
        ("drinks", None, "printed"),
    ]
    food_ticket, drinks_ticket = jobs[0].payload["ticket"], jobs[1].payload["ticket"]
    assert [(i["item_name"], i["quantity"], i["order_item_id"]) for i in food_ticket["items"]] == [
        (mohinga.name, 2, lines[0].id),
        (rice.name, 1, lines[2].id),
    ]
    assert [(i["item_name"], i["quantity"], i["order_item_id"]) for i in drinks_ticket["items"]] == [
        (tea.name, 1, lines[1].id)
    ]
    assert food_ticket["order_id"] == body["id"]
    assert food_ticket["batch_number"] == 1
    assert food_ticket["table_number"] == drinks_ticket["table_number"]
    # Exactly two slips reached the printers.
    assert [(c["route"], len(c["ticket"]["items"])) for c in printer.calls] == [("food", 2), ("drinks", 1)]


def test_mode_does_not_change_the_order_or_the_response(
    client, db_session, auth_headers, slip_mode, printer
):
    """Money, lines and the response shape are identical in both modes."""
    waiter = auth_headers("waiter")
    order_lines = lambda tea, mohinga, rice: [(mohinga.id, 2), (tea.id, 3), (rice.id, 1)]
    expected_total = 2 * 3500.0 + 3 * 1500.0 + 2000.0

    table_a, tea_a, mohinga_a, rice_a = _seed_menu(db_session)
    per_item = _submit(client, waiter, table_a.id, order_lines(tea_a, mohinga_a, rice_a)).json()

    slip_mode("combined")
    table_b, tea_b, mohinga_b, rice_b = _seed_menu(db_session)
    combined = _submit(client, waiter, table_b.id, order_lines(tea_b, mohinga_b, rice_b)).json()

    assert per_item["total_amount"] == combined["total_amount"] == expected_total
    assert set(per_item) == set(combined)
    assert per_item["warning"] is None and combined["warning"] is None
    assert [l.quantity for l in _lines(db_session, combined["id"])] == [2, 3, 1]
    assert [float(l.subtotal) for l in _lines(db_session, combined["id"])] == [
        float(l.subtotal) for l in _lines(db_session, per_item["id"])
    ]
    order = db_session.query(Order).filter(Order.id == combined["id"]).first()
    assert order.total_amount == expected_total


def test_combined_second_submit_prints_only_the_new_batch(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    first = _submit(client, waiter, table.id, [(mohinga.id, 1)]).json()
    printer.calls.clear()

    second = _submit(client, waiter, table.id, [(rice.id, 2), (mohinga.id, 1)]).json()
    assert second["id"] == first["id"]
    (call,) = printer.calls
    assert call["ticket"]["batch_number"] == 2
    assert [(i["item_name"], i["quantity"]) for i in call["ticket"]["items"]] == [
        (rice.name, 2),
        (mohinga.name, 1),
    ]
    assert len(_jobs(db_session, first["id"])) == 2


# —— what is printed ——


def test_combined_slip_text(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined")
    table, tea, mohinga, rice = _seed_menu(db_session)
    res = _submit(
        client,
        auth_headers("waiter"),
        table.id,
        [
            {"menu_item_id": mohinga.id, "quantity": 2, "selected_modifiers": [], "note": "no chilli"},
            {"menu_item_id": tea.id, "quantity": 1, "selected_modifiers": []},
            {"menu_item_id": rice.id, "quantity": 1, "selected_modifiers": [], "is_takeaway": True},
        ],
    )
    assert res.status_code == 200, res.text

    assert [route for route, _ in slip_texts] == ["food", "drinks"]
    food, drinks = slip_texts[0][1], slip_texts[1][1]
    assert food.count("=== KITCHEN TICKET ===") == 1
    assert "Batch: #1" in food
    assert f"Order: #{res.json()['id']}" in food or str(res.json()["id"]) in food
    assert f"2x {mohinga.name}" in food
    assert "no chilli" in food
    assert f"1x {rice.name} (ပါဆယ်)" in food
    assert food.index(mohinga.name) < food.index(rice.name)
    assert food.count("[ --- CUT TICKET --- ]") == 1
    # Drinks are not on the kitchen slip, food is not on the bar slip.
    assert tea.name not in food
    assert f"1x {tea.name}" in drinks and mohinga.name not in drinks
    # Kitchen slips never carry prices.
    for text in (food, drinks):
        assert "3500" not in text and "1500" not in text and "2000" not in text


def test_per_item_slip_text(client, db_session, auth_headers, slip_mode, slip_texts):
    table, tea, mohinga, rice = _seed_menu(db_session)
    _submit(client, auth_headers("waiter"), table.id, [(mohinga.id, 2), (rice.id, 1)])

    assert len(slip_texts) == 2
    assert all(text.count("=== KITCHEN ITEM TICKET ===") == 1 for _, text in slip_texts)
    assert f"2x {mohinga.name}" in slip_texts[0][1] and rice.name not in slip_texts[0][1]
    assert f"1x {rice.name}" in slip_texts[1][1]


# —— combined slip in the print queue ——


def test_combined_failed_slip_is_listed_and_retried_as_one_slip(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    res = _submit(client, waiter, table.id, [(mohinga.id, 2), (rice.id, 1)])
    assert res.status_code == 200, res.text
    order_id = res.json()["id"]
    total = res.json()["total_amount"]

    (job,) = _jobs(db_session, order_id)
    assert (job.print_status, job.error_message, job.attempts) == ("failed", "Connection refused", 1)
    listed = [j for j in client.get("/api/print-jobs/failed", headers=waiter).json() if j["order_id"] == order_id]
    assert [(j["item_label"], j["order_item_id"], j["route"]) for j in listed] == [
        (f"{mohinga.name} x2, {rice.name} x1", None, "food")
    ]

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (1, 0)
    (call,) = printer.calls
    assert [i["item_name"] for i in call["ticket"]["items"]] == [mohinga.name, rice.name]
    (job,) = _jobs(db_session, order_id)
    assert (job.print_status, job.attempts) == ("printed", 2)
    db_session.expire_all()
    assert db_session.query(Order).filter(Order.id == order_id).first().total_amount == total


def test_combined_retry_leaves_out_cancelled_lines(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(client, waiter, table.id, [(mohinga.id, 2), (rice.id, 1)]).json()["id"]
    mohinga_line, rice_line = _lines(db_session, order_id)
    _cancel(db_session, mohinga_line.id)

    listed = [j for j in client.get("/api/print-jobs/failed", headers=waiter).json() if j["order_id"] == order_id]
    assert [j["item_label"] for j in listed] == [f"{rice.name} x1"]

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (1, 0)
    (call,) = printer.calls
    assert [i["item_name"] for i in call["ticket"]["items"]] == [rice.name]
    # The stored slip is not rewritten; only what is sent is filtered.
    (job,) = _jobs(db_session, order_id)
    assert job.print_status == "printed"
    assert len(job.payload["ticket"]["items"]) == 2


def test_combined_slip_with_every_line_cancelled_is_not_printed(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(client, waiter, table.id, [(mohinga.id, 2), (rice.id, 1)]).json()["id"]
    _cancel(db_session, *[line.id for line in _lines(db_session, order_id)])

    listed = client.get("/api/print-jobs/failed", headers=waiter).json()
    assert order_id not in {j["order_id"] for j in listed}

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (0, 1)
    assert printer.calls == []
    assert [j.print_status for j in _jobs(db_session, order_id)] == ["failed"]


def test_combined_slip_on_cancelled_order_is_not_printed(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(client, waiter, table.id, [(mohinga.id, 1)]).json()["id"]
    order = db_session.query(Order).filter(Order.id == order_id).first()
    order.status = "cancelled"
    db_session.commit()

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (0, 1)
    assert printer.calls == []


def test_line_cancelled_while_combined_slip_waits_is_left_out(db_session, slip_mode, printer):
    """A queued slip is filtered when it is sent, not when it was created."""
    table, tea, mohinga, rice = _seed_menu(db_session)
    order = Order(table_id=table.id, order_type="dine_in", status="open", total_amount=0.0)
    db_session.add(order)
    db_session.flush()
    lines = [
        OrderItem(order_id=order.id, menu_item_id=item.id, quantity=1, subtotal=item.price)
        for item in (mohinga, rice)
    ]
    db_session.add_all(lines)
    db_session.flush()

    def queue_slip() -> int:
        (job,) = print_jobs.create_kitchen_jobs_for_batch(
            db_session,
            slip_mode="combined",
            order_id=order.id,
            lines=[("food", {"item_name": item.name, "quantity": 1}, line.id)
                   for item, line in zip((mohinga, rice), lines)],
            table_number=table.name,
            date="2026-11-16T12:00:00",
            batch_number=1,
            order_type="dine_in",
            customer_name=None,
        )
        db_session.commit()
        return job.id

    first = queue_slip()
    _cancel(db_session, lines[0].id)
    asyncio.run(print_jobs.execute_print_job(db_session, first))
    assert [i["item_name"] for i in printer.calls[-1]["ticket"]["items"]] == [rice.name]
    assert db_session.get(PrintJob, first).print_status == "printed"

    second = queue_slip()
    _cancel(db_session, lines[1].id)
    sent_before = len(printer.calls)
    event = asyncio.run(print_jobs.execute_print_job(db_session, second))
    assert len(printer.calls) == sent_before
    job = db_session.get(PrintJob, second)
    assert (job.print_status, job.attempts) == ("failed", 0)
    assert job.error_message == "Skipped: all items were cancelled"
    assert event["print_status"] == "failed"


def test_changing_the_mode_does_not_reshape_slips_already_recorded(
    client, db_session, auth_headers, slip_mode, printer
):
    printer.fail_with = ConnectionError("Connection refused")
    waiter = auth_headers("waiter")

    slip_mode("combined")
    table_a, _, mohinga_a, rice_a = _seed_menu(db_session)
    combined_order = _submit(client, waiter, table_a.id, [(mohinga_a.id, 1), (rice_a.id, 1)]).json()["id"]

    slip_mode("per_item")
    table_b, _, mohinga_b, rice_b = _seed_menu(db_session)
    per_item_order = _submit(client, waiter, table_b.id, [(mohinga_b.id, 1), (rice_b.id, 1)]).json()["id"]

    printer.fail_with = None
    printer.calls.clear()
    # Recorded as one combined slip; retried under per_item → still one slip.
    client.post(f"/api/orders/{combined_order}/retry-print", headers=waiter)
    assert [len(c["ticket"]["items"]) for c in printer.calls] == [2]

    slip_mode("combined")
    printer.calls.clear()
    # Recorded as two single slips; retried under combined → still two slips.
    client.post(f"/api/orders/{per_item_order}/retry-print", headers=waiter)
    assert [c["ticket"]["item_name"] for c in printer.calls] == [mohinga_b.name, rice_b.name]


def test_combined_label_shows_three_lines_then_a_count(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(
        client, waiter, table.id, [(mohinga.id, qty) for qty in (1, 2, 3, 4, 5)]
    ).json()["id"]

    (job,) = client.get(f"/api/orders/{order_id}/print-jobs", headers=waiter).json()
    assert job["item_label"] == (
        f"{mohinga.name} x1, {mohinga.name} x2, {mohinga.name} x3 +2 more"
    )
    assert job["kind"] == "kitchen" and job["order_item_id"] is None


# —— existing database gets the column at startup ——


def test_startup_adds_the_column_to_an_existing_database(tmp_path):
    db_path = tmp_path / "old.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE kitchen_printer_settings ("
        "id INTEGER PRIMARY KEY, backend VARCHAR(32) NOT NULL, "
        "render_mode VARCHAR(32) NOT NULL DEFAULT 'text', "
        "paper_width_px INTEGER NOT NULL DEFAULT 576, "
        "default_printers_seeded BOOLEAN NOT NULL DEFAULT 0)"
    )
    con.execute(
        "INSERT INTO kitchen_printer_settings (id, backend, render_mode, paper_width_px, "
        "default_printers_seeded) VALUES (1, 'escpos_network', 'image', 384, 1)"
    )
    con.commit()
    con.close()

    env = {k: v for k, v in os.environ.items() if not k.startswith("PRINTER_")}
    env.update(
        DATABASE_URL=f"sqlite:///{db_path}",
        KITCHEN_PRINT_OUTPUT_DIR=str(tmp_path),
        PYTHONPATH=os.pathsep.join(
            [str(REPO_ROOT), str(REPO_ROOT / ".pip_pkgs"), env.get("PYTHONPATH", "")]
        ),
    )
    script = (
        "from services.printing import print_log\n"
        f"print_log.PRINT_LOG_DIR = __import__('pathlib').Path({str(tmp_path / 'logs')!r})\n"
        "print_log.PRINT_LOG_FILE = print_log.PRINT_LOG_DIR / 'print.log'\n"
        "from fastapi.testclient import TestClient\n"
        "import main\n"
        "from database import SessionLocal\n"
        "from services.printing.settings import load_kitchen_slip_mode\n"
        "with TestClient(main.app):\n"
        "    db = SessionLocal()\n"
        "    print('MODE=' + load_kitchen_slip_mode(db))\n"
        "    db.close()\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "MODE=per_item" in proc.stdout

    con = sqlite3.connect(db_path)
    columns = {row[1] for row in con.execute("PRAGMA table_info(kitchen_printer_settings)")}
    row = con.execute(
        "SELECT backend, render_mode, paper_width_px, kitchen_slip_mode "
        "FROM kitchen_printer_settings WHERE id = 1"
    ).fetchone()
    con.close()
    assert "kitchen_slip_mode" in columns
    # Existing settings are untouched; the new column starts as per_item.
    assert row == ("escpos_network", "image", 384, "per_item")
