"""KPay / MMQR payments and the per-cashier payment report.

Spec: specs/feature-payment-kpay-mmqr
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from auth import hash_password
from models import Base, Category, MenuItem, Order, OrderItem, PrintJob, Table, User, Zone
from services.printing.receipt import build_receipt_text

REPO_ROOT = Path(__file__).resolve().parents[1]


# —— helpers ——


def _open_order(db_session, *, total: float = 10000.0) -> Order:
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"KM-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"KM-T-{suffix}", zone_id=zone.id, status="occupied")
    category = Category(name=f"KM-Cat-{suffix}", printer_route="food")
    db_session.add_all([table, category])
    db_session.flush()
    item = MenuItem(
        name=f"KM-Item-{suffix}", price=total, category_id=category.id,
        is_available=True, modifiers_config=[],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id, table_number=table.id, order_type="dine_in",
        status="open", total_amount=total,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id, menu_item_id=item.id, quantity=1, subtotal=total,
            batch_number=1, batch_status="pending", item_status="pending",
            selected_modifiers=[], unit_tax_at_sale=0.0,
        )
    )
    db_session.commit()
    db_session.refresh(order)
    return order


def _checkout(client, headers, order_id: int, **body):
    body.setdefault("issue_receipt", False)
    return client.put(f"/api/orders/{order_id}/checkout", headers=headers, json=body)


def _stored(db_session, order_id: int) -> Order:
    db_session.expire_all()
    return db_session.query(Order).filter(Order.id == order_id).first()


def _assert_unpaid(db_session, order_id: int) -> None:
    order = _stored(db_session, order_id)
    assert order.status == "open"
    assert order.payment_method is None
    assert (order.cash_amount, order.kpay_amount, order.mmqr_amount) == (None, None, None)
    assert order.checked_out_by_id is None


def _pay_on(client, db_session, headers, day: datetime, *, total: float, **body) -> int:
    """Check out through the API, then move the order to `day` (reports filter on created_at)."""
    order = _open_order(db_session, total=total)
    res = _checkout(client, headers, order.id, **body)
    assert res.status_code == 200, res.text
    db_session.query(Order).filter(Order.id == order.id).update({Order.created_at: day})
    db_session.commit()
    return order.id


@pytest.fixture()
def second_cashier(db_session, client, seed_users):
    user = User(
        username="cashier2", role="cashier",
        password_hash=hash_password("changeme"), pin_code="4455",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    res = client.post("/api/auth/login-pin", json={"pin_code": "4455", "device_id": "pytest-device-2"})
    assert res.status_code == 200, res.text
    return user, {"Authorization": f"Bearer {res.json()['access_token']}"}


def _by_cashier(client, headers, day: datetime) -> dict[int, dict]:
    iso = day.date().isoformat()
    res = client.get(
        f"/api/reports/sales/by-cashier?start_date={iso}&end_date={iso}", headers=headers
    )
    assert res.status_code == 200, res.text
    return {row["user_id"]: row for row in res.json()}


# —— checkout: one method ——


@pytest.mark.parametrize(
    "method, expected",
    [
        ("cash", {"cash_amount": 10000.0, "kpay_amount": 0.0, "mmqr_amount": 0.0, "mobile_money_amount": 0.0}),
        ("kpay", {"cash_amount": 0.0, "kpay_amount": 10000.0, "mmqr_amount": 0.0, "mobile_money_amount": 10000.0}),
        ("mmqr", {"cash_amount": 0.0, "kpay_amount": 0.0, "mmqr_amount": 10000.0, "mobile_money_amount": 10000.0}),
    ],
)
def test_single_method_records_the_whole_bill_under_that_method(
    client, db_session, auth_headers, seed_users, method, expected
):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method=method, amount_tendered=10000.0)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "paid"
    assert body["payment_method"] == method
    assert {key: body[key] for key in expected} == expected
    assert body["total_amount"] == 10000.0

    stored = _stored(db_session, order.id)
    assert stored.payment_method == method
    assert {key: getattr(stored, key) for key in expected} == expected
    assert stored.checked_out_by_id == seed_users["cashier"].id


def test_method_name_ignores_case_and_spaces(client, db_session, auth_headers):
    order = _open_order(db_session, total=500.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method=" KPay ", amount_tendered=500.0)
    assert res.status_code == 200, res.text
    assert res.json()["payment_method"] == "kpay"


# —— checkout: amounts (split) ——


def test_split_of_three_methods(client, db_session, auth_headers):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(
        client, auth_headers("cashier"), order.id,
        payment_method="split", kpay_amount=3000.0, mmqr_amount=2000.0, cash_amount=6000.0,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["payment_method"] == "split"
    assert body["kpay_amount"] == 3000.0
    assert body["mmqr_amount"] == 2000.0
    assert body["cash_amount"] == 5000.0  # applied to the bill
    assert body["amount_tendered"] == 6000.0  # cash handed over
    assert body["change_amount"] == 1000.0
    assert body["mobile_money_amount"] == 5000.0

    stored = _stored(db_session, order.id)
    assert stored.cash_amount + stored.kpay_amount + stored.mmqr_amount == stored.total_amount == 10000.0
    assert stored.mobile_money_amount == stored.kpay_amount + stored.mmqr_amount


def test_split_of_kpay_and_mmqr_without_cash(client, db_session, auth_headers):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, kpay_amount=6000.0, mmqr_amount=4000.0)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["payment_method"] == "split"
    assert (body["cash_amount"], body["amount_tendered"], body["change_amount"]) == (0.0, 0.0, 0.0)
    assert (body["kpay_amount"], body["mmqr_amount"]) == (6000.0, 4000.0)


@pytest.mark.parametrize(
    "amounts, method",
    [
        ({"kpay_amount": 800.0}, "kpay"),
        ({"mmqr_amount": 800.0}, "mmqr"),
        ({"cash_amount": 800.0}, "cash"),
        ({"cash_amount": 1000.0, "kpay_amount": 0, "mmqr_amount": 0}, "cash"),
        # Declared "split" but only one method has money: stored as that method.
        ({"payment_method": "split", "mmqr_amount": 800.0, "cash_amount": 0}, "mmqr"),
    ],
)
def test_amounts_for_one_method_are_stored_as_that_method(
    client, db_session, auth_headers, amounts, method
):
    order = _open_order(db_session, total=800.0)
    res = _checkout(client, auth_headers("cashier"), order.id, **amounts)
    assert res.status_code == 200, res.text
    assert res.json()["payment_method"] == method
    stored = _stored(db_session, order.id)
    assert stored.cash_amount + stored.kpay_amount + stored.mmqr_amount == 800.0


def test_amounts_with_cents_add_up_to_the_total(client, db_session, auth_headers):
    order = _open_order(db_session, total=100.0)
    res = _checkout(
        client, auth_headers("cashier"), order.id,
        kpay_amount=33.33, mmqr_amount=33.33, cash_amount=33.34,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["kpay_amount"], body["mmqr_amount"], body["cash_amount"]) == (33.33, 33.33, 33.34)
    assert body["change_amount"] == 0.0
    assert round(body["kpay_amount"] + body["mmqr_amount"] + body["cash_amount"], 2) == 100.0


@pytest.mark.parametrize(
    "amounts",
    [
        {"kpay_amount": 10000.01},
        {"mmqr_amount": 12000.0},
        {"kpay_amount": 6000.0, "mmqr_amount": 5000.0},
        {"kpay_amount": 6000.0, "mmqr_amount": 5000.0, "cash_amount": 1000.0},
    ],
)
def test_kpay_plus_mmqr_above_the_total_is_rejected(client, db_session, auth_headers, amounts):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, **amounts)
    assert res.status_code == 400, res.text
    assert "more than the total" in res.json()["detail"]
    _assert_unpaid(db_session, order.id)


@pytest.mark.parametrize(
    "amounts",
    [
        {"kpay_amount": 3000.0, "mmqr_amount": 2000.0, "cash_amount": 4999.99},
        {"kpay_amount": 9999.0},
        {"cash_amount": 0, "kpay_amount": 0, "mmqr_amount": 0},
    ],
)
def test_amounts_that_do_not_cover_the_total_are_rejected(client, db_session, auth_headers, amounts):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, **amounts)
    assert res.status_code == 400, res.text
    assert "less than total" in res.json()["detail"]
    _assert_unpaid(db_session, order.id)


def test_limit_for_kpay_and_mmqr_is_the_total_after_discount(client, db_session, auth_headers):
    order = _open_order(db_session, total=10000.0)
    cashier = auth_headers("cashier")
    discount = {"discount_type": "percentage", "discount_value": 10}

    too_much = _checkout(client, cashier, order.id, kpay_amount=9500.0, **discount)
    assert too_much.status_code == 400, too_much.text
    _assert_unpaid(db_session, order.id)

    ok = _checkout(client, cashier, order.id, kpay_amount=5000.0, mmqr_amount=4000.0, **discount)
    assert ok.status_code == 200, ok.text
    assert ok.json()["total_amount"] == 9000.0
    assert (ok.json()["kpay_amount"], ok.json()["mmqr_amount"], ok.json()["cash_amount"]) == (5000.0, 4000.0, 0.0)


# —— checkout: what is no longer accepted ——


@pytest.mark.parametrize(
    "body",
    [
        {"payment_method": "mobile_money", "amount_tendered": 10000.0},
        {"payment_method": "Mobile Money", "amount_tendered": 10000.0},
        {"payment_method": "split", "cash_amount": 5000.0, "mobile_money_amount": 5000.0},
        {"mobile_money_amount": 10000.0},
        {"kpay_amount": 5000.0, "mobile_money_amount": 5000.0},
    ],
)
def test_unspecified_mobile_money_is_rejected(client, db_session, auth_headers, body):
    """The server never guesses whether mobile money was KPay or MMQR."""
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, **body)
    assert res.status_code == 422, res.text
    assert "kpay" in res.text.lower() and "mmqr" in res.text.lower()
    _assert_unpaid(db_session, order.id)


def test_zero_mobile_money_amount_from_an_older_client_is_harmless(client, db_session, auth_headers):
    order = _open_order(db_session, total=700.0)
    res = _checkout(client, auth_headers("cashier"), order.id, cash_amount=700.0, mobile_money_amount=0)
    assert res.status_code == 200, res.text
    assert res.json()["payment_method"] == "cash"


@pytest.mark.parametrize(
    "body",
    [
        {"kpay_amount": -1, "cash_amount": 10001.0},
        {"mmqr_amount": -0.01, "cash_amount": 10000.0},
        {"kpay_amount": "abc"},
        {"payment_method": "wave", "amount_tendered": 10000.0},
        {"payment_method": "card", "amount_tendered": 10000.0},
        {"payment_method": "split"},
        {"payment_method": "kpay"},
    ],
)
def test_invalid_payment_input_is_422_and_changes_nothing(client, db_session, auth_headers, body):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, **body)
    assert res.status_code == 422, res.text
    _assert_unpaid(db_session, order.id)


@pytest.mark.parametrize("method", ["kpay", "mmqr", "cash"])
def test_single_method_with_too_little_tendered_is_rejected(client, db_session, auth_headers, method):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method=method, amount_tendered=9999.0)
    assert res.status_code == 400, res.text
    _assert_unpaid(db_session, order.id)


@pytest.mark.parametrize("method, label", [("kpay", "KPay"), ("mmqr", "MMQR")])
@pytest.mark.parametrize("tendered", [10000.01, 10001.0, 15000.0])
def test_a_transfer_must_equal_the_bill_no_change_is_given(
    client, db_session, auth_headers, method, label, tendered
):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method=method, amount_tendered=tendered)
    assert res.status_code == 400, res.text
    assert f"{label} amount" in res.json()["detail"] and "must equal the total" in res.json()["detail"]
    _assert_unpaid(db_session, order.id)


@pytest.mark.parametrize("method", ["kpay", "mmqr"])
def test_a_transfer_may_equal_the_bill_after_a_discount(client, db_session, auth_headers, method):
    order = _open_order(db_session, total=10000.0)
    # 10% off -> the bill is 9000, so 10000 is now too much and 9000 is exact.
    too_much = _checkout(
        client, auth_headers("cashier"), order.id, payment_method=method, amount_tendered=10000.0,
        discount_type="percentage", discount_value=10,
    )
    assert too_much.status_code == 400, too_much.text
    _assert_unpaid(db_session, order.id)
    exact = _checkout(
        client, auth_headers("cashier"), order.id, payment_method=method, amount_tendered=9000.0,
        discount_type="percentage", discount_value=10,
    )
    assert exact.status_code == 200, exact.text
    assert exact.json()["change_amount"] == 0.0


def test_cash_may_still_be_more_than_the_bill_and_gives_change(client, db_session, auth_headers):
    order = _open_order(db_session, total=10000.0)
    res = _checkout(client, auth_headers("cashier"), order.id, payment_method="cash", amount_tendered=15000.0)
    assert res.status_code == 200, res.text
    assert res.json()["change_amount"] == 5000.0


@pytest.mark.parametrize("role, status", [("waiter", 403), ("account", 403), ("admin", 200), ("root", 200)])
def test_who_may_take_a_kpay_payment(client, db_session, auth_headers, role, status):
    order = _open_order(db_session, total=300.0)
    res = _checkout(client, auth_headers(role), order.id, payment_method="kpay", amount_tendered=300.0)
    assert res.status_code == status, res.text
    if status != 200:
        _assert_unpaid(db_session, order.id)


def test_checkout_without_login_is_401(client, db_session):
    order = _open_order(db_session, total=300.0)
    res = _checkout(client, {}, order.id, payment_method="kpay", amount_tendered=300.0)
    assert res.status_code == 401, res.text
    _assert_unpaid(db_session, order.id)


# —— per-cashier report ——


def test_by_cashier_splits_each_cashiers_sales_by_method(
    client, db_session, auth_headers, seed_users, second_cashier
):
    day = datetime(2033, 2, 3, 9, 0, 0)
    first, first_headers = seed_users["cashier"], auth_headers("cashier")
    second, second_headers = second_cashier

    _pay_on(client, db_session, first_headers, day, total=1000.0, payment_method="cash", amount_tendered=1500.0)
    _pay_on(client, db_session, first_headers, day, total=2000.0, payment_method="kpay", amount_tendered=2000.0)
    _pay_on(
        client, db_session, first_headers, day, total=1000.0,
        cash_amount=600.0, kpay_amount=300.0, mmqr_amount=200.0,
    )
    _pay_on(client, db_session, second_headers, day, total=700.0, payment_method="mmqr", amount_tendered=700.0)
    _pay_on(client, db_session, second_headers, day, total=250.0, payment_method="cash", amount_tendered=250.0)
    # Another day: must not be counted.
    _pay_on(
        client, db_session, second_headers, datetime(2033, 2, 4, 9, 0, 0),
        total=9999.0, payment_method="kpay", amount_tendered=9999.0,
    )
    # Not paid yet: must not be counted.
    unpaid = _open_order(db_session, total=5555.0)
    db_session.query(Order).filter(Order.id == unpaid.id).update(
        {Order.created_at: day, Order.checked_out_by_id: first.id}
    )
    db_session.commit()

    rows = _by_cashier(client, auth_headers("admin"), day)
    assert set(rows) == {first.id, second.id}

    a, b = rows[first.id], rows[second.id]
    assert (a["username"], a["role"]) == ("cashier1", "cashier")
    # Cash tendered 1500 for a 1000 bill counts as 1000; the split adds 500 cash.
    assert (a["cash"], a["kpay"], a["mmqr"], a["mobile_unspecified"]) == (1500.0, 2300.0, 200.0, 0.0)
    assert (a["total_sales"], a["order_count"]) == (4000.0, 3)
    assert (b["cash"], b["kpay"], b["mmqr"], b["mobile_unspecified"]) == (250.0, 0.0, 700.0, 0.0)
    assert (b["total_sales"], b["order_count"]) == (950.0, 2)
    for row in (a, b):
        assert row["cash"] + row["kpay"] + row["mmqr"] == row["total_sales"]


def test_by_cashier_reports_older_mobile_money_as_unspecified(
    client, db_session, auth_headers, seed_users
):
    """Sales from before KPay / MMQR: never guessed, never dropped from the total."""
    day = datetime(2033, 3, 5, 9, 0, 0)
    cashier = seed_users["cashier"]
    common = dict(
        table_id=None, table_number=None, order_type="takeaway", status="paid",
        created_at=day, checked_out_by_id=cashier.id,
    )
    db_session.add_all(
        [
            # With amount columns.
            Order(total_amount=400.0, payment_method="mobile_money", cash_amount=0.0, mobile_money_amount=400.0, **common),
            Order(total_amount=1100.0, payment_method="split", cash_amount=700.0, mobile_money_amount=400.0, **common),
            # From before the amount columns existed.
            Order(total_amount=110.0, payment_method="mobile_money", **common),
            Order(total_amount=90.0, payment_method="cash", **common),
        ]
    )
    db_session.commit()
    _pay_on(client, db_session, auth_headers("cashier"), day, total=500.0, payment_method="kpay", amount_tendered=500.0)

    row = _by_cashier(client, auth_headers("admin"), day)[cashier.id]
    assert (row["cash"], row["kpay"], row["mmqr"]) == (790.0, 500.0, 0.0)
    assert row["mobile_unspecified"] == 910.0
    assert row["total_sales"] == 2200.0
    assert row["cash"] + row["kpay"] + row["mmqr"] + row["mobile_unspecified"] == row["total_sales"]


@pytest.mark.parametrize(
    "role, status", [("root", 200), ("admin", 200), ("account", 200), ("cashier", 403), ("waiter", 403)]
)
def test_by_cashier_roles(client, auth_headers, role, status):
    today = datetime.utcnow().date().isoformat()
    res = client.get(
        f"/api/reports/sales/by-cashier?start_date={today}&end_date={today}",
        headers=auth_headers(role),
    )
    assert res.status_code == status, res.text


def test_by_cashier_without_login_is_401(client):
    assert client.get("/api/reports/sales/by-cashier").status_code == 401


# —— store totals ——


def test_sales_breakdown_reports_kpay_and_mmqr(client, db_session, auth_headers, seed_users, second_cashier):
    admin, first_headers = auth_headers("admin"), auth_headers("cashier")
    _second, second_headers = second_cashier

    def today(headers):
        res = client.get("/api/analytics/sales-breakdown", headers=headers)
        assert res.status_code == 200, res.text
        return res.json()["today"]

    before, before_second = today(admin), today(second_headers)

    for headers, total, body in (
        (first_headers, 300.0, {"payment_method": "cash", "amount_tendered": 300.0}),
        (first_headers, 200.0, {"payment_method": "kpay", "amount_tendered": 200.0}),
        (second_headers, 500.0, {"cash_amount": 100.0, "kpay_amount": 150.0, "mmqr_amount": 250.0}),
    ):
        order = _open_order(db_session, total=total)
        assert _checkout(client, headers, order.id, **body).status_code == 200

    after, after_second = today(admin), today(second_headers)

    def delta(new, old, key):
        return round(float(new[key]) - float(old[key]), 2)

    assert delta(after, before, "cash") == 400.0
    assert delta(after, before, "kpay") == 350.0
    assert delta(after, before, "mmqr") == 250.0
    assert delta(after, before, "mobile_money") == 600.0  # all mobile money
    assert delta(after, before, "total") == 1000.0
    # A cashier sees only their own checkouts.
    assert delta(after_second, before_second, "cash") == 100.0
    assert delta(after_second, before_second, "kpay") == 150.0
    assert delta(after_second, before_second, "mmqr") == 250.0


def test_period_report_reports_kpay_and_mmqr(client, db_session, auth_headers):
    day = datetime(2033, 4, 6, 9, 0, 0)
    cashier = auth_headers("cashier")
    _pay_on(client, db_session, cashier, day, total=1000.0, payment_method="cash", amount_tendered=1000.0)
    _pay_on(client, db_session, cashier, day, total=600.0, payment_method="mmqr", amount_tendered=600.0)
    _pay_on(client, db_session, cashier, day, total=900.0, cash_amount=400.0, kpay_amount=500.0)
    db_session.add(
        Order(
            table_id=None, table_number=None, order_type="takeaway", status="paid", created_at=day,
            total_amount=50.0, payment_method="mobile_money", cash_amount=0.0, mobile_money_amount=50.0,
        )
    )
    db_session.commit()

    res = client.get("/api/reports/sales?period=daily&date=2033-04-06", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_orders"] == 4
    assert body["grand_total_revenue"] == 2550.0
    assert (body["total_cash"], body["total_kpay"], body["total_mmqr"]) == (1400.0, 500.0, 600.0)
    assert body["total_mobile"] == 1150.0  # KPay + MMQR + 50 from before they were told apart
    assert body["total_cash"] + body["total_mobile"] == body["grand_total_revenue"]


def test_daily_history_shows_the_parts_of_a_split(client, db_session, auth_headers):
    day = datetime(2033, 5, 7, 9, 0, 0)
    order_id = _pay_on(
        client, db_session, auth_headers("cashier"), day, total=1000.0,
        cash_amount=500.0, kpay_amount=300.0, mmqr_amount=200.0,
    )
    res = client.get("/api/orders/daily-history?date=2033-05-07", headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    (order,) = [o for o in res.json()["orders"] if o["id"] == order_id]
    assert order["payment_method"] == "split"
    assert (order["cash_amount"], order["kpay_amount"], order["mmqr_amount"]) == (500.0, 300.0, 200.0)
    assert order["mobile_money_amount"] == 500.0


# —— receipt ——


def _receipt(**payment) -> str:
    return build_receipt_text(
        order_id=42, served_by="waiter1", location_label="T5",
        items=[{"name": "Tea", "quantity": 1, "subtotal": 10000.0}],
        subtotal=10000.0, discount_amount=0.0, tax_amount=0.0, grand_total=10000.0,
        **payment,
    )


@pytest.mark.parametrize("method, label", [("cash", "Cash"), ("kpay", "KPay"), ("mmqr", "MMQR")])
def test_receipt_names_the_method(method, label):
    text = _receipt(
        payment_method=method, amount_tendered=10000.0, change_amount=0.0,
        cash_amount=10000.0 if method == "cash" else 0.0,
        kpay_amount=10000.0 if method == "kpay" else 0.0,
        mmqr_amount=10000.0 if method == "mmqr" else 0.0,
        mobile_money_amount=0.0 if method == "cash" else 10000.0,
    )
    assert f"Payment:      {label}\n" in text
    assert "Paid via" not in text
    assert "Mobile" not in text


def test_receipt_for_a_split_of_three_methods():
    text = _receipt(
        payment_method="split", amount_tendered=6000.0, change_amount=1000.0,
        cash_amount=5000.0, kpay_amount=3000.0, mmqr_amount=2000.0, mobile_money_amount=5000.0,
    )
    lines = text.split("\n")
    start = lines.index("Payment:      Split (Cash + KPay + MMQR)")
    assert lines[start + 1 : start + 5] == [
        "Paid via KPay:   3000.00",
        "Paid via MMQR:   2000.00",
        "Tendered Cash:   6000.00",
        "Change Due:      1000.00",
    ]
    assert "Paid via Mobile" not in text


def test_receipt_for_a_split_without_cash_has_no_cash_lines():
    text = _receipt(
        payment_method="split", amount_tendered=0.0, change_amount=0.0,
        cash_amount=0.0, kpay_amount=6000.0, mmqr_amount=4000.0, mobile_money_amount=10000.0,
    )
    assert "Payment:      Split (KPay + MMQR)" in text
    assert "Paid via KPay:   6000.00" in text and "Paid via MMQR:   4000.00" in text
    assert "Tendered Cash" not in text and "Change Due" not in text


def test_receipt_for_a_split_names_only_the_methods_used():
    text = _receipt(
        payment_method="split", amount_tendered=7000.0, change_amount=0.0,
        cash_amount=7000.0, kpay_amount=0.0, mmqr_amount=3000.0, mobile_money_amount=3000.0,
    )
    assert "Payment:      Split (Cash + MMQR)" in text
    assert "Paid via MMQR:   3000.00" in text
    assert "KPay" not in text


def test_receipt_recorded_before_kpay_mmqr_still_prints_as_before():
    """A receipt job stored by the previous version, reprinted with Retry."""
    single = _receipt(payment_method="mobile_money", amount_tendered=10000.0, change_amount=0.0)
    assert "Payment:      Mobile Money" in single
    split = _receipt(
        payment_method="split", amount_tendered=3000.0, change_amount=1000.0,
        cash_amount=2000.0, mobile_money_amount=8000.0,
    )
    assert "Payment:      Split (Cash + Mobile)" in split
    assert "Paid via Mobile: 8000.00" in split
    assert "Tendered Cash:   3000.00" in split and "Change Due:      1000.00" in split


def test_printed_receipt_of_a_split_checkout(client, db_session, auth_headers, monkeypatch):
    """End to end: checkout → receipt job → rendered text handed to the printer."""
    sent: list[tuple[str, str]] = []

    async def capture(*, route, ticket_text, **kwargs):
        sent.append((route, ticket_text))

    monkeypatch.setattr("services.printing.service._dispatch_payload", capture)
    order = _open_order(db_session, total=10000.0)
    res = _checkout(
        client, auth_headers("cashier"), order.id, issue_receipt=True,
        kpay_amount=3000.0, mmqr_amount=2000.0, cash_amount=6000.0,
    )
    assert res.status_code == 200, res.text
    assert res.json()["warning"] is None

    job = db_session.query(PrintJob).filter(PrintJob.order_id == order.id, PrintJob.kind == "receipt").one()
    assert job.print_status == "printed", job.error_message
    assert (job.payload["kpay_amount"], job.payload["mmqr_amount"], job.payload["cash_amount"]) == (3000.0, 2000.0, 5000.0)

    ((route, text),) = sent
    assert route == "cashier"
    assert "Grand Total:  10000.00" in text
    assert "Payment:      Split (Cash + KPay + MMQR)" in text
    assert "Paid via KPay:   3000.00" in text and "Paid via MMQR:   2000.00" in text
    assert "Tendered Cash:   6000.00" in text and "Change Due:      1000.00" in text


# —— existing database ——


def test_startup_adds_the_columns_and_keeps_existing_sales(tmp_path):
    db_path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    con = sqlite3.connect(db_path)
    con.execute("ALTER TABLE orders DROP COLUMN kpay_amount")
    con.execute("ALTER TABLE orders DROP COLUMN mmqr_amount")
    con.execute(
        "INSERT INTO orders (id, order_type, status, total_amount, created_at, payment_method, "
        "cash_amount, mobile_money_amount) "
        "VALUES (1, 'takeaway', 'paid', 1100.0, '2026-11-01 10:00:00', 'split', 700.0, 400.0)"
    )
    con.commit()
    assert "kpay_amount" not in {row[1] for row in con.execute("PRAGMA table_info(orders)")}
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
        [sys.executable, "-c", script],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "STARTED" in proc.stdout

    con = sqlite3.connect(db_path)
    columns = {row[1] for row in con.execute("PRAGMA table_info(orders)")}
    row = con.execute(
        "SELECT total_amount, payment_method, cash_amount, mobile_money_amount, kpay_amount, mmqr_amount "
        "FROM orders WHERE id = 1"
    ).fetchone()
    con.close()
    assert {"kpay_amount", "mmqr_amount"} <= columns
    # The old sale is untouched; its mobile money is not assigned to KPay or MMQR.
    assert row == (1100.0, "split", 700.0, 400.0, None, None)


def test_dashboard_totals_can_load_when_the_page_opens():
    """The role check near the top of counter.js opens the dashboard straight away.

    `loadDashboardSummary()` assigns these two caches; while their `let` was
    further down the file the assignment threw, and the totals (now including
    KPay / MMQR) stayed at 0 until the Dashboard tab was clicked.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "static" / "counter.js").read_text(encoding="utf-8")
    first_dashboard_open = source.index("applyAdminOnlyTabVisibility(user.role)")
    for name in ("overviewSummaryCache", "overviewPaymentCache"):
        assert source.count(f"let {name}") == 1
        assert source.index(f"let {name}") < first_dashboard_open


# NaN / Infinity compare as "not less than the total", so before these fields
# refused them an order could be marked paid with no money counted (or paid and
# then fail to serialise, breaking every report that sums it).
_NOT_A_NUMBER = [
    '{"payment_method":"cash","amount_tendered":NaN}',
    '{"payment_method":"kpay","amount_tendered":Infinity}',
    '{"cash_amount":NaN}',
    '{"cash_amount":Infinity}',
    '{"kpay_amount":NaN}',
    '{"kpay_amount":Infinity}',
    '{"cash_amount":10000,"mmqr_amount":NaN}',
    '{"cash_amount":10000,"mmqr_amount":-Infinity}',
    '{"cash_amount":10000,"mobile_money_amount":NaN}',
    '{"payment_method":"cash","amount_tendered":10000,"discount_type":"amount","discount_value":NaN}',
    '{"payment_method":"cash","amount_tendered":10000,"discount_type":"amount","discount_value":Infinity}',
]


@pytest.mark.parametrize("raw", _NOT_A_NUMBER)
def test_nan_and_infinity_are_refused_and_nothing_is_paid(client, db_session, auth_headers, raw):
    order = _open_order(db_session, total=10000.0)
    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers={**auth_headers("cashier"), "Content-Type": "application/json"},
        content=raw,
    )
    assert res.status_code == 422, res.text
    _assert_unpaid(db_session, order.id)
