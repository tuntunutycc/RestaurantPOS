"""Print queue + retry (specs/feature-print-queue).

Three layers:
1. ``PrintQueue`` mechanics (ordering, pause, parallel printers, failures).
2. HTTP contract with the queue not started: slips are sent inside the request,
   which makes status assertions deterministic.
3. The real background queue against the database, plus one subprocess test
   that boots the real app lifespan and prints over real TCP sockets.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

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
from services.printing.print_queue import (
    PrintQueue,
    delay_from_env,
    file_key,
    lan_key,
    windows_key,
)
from services.printing.settings import seed_default_printers, seed_kitchen_printer_settings

REPO_ROOT = Path(__file__).resolve().parents[1]


# —— helpers ——


def _set_backend(db_session, backend: str = "file") -> None:
    seed_kitchen_printer_settings(db_session)
    settings = (
        db_session.query(KitchenPrinterSettings)
        .filter(KitchenPrinterSettings.id == 1)
        .first()
    )
    settings.backend = backend
    settings.render_mode = "text"
    db_session.commit()


def _seed_menu(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"PQ-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"PQ-T-{suffix}", zone_id=zone.id, status="available")
    drinks = Category(name=f"PQ-Drinks-{suffix}", printer_route="drinks")
    food = Category(name=f"PQ-Food-{suffix}", printer_route="food")
    db_session.add_all([table, drinks, food])
    db_session.flush()
    tea = MenuItem(
        name=f"Tea-{suffix}",
        price=1500.0,
        category_id=drinks.id,
        is_available=True,
        modifiers_config=[],
    )
    mohinga = MenuItem(
        name=f"Mohinga-{suffix}",
        price=3500.0,
        category_id=food.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add_all([tea, mohinga])
    db_session.commit()
    for obj in (table, tea, mohinga):
        db_session.refresh(obj)
    return table, tea, mohinga


def _submit(client, headers, table_id, lines):
    return client.post(
        "/api/orders/submit",
        headers=headers,
        json={
            "table_id": table_id,
            "order_type": "dine_in",
            "items": [
                {"menu_item_id": item_id, "quantity": qty, "selected_modifiers": []}
                for item_id, qty in lines
            ],
        },
    )


def _jobs(db_session, order_id: int) -> list[PrintJob]:
    db_session.expire_all()
    return (
        db_session.query(PrintJob)
        .filter(PrintJob.order_id == order_id)
        .order_by(PrintJob.id.asc())
        .all()
    )


class _Printer:
    """Stand-in for dispatch_kitchen_ticket / dispatch_cashier_receipt."""

    def __init__(self, *, fail_with: Exception | None = None, hold: float = 0.0):
        self.fail_with = fail_with
        self.hold = hold
        self.calls: list[dict] = []
        self.active = 0
        self.max_active = 0

    async def kitchen(self, route, ticket, **kwargs):
        await self._send({"kind": "kitchen", "route": route, "ticket": dict(ticket), **kwargs})

    async def receipt(self, **kwargs):
        await self._send({"kind": "receipt", **kwargs})

    async def _send(self, call):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        call["started"] = time.monotonic()
        self.calls.append(call)
        try:
            if self.hold:
                await asyncio.sleep(self.hold)
            if self.fail_with is not None:
                raise self.fail_with
        finally:
            call["ended"] = time.monotonic()
            self.active -= 1


@pytest.fixture()
def printer(monkeypatch):
    fake = _Printer()
    monkeypatch.setattr("services.printing.print_jobs.dispatch_kitchen_ticket", fake.kitchen)
    monkeypatch.setattr("services.printing.print_jobs.dispatch_cashier_receipt", fake.receipt)
    return fake


@pytest.fixture()
def file_backend(db_session):
    _set_backend(db_session, "file")
    yield
    _set_backend(db_session, "file")


# —— 1. queue mechanics ——


def test_same_printer_slips_are_sent_one_at_a_time_with_a_pause():
    async def scenario():
        queue = PrintQueue(delay_seconds=0.05)
        await queue.start()
        spans: list[tuple[float, float]] = []
        active = 0
        overlapped = False

        async def slip():
            nonlocal active, overlapped
            active += 1
            overlapped = overlapped or active > 1
            start = time.monotonic()
            await asyncio.sleep(0.01)
            spans.append((start, time.monotonic()))
            active -= 1

        for _ in range(4):
            queue.submit("lan:10.0.0.5:9100", slip)
        await queue.join()
        await queue.stop()
        return spans, overlapped

    spans, overlapped = asyncio.run(scenario())
    assert len(spans) == 4
    assert overlapped is False
    for (_, previous_end), (next_start, _) in zip(spans, spans[1:]):
        # The pause is measured from the end of one slip to the start of the next.
        assert next_start - previous_end >= 0.045


def test_slips_keep_submission_order():
    async def scenario():
        queue = PrintQueue(delay_seconds=0)
        await queue.start()
        seen: list[int] = []

        def make(n):
            async def slip():
                seen.append(n)

            return slip

        for n in range(6):
            queue.submit("lan:10.0.0.5:9100", make(n))
        await queue.join()
        await queue.stop()
        return seen

    assert asyncio.run(scenario()) == [0, 1, 2, 3, 4, 5]


def test_different_printers_do_not_wait_for_each_other():
    async def scenario():
        queue = PrintQueue(delay_seconds=0.5)
        await queue.start()
        finished: dict[str, float] = {}
        began = time.monotonic()

        def make(name):
            async def slip():
                finished[name] = time.monotonic() - began

            return slip

        # Kitchen has a backlog; the cashier receipt must not sit behind it.
        queue.submit("lan:kitchen:9100", make("kitchen-1"))
        queue.submit("lan:kitchen:9100", make("kitchen-2"))
        queue.submit("lan:cashier:9100", make("receipt"))
        await asyncio.sleep(0.1)
        early = dict(finished)
        await queue.join()
        await queue.stop()
        return early, finished

    early, finished = asyncio.run(scenario())
    assert set(early) == {"kitchen-1", "receipt"}
    assert finished["receipt"] < 0.1
    assert finished["kitchen-2"] >= 0.5


def test_worker_keeps_going_after_a_failed_slip():
    async def scenario():
        queue = PrintQueue(delay_seconds=0)
        await queue.start()
        done: list[str] = []

        async def bad():
            raise ConnectionError("Connection refused")

        async def good():
            done.append("ok")

        queue.submit("lan:10.0.0.5:9100", bad)
        queue.submit("lan:10.0.0.5:9100", good)
        await queue.join()
        await queue.stop()
        return done

    assert asyncio.run(scenario()) == ["ok"]


def test_run_waits_for_result_and_raises_the_failure():
    async def scenario():
        queue = PrintQueue(delay_seconds=0)
        await queue.start()

        async def ok():
            return "sent"

        async def bad():
            raise ConnectionError("Connection refused")

        result = await queue.run("lan:10.0.0.5:9100", ok)
        with pytest.raises(ConnectionError):
            await queue.run("lan:10.0.0.5:9100", bad)
        await queue.stop()
        return result

    assert asyncio.run(scenario()) == "sent"


def test_run_without_started_queue_runs_directly():
    queue = PrintQueue(delay_seconds=5)

    async def ok():
        return "sent"

    assert queue.running is False
    assert asyncio.run(queue.run("lan:10.0.0.5:9100", ok)) == "sent"


def test_submit_without_started_queue_is_an_error_not_a_silent_drop():
    queue = PrintQueue()

    async def scenario():
        async def slip():
            return None

        with pytest.raises(RuntimeError):
            queue.submit("lan:10.0.0.5:9100", slip)

    asyncio.run(scenario())


def test_stop_releases_callers_still_waiting():
    async def scenario():
        queue = PrintQueue(delay_seconds=0)
        await queue.start()
        gate = asyncio.Event()

        async def blocked():
            await gate.wait()

        async def never_sent():
            return "sent"

        queue.submit("lan:10.0.0.5:9100", blocked)
        waiter = asyncio.create_task(queue.run("lan:10.0.0.5:9100", never_sent))
        await asyncio.sleep(0.01)
        await queue.stop()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, timeout=1)
        return queue.running

    assert asyncio.run(scenario()) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 1.0), ("", 1.0), ("2.5", 2.5), ("0", 0.0), ("-3", 0.0), ("abc", 1.0)],
)
def test_delay_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("PRINT_QUEUE_DELAY_SECONDS", raising=False)
    else:
        monkeypatch.setenv("PRINT_QUEUE_DELAY_SECONDS", raw)
    assert delay_from_env() == expected


def test_queue_keys_identify_one_physical_printer():
    assert lan_key(" 192.168.1.50 ", 9100) == lan_key("192.168.1.50", 9100)
    assert lan_key("192.168.1.50", 9100) != lan_key("192.168.1.51", 9100)
    assert lan_key("192.168.1.50", 9100) != lan_key("192.168.1.50", 9101)
    assert windows_key("POS-80") == windows_key("pos-80 ")
    assert file_key("food") != file_key("drinks")


# —— 2. HTTP contract (queue not started → slips sent inside the request) ——


def test_submit_records_one_printed_job_per_line(client, db_session, auth_headers, printer, file_backend):
    table, tea, mohinga = _seed_menu(db_session)
    res = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 2), (mohinga.id, 1)])
    assert res.status_code == 200, res.text
    assert res.json()["warning"] is None

    order_id = res.json()["id"]
    jobs = _jobs(db_session, order_id)
    assert [(j.kind, j.route, j.print_status, j.attempts) for j in jobs] == [
        ("kitchen", "drinks", "printed", 1),
        ("kitchen", "food", "printed", 1),
    ]
    assert all(j.error_message is None and j.printed_at is not None for j in jobs)
    line_ids = {
        oi.id for oi in db_session.query(OrderItem).filter(OrderItem.order_id == order_id)
    }
    assert {j.order_item_id for j in jobs} == line_ids
    # The printer received exactly what was stored.
    assert [c["ticket"]["item_name"] for c in printer.calls] == [tea.name, mohinga.name]
    assert printer.calls[0]["ticket"]["quantity"] == 2
    assert printer.calls[0]["ticket"]["order_id"] == order_id


def test_submit_with_printer_failure_saves_order_and_marks_jobs_failed(
    client, db_session, auth_headers, printer, file_backend
):
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga = _seed_menu(db_session)
    res = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1), (mohinga.id, 2)])

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_amount"] == 1500.0 + 2 * 3500.0
    order = db_session.query(Order).filter(Order.id == body["id"]).first()
    assert order.status in ("open", "dining")
    jobs = _jobs(db_session, body["id"])
    assert [j.print_status for j in jobs] == ["failed", "failed"]
    assert {j.error_message for j in jobs} == {"Connection refused"}
    assert all(j.printed_at is None and j.attempts == 1 for j in jobs)


def test_retry_print_reprints_only_failed_jobs(client, db_session, auth_headers, printer, file_backend):
    table, tea, mohinga = _seed_menu(db_session)
    waiter = auth_headers("waiter")

    # Tea prints, mohinga fails.
    async def flaky(route, ticket, **kwargs):
        if ticket["item_name"] == mohinga.name:
            raise TimeoutError("timed out")
        await printer.kitchen(route, ticket, **kwargs)

    import services.printing.print_jobs as jobs_module

    original = jobs_module.dispatch_kitchen_ticket
    jobs_module.dispatch_kitchen_ticket = flaky
    try:
        res = _submit(client, waiter, table.id, [(tea.id, 1), (mohinga.id, 1)])
    finally:
        jobs_module.dispatch_kitchen_ticket = original
    order_id = res.json()["id"]
    total_before = res.json()["total_amount"]
    assert [j.print_status for j in _jobs(db_session, order_id)] == ["printed", "failed"]
    printer.calls.clear()

    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert (body["order_id"], body["requeued"], body["skipped"]) == (order_id, 1, 0)
    assert [(j["item_label"], j["print_status"]) for j in body["jobs"]] == [
        (f"{mohinga.name} x1", "printed")
    ]
    # Only the failed slip was sent again, with the stored content.
    assert [c["ticket"]["item_name"] for c in printer.calls] == [mohinga.name]

    jobs = _jobs(db_session, order_id)
    assert [(j.print_status, j.attempts, j.error_message) for j in jobs] == [
        ("printed", 1, None),
        ("printed", 2, None),
    ]
    # Retrying again must not print anything twice.
    printer.calls.clear()
    again = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter)
    assert again.status_code == 200
    assert (again.json()["requeued"], again.json()["skipped"]) == (0, 0)
    assert printer.calls == []
    # Printing never touches money.
    db_session.expire_all()
    assert db_session.query(Order).filter(Order.id == order_id).first().total_amount == total_before


def test_retry_print_still_failing_stays_failed_with_new_reason(
    client, db_session, auth_headers, printer, file_backend
):
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)]).json()["id"]

    printer.fail_with = TimeoutError("timed out")
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=auth_headers("waiter"))
    assert retry.json()["requeued"] == 1
    (job,) = _jobs(db_session, order_id)
    assert (job.print_status, job.error_message, job.attempts) == ("failed", "timed out", 2)


def test_retry_print_skips_cancelled_lines(client, db_session, auth_headers, printer, file_backend):
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, mohinga = _seed_menu(db_session)
    waiter = auth_headers("waiter")
    order_id = _submit(client, waiter, table.id, [(tea.id, 1), (mohinga.id, 1)]).json()["id"]

    tea_job, mohinga_job = _jobs(db_session, order_id)
    line = db_session.query(OrderItem).filter(OrderItem.id == tea_job.order_item_id).first()
    line.item_status = "cancelled"
    db_session.commit()

    listed = client.get("/api/print-jobs/failed", headers=waiter).json()
    assert tea_job.id not in {j["id"] for j in listed}
    assert mohinga_job.id in {j["id"] for j in listed}

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=waiter)
    assert (retry.json()["requeued"], retry.json()["skipped"]) == (1, 1)
    assert [c["ticket"]["item_name"] for c in printer.calls] == [mohinga.name]
    statuses = {j.id: j.print_status for j in _jobs(db_session, order_id)}
    assert statuses == {tea_job.id: "failed", mohinga_job.id: "printed"}


def test_retry_print_on_cancelled_order_prints_nothing(
    client, db_session, auth_headers, printer, file_backend
):
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)]).json()["id"]
    order = db_session.query(Order).filter(Order.id == order_id).first()
    order.status = "cancelled"
    db_session.commit()

    printer.fail_with = None
    printer.calls.clear()
    retry = client.post(f"/api/orders/{order_id}/retry-print", headers=auth_headers("waiter"))
    assert retry.status_code == 200
    assert (retry.json()["requeued"], retry.json()["skipped"]) == (0, 1)
    assert printer.calls == []


def test_retry_print_unknown_order_is_404(client, auth_headers):
    res = client.post("/api/orders/99999999/retry-print", headers=auth_headers("waiter"))
    assert res.status_code == 404
    res = client.get("/api/orders/99999999/print-jobs", headers=auth_headers("waiter"))
    assert res.status_code == 404


def test_print_job_endpoints_role_enforcement(client, db_session, auth_headers, printer, file_backend):
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)]).json()["id"]

    paths = [
        ("post", f"/api/orders/{order_id}/retry-print"),
        ("get", f"/api/orders/{order_id}/print-jobs"),
        ("get", "/api/print-jobs/failed"),
    ]
    for method, path in paths:
        assert getattr(client, method)(path).status_code == 401, path
        assert getattr(client, method)(path, headers=auth_headers("account")).status_code == 403, path
        for role in ("waiter", "cashier", "admin", "root"):
            res = getattr(client, method)(path, headers=auth_headers(role))
            assert res.status_code == 200, (role, path, res.text)


def test_checkout_queues_receipt_and_waiter_cannot_reprint_it(
    client, db_session, auth_headers, printer, file_backend
):
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 2)]).json()["id"]

    printer.fail_with = ConnectionError("Connection refused")
    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 5000.0, "issue_receipt": True},
    )
    assert checkout.status_code == 200, checkout.text
    paid = checkout.json()
    assert (paid["status"], paid["warning"]) == ("paid", None)
    assert (paid["total_amount"], paid["change_amount"]) == (3000.0, 2000.0)

    receipt = [j for j in _jobs(db_session, order_id) if j.kind == "receipt"]
    assert [(j.route, j.print_status, j.error_message) for j in receipt] == [
        ("cashier", "failed", "Connection refused")
    ]

    # Waiter: sees no receipt in the failed list and cannot reprint it.
    waiter_list = client.get("/api/print-jobs/failed", headers=auth_headers("waiter")).json()
    assert receipt[0].id not in {j["id"] for j in waiter_list}
    printer.fail_with = None
    printer.calls.clear()
    as_waiter = client.post(f"/api/orders/{order_id}/retry-print", headers=auth_headers("waiter"))
    assert (as_waiter.json()["requeued"], as_waiter.json()["skipped"]) == (0, 1)
    assert printer.calls == []

    # Cashier: sees it and reprints the same receipt.
    cashier_list = client.get("/api/print-jobs/failed", headers=auth_headers("cashier")).json()
    listed = next(j for j in cashier_list if j["id"] == receipt[0].id)
    assert (listed["item_label"], listed["kind"]) == ("Receipt", "receipt")
    assert listed["location_label"].startswith("Table ")
    as_cashier = client.post(f"/api/orders/{order_id}/retry-print", headers=auth_headers("cashier"))
    assert as_cashier.json()["requeued"] == 1
    (call,) = printer.calls
    assert (call["kind"], call["order_id"], call["grand_total"]) == ("receipt", order_id, 3000.0)
    assert (call["amount_tendered"], call["change_amount"]) == (5000.0, 2000.0)
    db_session.expire_all()
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert (order.status, order.total_amount) == ("paid", 3000.0)


def test_checkout_without_receipt_creates_no_job(client, db_session, auth_headers, printer, file_backend):
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)]).json()["id"]
    printer.calls.clear()
    checkout = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 1500.0, "issue_receipt": False},
    )
    assert checkout.status_code == 200, checkout.text
    assert [j.kind for j in _jobs(db_session, order_id)] == ["kitchen"]
    assert printer.calls == []


def test_failed_list_contract_and_hours_validation(
    client, db_session, auth_headers, printer, file_backend
):
    printer.fail_with = ConnectionError("Connection refused")
    table, tea, _ = _seed_menu(db_session)
    order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 3)]).json()["id"]
    (job,) = _jobs(db_session, order_id)

    listed = client.get("/api/print-jobs/failed", headers=auth_headers("waiter")).json()
    item = next(j for j in listed if j["id"] == job.id)
    assert set(item) == {
        "id", "order_id", "order_item_id", "kind", "route", "print_status",
        "error_message", "attempts", "item_label", "location_label",
        "created_at", "updated_at", "printed_at",
    }
    assert item["print_status"] == "failed"
    assert item["item_label"] == f"{tea.name} x3"
    assert item["location_label"].startswith("Table ")
    assert [j["id"] for j in listed] == sorted((j["id"] for j in listed), reverse=True)

    # Outside the time window it is no longer offered for retry.
    job.created_at = job.created_at.replace(year=job.created_at.year - 1)
    db_session.commit()
    listed = client.get("/api/print-jobs/failed?hours=168", headers=auth_headers("waiter")).json()
    assert job.id not in {j["id"] for j in listed}

    for bad in ("0", "169", "abc"):
        res = client.get(f"/api/print-jobs/failed?hours={bad}", headers=auth_headers("waiter"))
        assert res.status_code == 422, bad


def test_submit_still_succeeds_when_slips_cannot_be_queued(
    client, db_session, auth_headers, monkeypatch, file_backend
):
    async def broken(db, job_ids):
        raise RuntimeError("queue exploded")

    monkeypatch.setattr("routers.orders.enqueue_print_jobs", broken)
    table, tea, _ = _seed_menu(db_session)
    res = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)])
    assert res.status_code == 200, res.text
    assert "could not be queued" in res.json()["warning"]
    assert res.json()["total_amount"] == 1500.0


def test_job_result_is_broadcast_as_print_job_updated(
    client, db_session, auth_headers, printer, file_backend
):
    events: list[tuple[str, dict]] = []

    async def notifier(event, data):
        events.append((event, data))

    print_jobs.configure(notifier=notifier)
    try:
        printer.fail_with = ConnectionError("Connection refused")
        table, tea, _ = _seed_menu(db_session)
        order_id = _submit(client, auth_headers("waiter"), table.id, [(tea.id, 1)]).json()["id"]
    finally:
        print_jobs.configure(notifier=None)

    ((event, data),) = events
    assert event == "print_job_updated"
    assert (data["order_id"], data["print_status"], data["error_message"]) == (
        order_id,
        "failed",
        "Connection refused",
    )
    json.dumps(data)  # must be sendable over the WebSocket as-is


def test_startup_marks_interrupted_jobs_failed(db_session):
    order = Order(order_type="takeaway", status="open", total_amount=0.0)
    db_session.add(order)
    db_session.flush()
    pending = PrintJob(order_id=order.id, kind="kitchen", route="food", payload={}, print_status="pending")
    printed = PrintJob(order_id=order.id, kind="kitchen", route="food", payload={}, print_status="printed")
    db_session.add_all([pending, printed])
    db_session.commit()
    try:
        assert print_jobs.mark_interrupted_jobs_failed(db_session) >= 1
        db_session.expire_all()
        assert (pending.print_status, pending.error_message) == (
            "failed",
            "Server restarted before this slip was printed",
        )
        assert printed.print_status == "printed"
        assert db_session.query(PrintJob).filter(PrintJob.print_status == "pending").count() == 0
    finally:
        db_session.delete(order)
        db_session.commit()


def test_print_status_is_constrained_to_three_values(db_session):
    from sqlalchemy.exc import IntegrityError

    order = Order(order_type="takeaway", status="open", total_amount=0.0)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        PrintJob(order_id=order.id, kind="kitchen", route="food", payload={}, print_status="printing")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# —— 3. real background queue against the database ——


@pytest.fixture()
def live_queue(test_engine, monkeypatch):
    """A started-on-demand queue wired like the app lifespan wires it."""
    queue = PrintQueue(delay_seconds=0.03)
    events: list[tuple[str, dict]] = []

    async def notifier(event, data):
        events.append((event, data))

    monkeypatch.setattr("services.printing.print_jobs.get_print_queue", lambda: queue)
    monkeypatch.setattr("services.printing.service.get_print_queue", lambda: queue)
    print_jobs.configure(
        notifier=notifier,
        session_factory=sessionmaker(autocommit=False, autoflush=False, bind=test_engine),
    )
    yield queue, events
    print_jobs.configure()


def _seed_order_with_jobs(db_session, count: int, *, route: str = "food"):
    table, tea, mohinga = _seed_menu(db_session)
    order = Order(table_id=table.id, table_number=table.id, order_type="dine_in", status="open", total_amount=0.0)
    db_session.add(order)
    db_session.flush()
    jobs = []
    for n in range(count):
        line = OrderItem(
            order_id=order.id,
            menu_item_id=mohinga.id,
            quantity=1,
            subtotal=3500.0,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
        db_session.add(line)
        db_session.flush()
        jobs.append(
            print_jobs.create_kitchen_job(
                db_session,
                order_id=order.id,
                order_item_id=line.id,
                route=route,
                ticket={"item_name": f"slip-{n}", "quantity": 1, "table_number": 7, "order_id": order.id, "date": ""},
                order_type="dine_in",
                customer_name=None,
            )
        )
    db_session.commit()
    return order.id, [job.id for job in jobs]


def test_background_queue_returns_first_then_prints_in_order_without_overlap(
    db_session, live_queue, printer, file_backend
):
    queue, events = live_queue
    printer.hold = 0.01
    order_id, job_ids = _seed_order_with_jobs(db_session, 4)

    async def scenario():
        await queue.start()
        await print_jobs.enqueue_print_jobs(db_session, job_ids)
        statuses_at_return = [j.print_status for j in _jobs(db_session, order_id)]
        calls_at_return = len(printer.calls)
        await queue.join()
        await queue.stop()
        return statuses_at_return, calls_at_return

    statuses_at_return, calls_at_return = asyncio.run(scenario())
    # The request side is not held up by the printer.
    assert statuses_at_return == ["pending"] * 4
    assert calls_at_return == 0

    assert [j.print_status for j in _jobs(db_session, order_id)] == ["printed"] * 4
    assert [c["ticket"]["item_name"] for c in printer.calls] == [f"slip-{n}" for n in range(4)]
    assert printer.max_active == 1
    for previous, following in zip(printer.calls, printer.calls[1:]):
        assert following["started"] - previous["ended"] >= 0.025
    assert [e for e, _ in events] == ["print_job_updated"] * 4
    assert [d["print_status"] for _, d in events] == ["printed"] * 4


def test_background_queue_failure_is_recorded_and_worker_continues(
    db_session, live_queue, monkeypatch, file_backend
):
    queue, events = live_queue
    sent: list[str] = []

    async def dispatch(route, ticket, **kwargs):
        if ticket["item_name"] == "slip-1":
            raise ConnectionResetError("Connection reset by peer")
        sent.append(ticket["item_name"])

    monkeypatch.setattr("services.printing.print_jobs.dispatch_kitchen_ticket", dispatch)
    order_id, job_ids = _seed_order_with_jobs(db_session, 3)

    async def scenario():
        await queue.start()
        await print_jobs.enqueue_print_jobs(db_session, job_ids)
        await queue.join()
        await queue.stop()

    asyncio.run(scenario())
    jobs = _jobs(db_session, order_id)
    assert [(j.print_status, j.error_message) for j in jobs] == [
        ("printed", None),
        ("failed", "Connection reset by peer"),
        ("printed", None),
    ]
    assert sent == ["slip-0", "slip-2"]
    assert [d["print_status"] for _, d in events] == ["printed", "failed", "printed"]


def test_line_cancelled_while_waiting_in_queue_is_not_printed(
    db_session, live_queue, printer, file_backend
):
    queue, _events = live_queue
    order_id, job_ids = _seed_order_with_jobs(db_session, 2)
    second = db_session.query(PrintJob).filter(PrintJob.id == job_ids[1]).first()

    async def scenario():
        await queue.start()
        await print_jobs.enqueue_print_jobs(db_session, job_ids)
        # Cancelled after queueing, before its turn.
        line = db_session.query(OrderItem).filter(OrderItem.id == second.order_item_id).first()
        line.item_status = "cancelled"
        db_session.commit()
        await queue.join()
        await queue.stop()

    asyncio.run(scenario())
    first_job, second_job = _jobs(db_session, order_id)
    assert first_job.print_status == "printed"
    assert second_job.print_status == "failed"
    assert second_job.error_message == "Skipped: item was cancelled"
    assert second_job.attempts == 0
    assert [c["ticket"]["item_name"] for c in printer.calls] == ["slip-0"]


def test_kitchen_bar_and_cashier_get_separate_queues(db_session, monkeypatch):
    for name in ("PRINTER_FOOD_HOST", "PRINTER_DRINKS_HOST", "PRINTER_CASHIER_HOST"):
        monkeypatch.delenv(name, raising=False)
    _set_backend(db_session, "escpos_network")
    seed_default_printers(db_session, force=True)
    db_session.query(Printer).delete()
    kitchen = Printer(name="K", host="192.168.1.60", port=9100, role="kitchen", is_active=True)
    bar = Printer(name="B", host="192.168.1.61", port=9100, role="bar", is_active=True)
    cashier = Printer(
        name="C", host="192.168.1.62", port=9100, role="cashier", is_active=True,
        windows_printer_name="POS-80",
    )
    db_session.add_all([kitchen, bar, cashier])
    db_session.commit()
    try:
        def key(route, printer_id=None):
            return print_jobs.print_target_key(
                db_session,
                PrintJob(order_id=1, kind="kitchen", route=route, printer_id=printer_id, payload={}),
            )

        assert key("food") == lan_key("192.168.1.60", 9100)
        assert key("drinks") == lan_key("192.168.1.61", 9100)
        assert key("cashier", cashier.id) == lan_key("192.168.1.62", 9100)

        # No bar printer: drinks fall back to the kitchen printer and must share its queue.
        bar.is_active = False
        db_session.commit()
        assert key("drinks") == key("food")

        _set_backend(db_session, "windows_printer")
        assert key("cashier", cashier.id) == windows_key("POS-80")
        assert key("food") == lan_key("192.168.1.60", 9100)

        _set_backend(db_session, "file")
        assert (key("food"), key("drinks"), key("cashier")) == (
            file_key("food"), file_key("drinks"), file_key("cashier"),
        )
    finally:
        db_session.query(Printer).delete()
        db_session.commit()
        # Bulk delete leaves the deleted rows in the identity map; the re-seed
        # reuses their ids.
        db_session.expunge_all()
        _set_backend(db_session, "file")
        seed_default_printers(db_session, force=True)


def test_print_test_waits_behind_live_slips_for_the_same_printer(
    db_session, live_queue, monkeypatch
):
    from services.printing.service import dispatch_printer_test

    queue, _events = live_queue
    _set_backend(db_session, "escpos_network")
    row = Printer(name="PQ Kitchen", host="192.168.1.70", port=9100, role="kitchen", is_active=True)
    db_session.add(row)
    db_session.commit()
    order: list[str] = []

    def fake_lan(endpoint, payload, **kwargs):
        order.append(f"test-print:{endpoint.host}")

    monkeypatch.setattr("services.printing.service.print_image_to_network", fake_lan)

    async def scenario():
        await queue.start()

        async def live_slip():
            await asyncio.sleep(0.02)
            order.append("live-slip")

        queue.submit(lan_key("192.168.1.70", 9100), live_slip)
        result = await dispatch_printer_test(printer_id=row.id, db=db_session)
        await queue.stop()
        return result

    try:
        result = asyncio.run(scenario())
        assert result["ok"] is True
        assert order == ["live-slip", "test-print:192.168.1.70"]
    finally:
        db_session.delete(row)
        db_session.commit()
        _set_backend(db_session, "file")


# —— real app lifespan + real TCP sockets (isolated process and database) ——

_LIFESPAN_SCRIPT = textwrap.dedent(
    """
    import json, socket, threading, time

    from fastapi.testclient import TestClient

    import main
    from database import Base, SessionLocal, engine
    from models import Category, MenuItem, Order, PrintJob, Table, Zone
    from scripts.seed_root import seed_root

    class FakePrinter:
        def __init__(self):
            self.arrivals = []
            self.sock = socket.socket()
            self.sock.bind(("127.0.0.1", 0))
            self.sock.listen(16)
            self.port = self.sock.getsockname()[1]
            threading.Thread(target=self._serve, daemon=True).start()

        def _serve(self):
            while True:
                try:
                    conn, _ = self.sock.accept()
                except OSError:
                    return
                arrived = time.monotonic()
                size = 0
                with conn:
                    while True:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        size += len(chunk)
                if size:  # health probes connect and send nothing
                    self.arrivals.append(arrived)

    # State left behind by a previous run of the server.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    old = Order(order_type="takeaway", status="open", total_amount=0.0)
    db.add(old); db.flush()
    db.add(PrintJob(order_id=old.id, kind="kitchen", route="food", payload={}, print_status="pending"))
    db.commit()
    old_id = old.id
    db.close()

    out = {}
    printer = FakePrinter()
    dead = socket.socket(); dead.bind(("127.0.0.1", 0)); dead_port = dead.getsockname()[1]; dead.close()

    def wait_for(fn, timeout=10.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = fn()
            if value:
                return value
            time.sleep(0.05)
        return fn()

    with TestClient(main.app) as c:
        out["queue_running_after_startup"] = main.app.state.print_queue._loop is not None
        out["delay"] = main.app.state.print_queue.delay_seconds
        seed_root("root", "smoke123")
        token = c.post("/api/auth/login", json={"username": "root", "password": "smoke123", "device_id": "t"}).json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}
        out["interrupted"] = [(j["print_status"], j["error_message"]) for j in c.get(f"/api/orders/{old_id}/print-jobs", headers=H).json()]

        db = SessionLocal()
        zone = Zone(name="Z"); db.add(zone); db.flush()
        table = Table(name="T1", zone_id=zone.id, status="available")
        food = Category(name="Food", printer_route="food")
        db.add_all([table, food]); db.flush()
        item = MenuItem(name="Mohinga", price=3500.0, category_id=food.id, is_available=True, modifiers_config=[])
        db.add(item); db.commit()
        table_id, item_id = table.id, item.id
        db.close()

        kitchen = next(p for p in c.get("/api/printers", headers=H).json() if p["role"] == "kitchen")
        c.put("/api/admin/kitchen-printers", headers=H, json={"backend": "escpos_network", "render_mode": "text", "paper_width_px": 576, "routes": []})
        c.put(f"/api/printers/{kitchen['id']}", headers=H, json={"host": "127.0.0.1", "port": printer.port})

        def submit(lines):
            return c.post("/api/orders/submit", headers=H, json={"table_id": table_id, "order_type": "dine_in",
                "items": [{"menu_item_id": item_id, "quantity": 1, "selected_modifiers": []} for _ in range(lines)]})

        def statuses(order_id):
            return [j["print_status"] for j in c.get(f"/api/orders/{order_id}/print-jobs", headers=H).json()]

        began = time.monotonic()
        res = submit(4)
        out["submit_seconds"] = time.monotonic() - began
        out["submit_status"] = res.status_code
        out["submit_warning"] = res.json().get("warning")
        order_id = res.json()["id"]
        out["all_printed"] = bool(wait_for(lambda: statuses(order_id) == ["printed"] * 4))
        out["slips_received"] = len(printer.arrivals)
        out["gaps"] = [b - a for a, b in zip(printer.arrivals, printer.arrivals[1:])]

        # Printer unreachable -> failed, order still saved.
        c.put(f"/api/printers/{kitchen['id']}", headers=H, json={"host": "127.0.0.1", "port": dead_port})
        res = submit(1)
        out["offline_submit_status"] = res.status_code
        out["offline_warning"] = res.json().get("warning")
        out["failed_recorded"] = bool(wait_for(lambda: "failed" in statuses(order_id)))
        failed = [j for j in c.get("/api/print-jobs/failed", headers=H).json() if j["order_id"] == order_id]
        out["failed_listed"] = [(j["print_status"], bool(j["error_message"])) for j in failed]

        # Admin fixes the printer address, staff press Retry.
        c.put(f"/api/printers/{kitchen['id']}", headers=H, json={"host": "127.0.0.1", "port": printer.port})
        before = len(printer.arrivals)
        retry = c.post(f"/api/orders/{order_id}/retry-print", headers=H)
        out["retry"] = [retry.status_code, retry.json()["requeued"], retry.json()["skipped"]]
        out["retry_printed"] = bool(wait_for(lambda: statuses(order_id) == ["printed"] * 5))
        out["retry_slips_received"] = len(printer.arrivals) - before
        out["failed_list_empty_after_retry"] = not [j for j in c.get("/api/print-jobs/failed", headers=H).json() if j["order_id"] == order_id]

    out["queue_stopped_after_shutdown"] = main.app.state.print_queue._loop is None
    print("RESULT=" + json.dumps(out))
    """
)


def test_real_app_lifespan_queue_over_tcp(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PRINTER_")}
    env.update(
        DATABASE_URL=f"sqlite:///{tmp_path / 'queue.db'}",
        KITCHEN_PRINT_OUTPUT_DIR=str(tmp_path),
        PRINT_QUEUE_DELAY_SECONDS="0.3",
        PYTHONPATH=os.pathsep.join(
            [str(REPO_ROOT), str(REPO_ROOT / ".pip_pkgs"), env.get("PYTHONPATH", "")]
        ),
    )
    script = (
        "from services.printing import print_log\n"
        f"print_log.PRINT_LOG_DIR = __import__('pathlib').Path({str(tmp_path / 'logs')!r})\n"
        "print_log.PRINT_LOG_FILE = print_log.PRINT_LOG_DIR / 'print.log'\n" + _LIFESPAN_SCRIPT
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("RESULT="))
    out = json.loads(line[len("RESULT="):])

    assert out["queue_running_after_startup"] is True
    assert out["delay"] == 0.3
    assert out["interrupted"] == [["failed", "Server restarted before this slip was printed"]]

    # Submit returned before four paced slips could have printed (3 pauses = 0.9s).
    assert out["submit_status"] == 200
    assert out["submit_warning"] is None
    assert out["submit_seconds"] < 0.8
    assert out["all_printed"] is True
    assert out["slips_received"] == 4
    assert all(gap >= 0.28 for gap in out["gaps"]), out["gaps"]

    assert out["offline_submit_status"] == 200
    assert "offline" in (out["offline_warning"] or "").lower()
    assert out["failed_recorded"] is True
    assert out["failed_listed"] == [["failed", True]]

    assert out["retry"] == [200, 1, 0]
    assert out["retry_printed"] is True
    assert out["retry_slips_received"] == 1
    assert out["failed_list_empty_after_retry"] is True
    assert out["queue_stopped_after_shutdown"] is True
