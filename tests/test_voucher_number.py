"""Daily voucher number: restarts at 1 every day, written with the date.

Spec: specs/feature-voucher-number
"""

from __future__ import annotations

import itertools
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import routers.orders as orders_router
import services.voucher as voucher
from models import Base, Order
from services.printing.receipt import build_receipt_text
from test_payment_kpay_mmqr import _checkout, _open_order, _pay_on

REPO_ROOT = Path(__file__).resolve().parents[1]
VOUCHER_RE = re.compile(r"^\d{8}-\d{4,}$")

# The test database is shared by the whole suite, so every test works on a day
# of its own (far in the future) and sees a clean sequence.
_days = itertools.count(30000101)


@pytest.fixture()
def day(monkeypatch) -> str:
    chosen = str(next(_days))
    monkeypatch.setattr(voucher, "voucher_date_for", lambda now_utc=None: chosen)
    return chosen


def _pay(client, db_session, auth_headers, *, total=1000.0) -> dict:
    order = _open_order(db_session, total=total)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=total)
    assert res.status_code == 200, res.text
    return res.json()


# —— day boundary (Myanmar time, UTC+06:30) ——


@pytest.mark.parametrize(
    "utc, expected",
    [
        (datetime(2026, 11, 19, 0, 0, 0), "20261119"),  # 06:30 in Myanmar
        (datetime(2026, 11, 19, 17, 29, 59), "20261119"),  # 23:59:59 in Myanmar
        (datetime(2026, 11, 19, 17, 30, 0), "20261120"),  # 00:00:00 next day in Myanmar
        (datetime(2026, 11, 19, 23, 59, 59), "20261120"),
        (datetime(2026, 12, 31, 17, 30, 0), "20270101"),  # year end
        (datetime(2028, 2, 28, 17, 30, 0), "20280229"),  # leap day
    ],
)
def test_the_day_changes_at_midnight_myanmar_time(utc, expected):
    assert voucher.voucher_date_for(utc) == expected


def test_format_is_date_dash_four_digits():
    assert voucher.format_voucher_no("20261119", 1) == "20261119-0001"
    assert voucher.format_voucher_no("20261119", 42) == "20261119-0042"
    assert voucher.format_voucher_no("20261119", 9999) == "20261119-9999"
    assert voucher.format_voucher_no("20261119", 10000) == "20261119-10000"


def test_voucher_no_is_derived_from_its_two_parts():
    assert Order().voucher_no is None
    assert Order(voucher_date="20261119").voucher_no is None
    assert Order(voucher_seq=3).voucher_no is None
    assert Order(voucher_date="20261119", voucher_seq=3).voucher_no == "20261119-0003"


# —— the sequence ——


def test_first_voucher_of_a_day_is_one_then_counts_up(client, db_session, auth_headers, day):
    numbers = [_pay(client, db_session, auth_headers)["voucher_no"] for _ in range(3)]
    assert numbers == [f"{day}-0001", f"{day}-0002", f"{day}-0003"]


def test_a_new_day_starts_again_at_one(client, db_session, auth_headers, monkeypatch):
    first_day, second_day = str(next(_days)), str(next(_days))
    current = {"day": first_day}
    monkeypatch.setattr(voucher, "voucher_date_for", lambda now_utc=None: current["day"])

    a = _pay(client, db_session, auth_headers)["voucher_no"]
    b = _pay(client, db_session, auth_headers)["voucher_no"]
    current["day"] = second_day
    c = _pay(client, db_session, auth_headers)["voucher_no"]
    current["day"] = first_day  # the first day carries on where it stopped
    d = _pay(client, db_session, auth_headers)["voucher_no"]
    assert [a, b, c, d] == [f"{first_day}-0001", f"{first_day}-0002", f"{second_day}-0001", f"{first_day}-0003"]


def test_the_real_clock_gives_a_valid_voucher_for_today(client, db_session, auth_headers):
    body = _pay(client, db_session, auth_headers)
    assert VOUCHER_RE.match(body["voucher_no"])
    assert body["voucher_no"].startswith(voucher.voucher_date_for())


def test_unpaid_and_cancelled_orders_have_no_voucher_and_leave_no_gap(
    client, db_session, auth_headers, day
):
    open_order = _open_order(db_session)
    cancelled = _open_order(db_session)
    assert client.post(f"/api/orders/{cancelled.id}/cancel", headers=auth_headers("cashier")).status_code == 200

    for order_id in (open_order.id, cancelled.id):
        details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("cashier")).json()
        assert details["voucher_no"] is None

    assert _pay(client, db_session, auth_headers)["voucher_no"] == f"{day}-0001"


def test_a_failed_checkout_does_not_use_up_a_number(client, db_session, auth_headers, day):
    order = _open_order(db_session, total=1000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1.0)
    assert res.status_code == 400
    assert client.get(f"/api/orders/{order.id}/details", headers=auth_headers("cashier")).json()["voucher_no"] is None
    assert _pay(client, db_session, auth_headers)["voucher_no"] == f"{day}-0001"


def test_checking_out_again_keeps_the_voucher(client, db_session, auth_headers, day):
    order = _open_order(db_session, total=1000.0)
    first = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1000.0)
    again = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1000.0)
    assert first.status_code == 200
    assert again.status_code in (200, 400, 409), again.text
    db_session.expire_all()
    stored = db_session.query(Order).filter(Order.id == order.id).one()
    assert stored.voucher_no == first.json()["voucher_no"] == f"{day}-0001"
    # The next order still gets the next number, nothing was re-issued.
    assert _pay(client, db_session, auth_headers)["voucher_no"] == f"{day}-0002"


def test_the_client_cannot_choose_the_number(client, db_session, auth_headers, day):
    order = _open_order(db_session, total=1000.0)
    res = _checkout(
        client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1000.0,
        voucher_no="19990101-0001", voucher_date="19990101", voucher_seq=1,
    )
    assert res.status_code == 200, res.text
    assert res.json()["voucher_no"] == f"{day}-0001"


@pytest.mark.parametrize("role, status", [("waiter", 403), ("cashier", 200), ("admin", 200), ("root", 200)])
def test_checkout_roles_are_unchanged(client, db_session, auth_headers, day, role, status):
    order = _open_order(db_session, total=1000.0)
    res = _checkout(client, auth_headers(role), order.id, payment_method="cash", amount_tendered=1000.0)
    assert res.status_code == status, res.text
    assert (res.json().get("voucher_no") is not None) == (status == 200)


def test_checkout_without_login_is_refused_and_unpaid(client, db_session, day):
    order = _open_order(db_session, total=1000.0)
    res = _checkout(client, {}, order.id, payment_method="cash", amount_tendered=1000.0)
    assert res.status_code in (401, 403)
    db_session.expire_all()
    assert db_session.query(Order).filter(Order.id == order.id).one().voucher_no is None


# —— two checkouts taking the same number ——


def _force_clash(monkeypatch, db_session, taken_day, *, times):
    """Make the first `times` assignments pick a number that is already used."""
    real = orders_router.assign_voucher
    calls = {"n": 0}

    def clashing(db, order, now_utc=None):
        calls["n"] += 1
        if calls["n"] <= times:
            order.voucher_date, order.voucher_seq = taken_day, 1
            return order.voucher_no
        return real(db, order, now_utc)

    monkeypatch.setattr(orders_router, "assign_voucher", clashing)
    return calls


def test_a_number_clash_is_retried_and_the_payment_is_recorded_once(
    client, db_session, auth_headers, day, monkeypatch
):
    assert _pay(client, db_session, auth_headers)["voucher_no"] == f"{day}-0001"  # takes seq 1
    calls = _force_clash(monkeypatch, db_session, day, times=1)

    order = _open_order(db_session, total=1000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1000.0)

    assert res.status_code == 200, res.text
    assert res.json()["voucher_no"] == f"{day}-0002"
    assert calls["n"] == 2
    db_session.expire_all()
    stored = db_session.query(Order).filter(Order.id == order.id).one()
    assert (stored.status, stored.voucher_no, stored.cash_amount) == ("paid", f"{day}-0002", 1000.0)
    same_number = db_session.query(Order).filter(Order.voucher_date == day).count()
    assert same_number == 2


def test_after_five_clashes_the_checkout_answers_503_and_the_order_stays_unpaid(
    client, db_session, auth_headers, day, monkeypatch
):
    assert _pay(client, db_session, auth_headers)["voucher_no"] == f"{day}-0001"
    calls = _force_clash(monkeypatch, db_session, day, times=99)

    order = _open_order(db_session, total=1000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=1000.0)

    assert res.status_code == 503, res.text
    assert calls["n"] == voucher.MAX_VOUCHER_ATTEMPTS
    db_session.expire_all()
    stored = db_session.query(Order).filter(Order.id == order.id).one()
    assert stored.status == "open"
    assert stored.payment_method is None and stored.voucher_no is None
    assert stored.checked_out_by_id is None


def test_the_unique_index_refuses_a_second_order_with_the_same_number(db_session, day):
    a = Order(order_type="takeaway", status="paid", total_amount=1.0, voucher_date=day, voucher_seq=1)
    b = Order(order_type="takeaway", status="paid", total_amount=1.0, voucher_date=day, voucher_seq=1)
    db_session.add(a)
    db_session.commit()
    db_session.add(b)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_many_orders_without_a_voucher_do_not_conflict(db_session):
    db_session.add_all(
        [Order(order_type="takeaway", status="open", total_amount=1.0) for _ in range(3)]
    )
    db_session.commit()  # NULL voucher parts never clash


# —— where the voucher shows ——


def test_voucher_is_in_checkout_details_status_update_and_history(
    client, db_session, auth_headers, day
):
    day_dt = datetime(2034, 4, 5, 10, 0, 0)
    order = _open_order(db_session, total=800.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=800.0)
    number = res.json()["voucher_no"]
    assert number == f"{day}-0001"

    details = client.get(f"/api/orders/{order.id}/details", headers=auth_headers("waiter"))
    assert details.json()["voucher_no"] == number

    db_session.query(Order).filter(Order.id == order.id).update({Order.created_at: day_dt})
    db_session.commit()
    hist = client.get("/api/orders/daily-history?date=2034-04-05", headers=auth_headers("cashier"))
    assert hist.status_code == 200, hist.text
    assert [o["voucher_no"] for o in hist.json()["orders"] if o["id"] == order.id] == [number]

    export = client.get("/api/orders/daily-history/export?date=2034-04-05", headers=auth_headers("cashier"))
    from openpyxl import load_workbook

    rows = list(load_workbook(BytesIO(export.content)).active.iter_rows(values_only=True))
    assert rows[0][:2] == ("Order ID", "Voucher No")
    assert [r[1] for r in rows[1:] if r and r[0] == order.id] == [number]


def test_history_shows_no_voucher_for_an_order_from_before_the_feature(client, db_session, auth_headers):
    old = Order(
        order_type="takeaway", status="paid", total_amount=50.0, payment_method="cash",
        created_at=datetime(2034, 6, 7, 9, 0, 0),
    )
    db_session.add(old)
    db_session.commit()
    hist = client.get("/api/orders/daily-history?date=2034-06-07", headers=auth_headers("cashier"))
    entry = next(o for o in hist.json()["orders"] if o["id"] == old.id)
    assert entry["voucher_no"] is None


def test_status_update_answer_carries_the_voucher(client, db_session, auth_headers, day):
    order = _open_order(db_session, total=500.0)
    item_id = client.get(f"/api/orders/{order.id}/details", headers=auth_headers("waiter")).json()["items"][0]["id"]
    res = client.put(
        f"/api/orders/{order.id}/items/{item_id}/status",
        headers=auth_headers("waiter"), json={"status": "served"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["voucher_no"] is None  # not paid yet


def test_receipt_prints_the_voucher_instead_of_the_order_id():
    text = build_receipt_text(
        order_id=77, voucher_no="20261119-0001", served_by="Waiter", location_label="T1",
        items=[], subtotal=0.0, discount_amount=0.0, tax_amount=0.0, grand_total=0.0, payment_method="cash",
    )
    assert "Voucher: 20261119-0001" in text
    assert "Order: #" not in text


@pytest.mark.parametrize("missing", [None, "", "  "])
def test_receipt_without_a_voucher_keeps_the_order_id(missing):
    text = build_receipt_text(
        order_id=77, voucher_no=missing, served_by="Waiter", location_label="T1",
        items=[], subtotal=0.0, discount_amount=0.0, tax_amount=0.0, grand_total=0.0, payment_method="cash",
    )
    assert "Order: #77" in text
    assert "Voucher:" not in text


def test_a_receipt_queued_before_the_feature_still_prints():
    """Old print jobs hold no voucher_no; dispatch must accept them."""
    import inspect

    from services.printing.service import dispatch_cashier_receipt

    parameter = inspect.signature(dispatch_cashier_receipt).parameters["voucher_no"]
    assert parameter.default is None


def test_queued_receipt_carries_the_voucher(client, db_session, auth_headers, day):
    from models import PrintJob

    order = _open_order(db_session, total=900.0)
    res = _checkout(
        client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=900.0,
        issue_receipt=True,
    )
    assert res.status_code == 200, res.text
    job = db_session.query(PrintJob).filter(PrintJob.order_id == order.id, PrintJob.kind == "receipt").one()
    assert job.payload["voucher_no"] == f"{day}-0001"


# —— clearing sales / existing database ——


def test_after_clearing_sales_the_day_starts_again_at_one(tmp_path, day):
    from scripts import clear_sales as script

    engine = create_engine(f"sqlite:///{tmp_path / 'shop.db'}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    for _ in range(3):
        order = Order(order_type="takeaway", status="paid", total_amount=1.0)
        db.add(order)
        db.flush()
        voucher.assign_voucher(db, order)
        db.commit()
    assert [o.voucher_no for o in db.query(Order).order_by(Order.id)] == [f"{day}-000{i}" for i in (1, 2, 3)]

    script.clear_sales(db)

    fresh = Order(order_type="takeaway", status="paid", total_amount=1.0)
    db.add(fresh)
    db.flush()
    assert voucher.assign_voucher(db, fresh) == f"{day}-0001"
    db.close()


def test_startup_adds_the_voucher_columns_and_keeps_existing_sales(tmp_path):
    db_path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    con = sqlite3.connect(db_path)
    con.execute("DROP INDEX ux_orders_voucher")
    con.execute("ALTER TABLE orders DROP COLUMN voucher_date")
    con.execute("ALTER TABLE orders DROP COLUMN voucher_seq")
    con.execute(
        "INSERT INTO orders (id, order_type, status, total_amount, created_at, payment_method) "
        "VALUES (1, 'takeaway', 'paid', 500.0, '2026-11-01 10:00:00', 'cash')"
    )
    con.commit()
    assert "voucher_seq" not in {row[1] for row in con.execute("PRAGMA table_info(orders)")}
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
        "with TestClient(main.app):\n"
        "    print('STARTED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "STARTED" in proc.stdout

    con = sqlite3.connect(db_path)
    columns = {row[1] for row in con.execute("PRAGMA table_info(orders)")}
    indexes = {row[1] for row in con.execute("PRAGMA index_list(orders)")}
    row = con.execute("SELECT total_amount, voucher_date, voucher_seq FROM orders WHERE id = 1").fetchone()
    con.close()
    assert {"voucher_date", "voucher_seq"} <= columns
    assert "ux_orders_voucher" in indexes
    # The old sale is untouched and is not given a voucher.
    assert row == (500.0, None, None)
