"""Kitchen slip mode: one slip per item or one combined slip per printer route.

Spec: specs/feature-kitchen-slip-mode/requirements.md
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from models import (
    Category,
    KitchenPrinterSettings,
    MenuItem,
    Order,
    OrderItem,
    Printer,
    PrintJob,
    Table,
    Zone,
)
from services.printing import print_jobs
from services.printing.image_renderer import render_ticket_image
from services.printing.settings import (
    load_kitchen_slip_copies,
    load_kitchen_slip_mode,
    seed_kitchen_printer_settings,
)
from services.printing.ticket import (
    BANNER_PREFIX,
    build_batch_ticket_text,
    build_escpos_text_payload,
    plain_ticket_text,
)

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


def _store(db_session, *, mode: str, backend: str = "file", copies: int = 1) -> None:
    row = _settings_row(db_session)
    row.kitchen_slip_mode = mode
    row.kitchen_slip_copies = copies
    row.backend = backend
    row.render_mode = "text"
    db_session.commit()


@pytest.fixture()
def slip_mode(db_session):
    """Set the mode for a test; always back to per_item afterwards (shared DB)."""
    _store(db_session, mode="per_item")
    yield lambda mode, copies=1: _store(db_session, mode=mode, copies=copies)
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


# —— copies of a combined slip (FR-SM7) ——


def test_copies_setting_contract(client, db_session, auth_headers, slip_mode):
    admin = auth_headers("admin")
    assert client.get(SETTINGS_URL, headers=admin).json()["kitchen_slip_copies"] == 1

    res = _put(client, admin, kitchen_slip_mode="combined", kitchen_slip_copies=3)
    assert res.status_code == 200, res.text
    assert (res.json()["kitchen_slip_mode"], res.json()["kitchen_slip_copies"]) == ("combined", 3)
    db_session.expire_all()
    assert load_kitchen_slip_copies(db_session) == 3

    # A client that does not send the field must not reset it.
    kept = _put(client, admin, paper_width_px=384)
    assert kept.json()["kitchen_slip_copies"] == 3
    assert kept.json()["kitchen_slip_mode"] == "combined"
    _put(client, admin, paper_width_px=576)


@pytest.mark.parametrize("bad", [0, 4, -1, 2.5, "2", "many", True])
def test_copies_setting_rejects_values_outside_1_to_3(client, db_session, auth_headers, slip_mode, bad):
    slip_mode("combined", copies=2)
    res = _put(client, auth_headers("admin"), kitchen_slip_copies=bad)
    assert res.status_code == 422, res.text
    db_session.expire_all()
    assert load_kitchen_slip_copies(db_session) == 2


def test_copies_setting_needs_an_admin(client, db_session, auth_headers, slip_mode):
    for role in ("waiter", "cashier", "account"):
        assert _put(client, auth_headers(role), kitchen_slip_copies=3).status_code == 403, role
    db_session.expire_all()
    assert load_kitchen_slip_copies(db_session) == 1


@pytest.mark.parametrize("stored", [0, 9, -2])
def test_out_of_range_stored_copies_behave_as_one(
    client, db_session, auth_headers, slip_mode, printer, stored
):
    slip_mode("combined")
    row = _settings_row(db_session)
    row.kitchen_slip_copies = stored
    db_session.commit()

    assert load_kitchen_slip_copies(db_session) == 1
    assert client.get(SETTINGS_URL, headers=auth_headers("admin")).json()["kitchen_slip_copies"] == 1
    table, tea, mohinga, rice = _seed_menu(db_session)
    _submit(client, auth_headers("waiter"), table.id, [(mohinga.id, 1)])
    assert len(printer.calls) == 1


def test_combined_with_three_copies_prints_each_slip_three_times(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined", copies=3)
    table, tea, mohinga, rice = _seed_menu(db_session)
    res = _submit(
        client, auth_headers("waiter"), table.id, [(mohinga.id, 2), (tea.id, 1), (rice.id, 1)]
    )
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 2 * 3500.0 + 1500.0 + 2000.0

    jobs = _jobs(db_session, res.json()["id"])
    assert [
        (j.route, j.payload["ticket"]["copy_number"], j.payload["ticket"]["copy_total"], j.print_status)
        for j in jobs
    ] == [
        ("food", 1, 3, "printed"), ("food", 2, 3, "printed"), ("food", 3, 3, "printed"),
        ("drinks", 1, 3, "printed"), ("drinks", 2, 3, "printed"), ("drinks", 3, 3, "printed"),
    ]
    # Every copy lists the same lines.
    food_items = [[i["item_name"] for i in j.payload["ticket"]["items"]] for j in jobs[:3]]
    assert food_items == [[mohinga.name, rice.name]] * 3
    assert [(c["route"], c["ticket"]["copy_number"]) for c in printer.calls] == [
        ("food", 1), ("food", 2), ("food", 3), ("drinks", 1), ("drinks", 2), ("drinks", 3),
    ]
    # The order itself is not duplicated: still three lines.
    assert [l.quantity for l in _lines(db_session, res.json()["id"])] == [2, 1, 1]


def test_one_copy_adds_nothing_to_the_slip(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined", copies=1)
    table, tea, mohinga, rice = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(mohinga.id, 1)]).json()["id"]

    (job,) = _jobs(db_session, order_id)
    assert "copy_number" not in job.payload["ticket"] and "copy_total" not in job.payload["ticket"]
    ((_, text),) = slip_texts
    assert "COPY" not in text and BANNER_PREFIX not in text
    assert text.startswith("=== KITCHEN TICKET ===")


def test_copies_are_ignored_in_per_item_mode(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("per_item", copies=3)
    table, tea, mohinga, rice = _seed_menu(db_session)
    order_id = _submit(
        client, auth_headers("waiter"), table.id, [(mohinga.id, 1), (rice.id, 1)]
    ).json()["id"]

    assert len(_jobs(db_session, order_id)) == 2
    assert len(slip_texts) == 2
    assert all("COPY" not in text for _, text in slip_texts)


def test_each_copy_starts_with_its_own_banner(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined", copies=3)
    table, tea, mohinga, rice = _seed_menu(db_session)
    _submit(client, auth_headers("waiter"), table.id, [(mohinga.id, 2), (rice.id, 1)])

    texts = [text for _, text in slip_texts]
    assert len(texts) == 3
    for number, text in enumerate(texts, start=1):
        first, second = text.split("\n")[:2]
        # The banner is the first line of the slip, before the title.
        assert first == f"{BANNER_PREFIX}COPY {number} / 3"
        assert second == "=== KITCHEN TICKET ==="
        assert text.count("COPY") == 1
        assert f"2x {mohinga.name}" in text and f"1x {rice.name}" in text
    # Apart from the banner the three copies are identical.
    assert len({text.split("\n", 1)[1] for text in texts}) == 1


def _copy_slip(number: int = 2, total: int = 3) -> str:
    return build_batch_ticket_text(
        route="food",
        items=[{"item_name": "Mohinga", "quantity": 2}],
        table_number="5",
        order_id=7,
        created_at="2026-11-16T12:00:00",
        batch_number=1,
        copy_number=number,
        copy_total=total,
    )


def test_a_single_copy_never_gets_a_banner():
    assert _copy_slip(1, 1).startswith("=== KITCHEN TICKET ===")
    assert "COPY" not in _copy_slip(1, 1)
    assert _copy_slip(1, 2).startswith(f"{BANNER_PREFIX}COPY 1 / 2\n")


def test_copy_banner_in_plain_text_is_a_framed_block():
    lines = plain_ticket_text(_copy_slip()).split("\n")
    assert lines[0] == "#" * 33
    assert lines[1].startswith("###") and lines[1].endswith("###") and len(lines[1]) == 33
    assert lines[1].strip("#").strip() == "COPY 2 / 3"
    assert lines[2] == "#" * 33
    assert lines[3] == "=== KITCHEN TICKET ==="
    assert BANNER_PREFIX not in "\n".join(lines)
    # Text without a banner is returned untouched.
    plain = build_batch_ticket_text(
        route="food", items=[{"item_name": "Mohinga", "quantity": 2}],
        table_number="5", order_id=7, created_at="x",
    )
    assert plain_ticket_text(plain) == plain


def test_copy_banner_in_escpos_text_is_double_size_reversed_and_reset():
    payload = build_escpos_text_payload(_copy_slip())
    centre, double, reverse_on = b"\x1b\x61\x01", b"\x1d\x21\x11", b"\x1d\x42\x01"
    reverse_off, normal, left = b"\x1d\x42\x00", b"\x1d\x21\x00", b"\x1b\x61\x00"

    banner = centre + double + reverse_on + b" COPY 2 / 3 " + reverse_off + normal + b"\n" + left
    assert payload.startswith(b"\x1b\x40" + banner + b"=== KITCHEN TICKET ===\n")
    # The marker itself is never sent to the printer, and big/reversed is
    # switched off again before the rest of the slip.
    assert BANNER_PREFIX.strip().encode() not in payload
    after = payload[payload.index(b"=== KITCHEN TICKET ==="):]
    assert double not in after and reverse_on not in after
    assert payload.endswith(b"\n\n\x1d\x56\x00")

    # A slip without copies is byte-for-byte what it was before this feature.
    plain = build_batch_ticket_text(
        route="food", items=[{"item_name": "Mohinga", "quantity": 2}],
        table_number="5", order_id=7, created_at="x",
    )
    assert build_escpos_text_payload(plain) == b"\x1b\x40" + plain.encode("utf-8") + b"\n\n\x1d\x56\x00"


def test_copy_banner_in_image_mode_is_a_full_width_black_bar():
    with_banner = render_ticket_image(_copy_slip(), paper_width_px=576)
    without = render_ticket_image(_copy_slip().split("\n", 1)[1], paper_width_px=576)
    assert with_banner.size[0] == without.size[0] == 576
    banner_height = with_banner.size[1] - without.size[1]
    # Taller than two normal text lines: clearly bigger than anything else on the slip.
    assert banner_height >= 70

    def black_share(image, top, bottom):
        region = image.crop((0, top, image.size[0], bottom)).convert("L")
        pixels = list(region.getdata())
        return sum(1 for value in pixels if value < 128) / len(pixels)

    # Inside the banner most pixels are black (white text on a black bar) and
    # the bar reaches both paper edges; ordinary text rows are mostly white.
    top = 16 + 4
    assert black_share(with_banner, top, top + 40) > 0.6
    edge_columns = with_banner.crop((0, top, 4, top + 40)).convert("L").getdata()
    assert all(value < 128 for value in edge_columns)
    right_columns = with_banner.crop((572, top, 576, top + 40)).convert("L").getdata()
    assert all(value < 128 for value in right_columns)
    assert black_share(without, top, top + 40) < 0.3


def test_file_backend_writes_copy_banner_without_the_marker(
    client, db_session, auth_headers, slip_mode, monkeypatch, tmp_path
):
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    slip_mode("combined", copies=2)
    table, tea, mohinga, rice = _seed_menu(db_session)
    res = _submit(client, auth_headers("waiter"), table.id, [(mohinga.id, 1)])
    assert res.status_code == 200 and res.json()["warning"] is None

    written = (tmp_path / "food_printer_output.txt").read_text(encoding="utf-8")
    assert written.count("=== KITCHEN TICKET ===") == 2
    assert "COPY 1 / 2" in written and "COPY 2 / 2" in written
    assert BANNER_PREFIX.strip() not in written


def test_only_the_failed_copy_is_retried(client, db_session, auth_headers, slip_mode, printer):
    slip_mode("combined", copies=3)
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")

    async def second_copy_fails(route, ticket, **kwargs):
        if ticket.get("copy_number") == 2:
            raise ConnectionError("Connection refused")
        await printer.kitchen(route, ticket, **kwargs)

    original = print_jobs.dispatch_kitchen_ticket
    print_jobs.dispatch_kitchen_ticket = second_copy_fails
    try:
        order_id = _submit(client, waiter, table.id, [(mohinga.id, 2), (rice.id, 1)]).json()["id"]
    finally:
        print_jobs.dispatch_kitchen_ticket = original
    assert [j.print_status for j in _jobs(db_session, order_id)] == ["printed", "failed", "printed"]

    listed = [j for j in client.get("/api/print-jobs/failed", headers=waiter).json() if j["order_id"] == order_id]
    assert [j["item_label"] for j in listed] == [f"{mohinga.name} x2, {rice.name} x1 (copy 2/3)"]

    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (1, 0)
    # Copies 1 and 3 already came out; only copy 2 is printed again.
    assert [(c["ticket"]["copy_number"], c["ticket"]["copy_total"]) for c in printer.calls] == [(2, 3)]
    assert [j.print_status for j in _jobs(db_session, order_id)] == ["printed"] * 3


def test_cancelled_line_is_left_out_of_every_copy_on_retry(
    client, db_session, auth_headers, slip_mode, printer
):
    slip_mode("combined", copies=2)
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga, rice = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(client, waiter, table.id, [(mohinga.id, 2), (rice.id, 1)]).json()["id"]
    _cancel(db_session, _lines(db_session, order_id)[0].id)

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter).json()
    assert (retry["requeued"], retry["skipped"]) == (2, 0)
    assert [
        (c["ticket"]["copy_number"], [i["item_name"] for i in c["ticket"]["items"]])
        for c in printer.calls
    ] == [(1, [rice.name]), (2, [rice.name])]


def test_copies_reach_the_kitchen_printer_and_the_cashier_still_gets_one_receipt(
    client, db_session, auth_headers, two_printers
):
    _store(db_session, mode="combined", backend="escpos_network", copies=3)
    table, tea, mohinga, rice = _seed_menu(db_session)
    _order_and_pay(
        client, auth_headers, table, [(mohinga.id, 2), (rice.id, 1)], two_printers["cashier_row"]
    )

    at_kitchen = two_printers["kitchen"].wait_for(3)
    at_cashier = two_printers["cashier"].wait_for(1)
    assert len(at_kitchen) == 3 and all(_is_kitchen_slip(text) for text in at_kitchen)
    assert [next(n for n in (1, 2, 3) if f"COPY {n} / 3" in text) for text in at_kitchen] == [1, 2, 3]
    # Copies are a kitchen setting: one receipt, without any copy banner.
    assert len(at_cashier) == 1 and _is_receipt(at_cashier[0])
    assert "COPY" not in at_cashier[0]


# —— kitchen printer vs cashier printer (real TCP, both modes) ——
#
# The mode is a kitchen setting. These tests send real bytes to two listening
# sockets and check which "printer" received what, so a kitchen slip can never
# end up on the cashier printer (or a receipt in the kitchen) in either mode.


class _TcpPrinter:
    """A listening socket standing in for one LAN thermal printer."""

    def __init__(self):
        self.payloads: list[str] = []
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(32)
        self.port = self._sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            data = b""
            with conn:
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
            if data:  # the offline pre-check connects and sends nothing
                self.payloads.append(data.decode("utf-8", errors="ignore"))

    def wait_for(self, count: int, timeout: float = 5.0) -> list[str]:
        end = time.monotonic() + timeout
        while time.monotonic() < end and len(self.payloads) < count:
            time.sleep(0.02)
        time.sleep(0.15)  # anything unexpected would arrive in this window
        return list(self.payloads)

    def close(self):
        self._sock.close()


@pytest.fixture()
def two_printers(db_session, monkeypatch, tmp_path):
    """One kitchen LAN printer and one cashier LAN printer; no bar printer."""
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    for name in list(os.environ):
        if name.startswith("PRINTER_") and name.endswith(("_HOST", "_PORT")):
            monkeypatch.delenv(name, raising=False)
    kitchen_tcp, cashier_tcp = _TcpPrinter(), _TcpPrinter()

    previous = {row.id: row.is_active for row in db_session.query(Printer).all()}
    db_session.query(Printer).update({Printer.is_active: False}, synchronize_session=False)
    kitchen = Printer(name="SM Kitchen", host="127.0.0.1", port=kitchen_tcp.port, role="kitchen", is_active=True)
    cashier = Printer(name="SM Cashier", host="127.0.0.1", port=cashier_tcp.port, role="cashier", is_active=True)
    db_session.add_all([kitchen, cashier])
    db_session.commit()
    try:
        yield {"kitchen": kitchen_tcp, "cashier": cashier_tcp, "cashier_row": cashier}
    finally:
        kitchen_tcp.close()
        cashier_tcp.close()
        db_session.rollback()
        db_session.query(PrintJob).filter(PrintJob.printer_id == cashier.id).delete(synchronize_session=False)
        db_session.query(Printer).filter(Printer.id.in_([kitchen.id, cashier.id])).delete(synchronize_session=False)
        for printer_id, active in previous.items():
            db_session.query(Printer).filter(Printer.id == printer_id).update(
                {Printer.is_active: active}, synchronize_session=False
            )
        db_session.commit()
        _store(db_session, mode="per_item", backend="file")


def _order_and_pay(client, auth_headers, table, lines, cashier_row):
    order = _submit(client, auth_headers("waiter"), table.id, lines)
    assert order.status_code == 200, order.text
    assert order.json()["warning"] is None, order.json()["warning"]
    paid = client.put(
        f"/api/orders/{order.json()['id']}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "cash",
            "amount_tendered": 100000.0,
            "discount_type": None,
            "discount_value": 0,
            "issue_receipt": True,
            "printer_id": cashier_row.id,
        },
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["warning"] in (None, "")
    return order.json(), paid.json()


def _is_kitchen_slip(text: str) -> bool:
    return "KITCHEN" in text and "Grand Total" not in text and "Served by" not in text


def _is_receipt(text: str) -> bool:
    return "Grand Total" in text and "Served by" in text and "KITCHEN" not in text


@pytest.mark.parametrize("mode, kitchen_slips", [("per_item", 3), ("combined", 2)])
def test_kitchen_slips_reach_only_the_kitchen_printer_and_receipt_only_the_cashier_printer(
    client, db_session, auth_headers, two_printers, mode, kitchen_slips
):
    _store(db_session, mode=mode, backend="escpos_network")
    table, tea, mohinga, rice = _seed_menu(db_session)
    order, paid = _order_and_pay(
        client, auth_headers, table, [(mohinga.id, 2), (tea.id, 1), (rice.id, 1)],
        two_printers["cashier_row"],
    )

    at_kitchen = two_printers["kitchen"].wait_for(kitchen_slips)
    at_cashier = two_printers["cashier"].wait_for(1)

    # Kitchen printer: only kitchen slips, as many as the mode says.
    # (No bar printer, so the drinks slip also comes out in the kitchen.)
    assert len(at_kitchen) == kitchen_slips, at_kitchen
    assert all(_is_kitchen_slip(text) for text in at_kitchen), at_kitchen
    for name in (mohinga.name, tea.name, rice.name):
        assert sum(name in text for text in at_kitchen) == 1, name
    # Cashier printer: exactly one receipt, never a kitchen slip — in both modes.
    assert len(at_cashier) == 1, at_cashier
    assert _is_receipt(at_cashier[0]), at_cashier[0]
    for name in (mohinga.name, tea.name, rice.name):
        assert name in at_cashier[0]

    by_route = {(j.kind, j.route) for j in _jobs(db_session, order["id"])}
    assert by_route == {("kitchen", "food"), ("kitchen", "drinks"), ("receipt", "cashier")}
    assert paid["total_amount"] == order["total_amount"] == 2 * 3500.0 + 1500.0 + 2000.0


def test_receipt_is_the_same_in_both_modes(client, db_session, auth_headers, two_printers):
    """The setting changes kitchen slips only; the printed receipt does not change."""
    table_a, tea, mohinga, rice = _seed_menu(db_session)
    table_b = Table(name=f"SM-T2-{uuid.uuid4().hex[:8]}", zone_id=table_a.zone_id, status="available")
    db_session.add(table_b)
    db_session.commit()
    lines = [(mohinga.id, 2), (tea.id, 1), (rice.id, 1)]

    _store(db_session, mode="per_item", backend="escpos_network")
    _order_and_pay(client, auth_headers, table_a, lines, two_printers["cashier_row"])
    _store(db_session, mode="combined", backend="escpos_network")
    _order_and_pay(client, auth_headers, table_b, lines, two_printers["cashier_row"])

    receipts = two_printers["cashier"].wait_for(2)
    assert len(receipts) == 2 and all(_is_receipt(text) for text in receipts)

    def body(text: str) -> list[str]:
        # Order number, table and time differ between the two orders by design.
        return [
            line for line in text.splitlines()
            if not re.match(r"\s*(Order:|Location:|Time:)", line)
        ]

    assert body(receipts[0]) == body(receipts[1])
    # 3 slips for the per_item order + 2 for the combined one, all kitchen slips.
    at_kitchen = two_printers["kitchen"].wait_for(5)
    assert len(at_kitchen) == 5 and all(_is_kitchen_slip(text) for text in at_kitchen)


def test_windows_cashier_queue_never_gets_kitchen_slips_in_combined_mode(
    client, db_session, auth_headers, two_printers, monkeypatch
):
    """Windows mode: receipt → Windows queue, kitchen slips → kitchen LAN printer."""
    windows_jobs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "services.printing.service.send_raw_to_windows_printer",
        lambda name, payload: windows_jobs.append((name, payload.decode("utf-8", errors="ignore"))),
    )
    cashier_row = two_printers["cashier_row"]
    cashier_row.windows_printer_name = "POS-80 Cashier"
    db_session.commit()
    _store(db_session, mode="combined", backend="windows_printer")

    table, tea, mohinga, rice = _seed_menu(db_session)
    _order_and_pay(client, auth_headers, table, [(mohinga.id, 2), (rice.id, 1)], cashier_row)

    at_kitchen = two_printers["kitchen"].wait_for(1)
    assert len(at_kitchen) == 1 and _is_kitchen_slip(at_kitchen[0])
    assert mohinga.name in at_kitchen[0] and rice.name in at_kitchen[0]
    # The Windows cashier queue got the receipt and nothing else.
    assert [name for name, _ in windows_jobs] == ["POS-80 Cashier"]
    assert _is_receipt(windows_jobs[0][1])
    # Nothing was sent to the cashier's LAN address in Windows mode.
    assert two_printers["cashier"].wait_for(0, timeout=0.3) == []


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
        "SELECT backend, render_mode, paper_width_px, kitchen_slip_mode, kitchen_slip_copies "
        "FROM kitchen_printer_settings WHERE id = 1"
    ).fetchone()
    con.close()
    assert {"kitchen_slip_mode", "kitchen_slip_copies"} <= columns
    # Existing settings are untouched; the new columns start as per_item / 1 copy.
    assert row == ("escpos_network", "image", 384, "per_item", 1)
