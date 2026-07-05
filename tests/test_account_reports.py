"""Account (accountant) role — 90-day report cap and access matrix."""

from datetime import date, timedelta

from services.report_access import ACCOUNT_ACCESS_DENIED_DETAIL


def test_account_report_range_capped(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=100)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 400
    assert res.json()["detail"] == ACCOUNT_ACCESS_DENIED_DETAIL


def test_account_rejects_start_before_90_days(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=91)
    end = today - timedelta(days=1)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={end.isoformat()}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 400
    assert res.json()["detail"] == ACCOUNT_ACCESS_DENIED_DETAIL


def test_account_daily_sales_within_window(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=29)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_admin_unrestricted_report_range(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=100)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_root_unrestricted_report_range(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=365)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("root"),
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_account_cannot_access_by_order_staff(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        f"/api/reports/sales/by-order-staff?start_date={today}&end_date={today}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 403


def test_account_by_cashier_within_window(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=7)
    res = client.get(
        f"/api/reports/sales/by-cashier?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_account_monthly_sales_rejects_year_outside_window(client, auth_headers):
    today = date.today()
    old_year = today.year - 5
    res = client.get(
        f"/api/reports/monthly-sales?year={old_year}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 400
    assert res.json()["detail"] == ACCOUNT_ACCESS_DENIED_DETAIL
