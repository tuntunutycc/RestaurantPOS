"""Sales period reports: daily/monthly aggregation and tax-aware totals."""

from __future__ import annotations

from datetime import datetime, timedelta

from models import Order


def _add_paid_order(
    db_session,
    *,
    created_at: datetime,
    total: float,
    tax: float,
    cash: float | None,
    mobile: float | None,
    payment_method: str,
    status: str = "paid",
):
    order = Order(
        table_id=None,
        table_number=None,
        order_type="takeaway",
        status=status,
        total_amount=total,
        tax_amount=tax,
        payment_method=payment_method,
        cash_amount=cash,
        mobile_money_amount=mobile,
        created_at=created_at,
    )
    db_session.add(order)
    db_session.flush()
    return order


def test_daily_sales_period_aggregation(client, db_session, auth_headers):
    day = datetime(2026, 7, 10, 12, 0, 0)
    other_day = datetime(2026, 7, 11, 12, 0, 0)
    # In-range: split 1100 grand / 100 tax → net 1000; cash 700 + mobile 400
    _add_paid_order(
        db_session,
        created_at=day,
        total=1100.0,
        tax=100.0,
        cash=700.0,
        mobile=400.0,
        payment_method="split",
    )
    # In-range: legacy cash only (no cash_amount) → cash = total
    _add_paid_order(
        db_session,
        created_at=day.replace(hour=15),
        total=220.0,
        tax=20.0,
        cash=None,
        mobile=None,
        payment_method="cash",
    )
    # Out of range
    _add_paid_order(
        db_session,
        created_at=other_day,
        total=999.0,
        tax=99.0,
        cash=999.0,
        mobile=0.0,
        payment_method="cash",
    )
    # Unpaid ignored
    _add_paid_order(
        db_session,
        created_at=day,
        total=50.0,
        tax=0.0,
        cash=None,
        mobile=None,
        payment_method="cash",
        status="open",
    )
    db_session.commit()

    res = client.get(
        "/api/reports/sales?period=daily&date=2026-07-10",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"] == "daily"
    assert body["date"] == "2026-07-10"
    assert body["total_orders"] == 2
    assert body["grand_total_revenue"] == 1320.0
    assert body["total_tax"] == 120.0
    assert body["subtotal_revenue"] == 1200.0
    assert round(body["subtotal_revenue"] + body["total_tax"], 2) == body["grand_total_revenue"]
    assert body["total_cash"] == 920.0  # 700 + 220
    assert body["total_mobile"] == 400.0


def test_monthly_sales_period_aggregation(client, db_session, auth_headers):
    mid = datetime(2026, 6, 15, 10, 0, 0)
    end = datetime(2026, 6, 30, 18, 0, 0)
    next_month = datetime(2026, 7, 1, 1, 0, 0)
    _add_paid_order(
        db_session,
        created_at=mid,
        total=550.0,
        tax=50.0,
        cash=300.0,
        mobile=250.0,
        payment_method="split",
        status="completed",
    )
    _add_paid_order(
        db_session,
        created_at=end,
        total=110.0,
        tax=10.0,
        cash=None,
        mobile=None,
        payment_method="mobile_money",
    )
    _add_paid_order(
        db_session,
        created_at=next_month,
        total=1000.0,
        tax=0.0,
        cash=1000.0,
        mobile=0.0,
        payment_method="cash",
    )
    db_session.commit()

    res = client.get(
        "/api/reports/sales?period=monthly&date=2026-06",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"] == "monthly"
    assert body["date"] == "2026-06"
    assert body["total_orders"] == 2
    assert body["grand_total_revenue"] == 660.0
    assert body["total_tax"] == 60.0
    assert body["subtotal_revenue"] == 600.0
    assert round(body["subtotal_revenue"] + body["total_tax"], 2) == body["grand_total_revenue"]
    assert body["total_cash"] == 300.0
    assert body["total_mobile"] == 360.0  # 250 + 110 legacy


def test_sales_period_rejects_bad_params(client, auth_headers):
    bad_period = client.get(
        "/api/reports/sales?period=weekly&date=2026-07-10",
        headers=auth_headers("admin"),
    )
    assert bad_period.status_code == 400

    bad_daily = client.get(
        "/api/reports/sales?period=daily&date=2026-07",
        headers=auth_headers("admin"),
    )
    assert bad_daily.status_code == 400

    bad_monthly = client.get(
        "/api/reports/sales?period=monthly&date=2026-07-10",
        headers=auth_headers("admin"),
    )
    assert bad_monthly.status_code == 400


def test_sales_period_role_gate(client, auth_headers):
    res = client.get(
        "/api/reports/sales?period=daily&date=2026-07-10",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 403

    account_ok = client.get(
        f"/api/reports/sales?period=daily&date={datetime.utcnow().date().isoformat()}",
        headers=auth_headers("account"),
    )
    assert account_ok.status_code == 200

    too_old = (datetime.utcnow().date() - timedelta(days=100)).isoformat()
    account_blocked = client.get(
        f"/api/reports/sales?period=daily&date={too_old}",
        headers=auth_headers("account"),
    )
    assert account_blocked.status_code == 400


def test_overview_summary_and_breakdown_expose_tax_fields(client, db_session, auth_headers):
    now = datetime.utcnow()
    _add_paid_order(
        db_session,
        created_at=now,
        total=1100.0,
        tax=100.0,
        cash=700.0,
        mobile=400.0,
        payment_method="split",
    )
    db_session.commit()

    summary = client.get("/api/reports/summary/today", headers=auth_headers("admin"))
    assert summary.status_code == 200, summary.text
    s = summary.json()
    assert s["grand_total_revenue"] >= 1100.0
    assert s["total_tax"] >= 100.0
    assert s["subtotal_revenue"] == round(s["grand_total_revenue"] - s["total_tax"], 2)

    breakdown = client.get("/api/analytics/sales-breakdown", headers=auth_headers("admin"))
    assert breakdown.status_code == 200, breakdown.text
    today = breakdown.json()["today"]
    assert today["grand_total_revenue"] >= 1100.0
    assert today["total_tax"] >= 100.0
    assert today["subtotal_revenue"] == round(today["grand_total_revenue"] - today["total_tax"], 2)
    assert today["cash"] >= 700.0
    assert today["mobile_money"] >= 400.0
