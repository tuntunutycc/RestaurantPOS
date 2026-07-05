"""RBAC feature tests: hierarchy, sessions, setup, reports."""

import uuid
from datetime import date, datetime, timedelta

from models import Category, MenuItem, Order, OrderItem, Table, User, Zone


def test_setup_status_and_root_creation(client, db_session):
    db_session.query(User).delete()
    db_session.commit()
    res = client.get("/api/setup/status")
    assert res.status_code == 200
    assert res.json()["needs_setup"] is True

    created = client.post(
        "/api/setup/root",
        json={"username": "owner", "password": "owner123"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["user"]["role"] == "root"

    res2 = client.get("/api/setup/status")
    assert res2.json()["needs_setup"] is False

    blocked = client.post(
        "/api/setup/root",
        json={"username": "other", "password": "other123"},
    )
    assert blocked.status_code == 403


def test_admin_cannot_create_admin(client, auth_headers):
    res = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": "newadmin", "role": "admin", "pin_code": "9999"},
    )
    assert res.status_code == 403, res.text


def test_root_creates_admin_and_lists(client, auth_headers):
    res = client.post(
        "/api/root/admins",
        headers=auth_headers("root"),
        json={"username": "mgr", "password": "mgr12345", "pin_code": "4321"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "admin"

    listed = client.get("/api/root/admins", headers=auth_headers("root"))
    assert listed.status_code == 200
    assert any(u["username"] == "mgr" for u in listed.json())


def test_admin_staff_crud_writes_audit_log(client, auth_headers, db_session):
    res = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": "newwaiter", "role": "waiter", "pin_code": "5555"},
    )
    assert res.status_code == 200, res.text

    logs = client.get("/api/root/audit-logs", headers=auth_headers("root"))
    assert logs.status_code == 200
    actions = [row["action"] for row in logs.json()]
    assert "admin_create_staff" in actions


def test_audit_log_never_stores_plaintext_pin(client, auth_headers):
    create = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": "pinwaiter", "role": "waiter", "pin_code": "7777"},
    )
    assert create.status_code == 200
    user_id = create.json()["id"]

    update = client.put(
        f"/api/admin/users/{user_id}",
        headers=auth_headers("admin"),
        json={"username": "pinwaiter", "role": "waiter", "pin_code": "8888"},
    )
    assert update.status_code == 200

    logs = client.get("/api/root/audit-logs", headers=auth_headers("root"))
    assert logs.status_code == 200

    def _walk_strings(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "pin_code" and isinstance(v, str):
                    assert v == "[REDACTED]", f"expected redacted PIN, got {v!r}"
                    assert v != "7777" and v != "8888"
                else:
                    yield from _walk_strings(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _walk_strings(item)

    for row in logs.json():
        detail = row.get("detail_json") or {}
        list(_walk_strings(detail))
        if row["action"] == "admin_create_staff" and row.get("target_user_id") == user_id:
            assert detail.get("pin_set") is True
        if row["action"] == "admin_update_staff" and row.get("target_user_id") == user_id:
            assert detail.get("pin_changed") is True

def test_single_device_login_revokes_prior_session(client, auth_headers):
    first = client.post(
        "/api/auth/login-pin",
        json={"pin_code": "2222", "device_id": "device-a"},
    )
    assert first.status_code == 200
    token_a = first.json()["access_token"]

    second = client.post(
        "/api/auth/login-pin",
        json={"pin_code": "2222", "device_id": "device-b"},
    )
    assert second.status_code == 200

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me.status_code == 401


def test_multi_device_admin_sessions_both_valid(client, auth_headers):
    a = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123", "device_id": "admin-a"},
    )
    b = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123", "device_id": "admin-b"},
    )
    assert a.status_code == 200 and b.status_code == 200
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {a.json()['access_token']}"}).status_code
        == 200
    )
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {b.json()['access_token']}"}).status_code
        == 200
    )


def test_account_cannot_submit_orders(client, auth_headers):
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("account"),
        json={
            "order_type": "takeaway",
            "customer_name": "Test",
            "items": [],
        },
    )
    assert res.status_code == 403


def test_account_report_range_capped(client, auth_headers):
    today = date.today()
    start = today - timedelta(days=100)
    res = client.get(
        f"/api/reports/daily-sales?start_date={start.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers("account"),
    )
    assert res.status_code == 400


def _seed_paid_order_with_staff(db_session, cashier: User, waiter: User):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"R-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    cat = Category(name=f"C-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(name=f"I-{suffix}", price=10.0, category_id=cat.id, is_available=True, modifiers_config=[])
    db_session.add(item)
    db_session.flush()
    order = Order(
        table_id=table.id,
        order_type="dine_in",
        status="paid",
        total_amount=10.5,
        checked_out_by_id=cashier.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.flush()
    oi = OrderItem(
        order_id=order.id,
        menu_item_id=item.id,
        quantity=1,
        subtotal=10.0,
        batch_number=1,
        batch_status="pending",
        item_status="served",
        selected_modifiers=[],
        created_by_id=waiter.id,
    )
    db_session.add(oi)
    db_session.commit()
    return order


def test_per_cashier_and_waiter_reports(client, auth_headers, seed_users, db_session):
    _seed_paid_order_with_staff(db_session, seed_users["cashier"], seed_users["waiter"])
    today = datetime.utcnow().date()
    today_str = today.isoformat()
    month_start = today.replace(day=1).isoformat()

    by_cashier = client.get(
        f"/api/reports/sales/by-cashier?start_date={today_str}&end_date={today_str}",
        headers=auth_headers("root"),
    )
    assert by_cashier.status_code == 200
    rows = by_cashier.json()
    cashier_row = next((r for r in rows if r["user_id"] == seed_users["cashier"].id), None)
    assert cashier_row is not None
    assert cashier_row["total_sales"] >= 10.5

    by_cashier_month = client.get(
        f"/api/reports/sales/by-cashier?start_date={month_start}&end_date={today_str}",
        headers=auth_headers("root"),
    )
    assert by_cashier_month.status_code == 200
    month_rows = by_cashier_month.json()
    month_cashier_row = next((r for r in month_rows if r["user_id"] == seed_users["cashier"].id), None)
    assert month_cashier_row is not None
    assert month_cashier_row["total_sales"] >= 10.5

    by_staff = client.get(
        f"/api/reports/sales/by-order-staff?start_date={today_str}&end_date={today_str}",
        headers=auth_headers("admin"),
    )
    assert by_staff.status_code == 200
    waiter_row = next((r for r in by_staff.json() if r["user_id"] == seed_users["waiter"].id), None)
    assert waiter_row is not None
    assert waiter_row["total_sales"] >= 10.0


def test_checkout_sets_checked_out_by_id(client, db_session, auth_headers, seed_users):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"CO-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"CO-T-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    cat = Category(name=f"CO-C-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(name=f"CO-I-{suffix}", price=9.5, category_id=cat.id, is_available=True, modifiers_config=[])
    db_session.add(item)
    db_session.flush()
    order = Order(table_id=table.id, order_type="dine_in", status="open", total_amount=9.5)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=9.5,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[],
        )
    )
    db_session.commit()

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100, "discount_type": None, "discount_value": 0},
    )
    assert res.status_code == 200, res.text
    db_session.refresh(order)
    assert order.checked_out_by_id == seed_users["cashier"].id


def test_audit_logs_forbidden_for_non_root(client, auth_headers):
    for role in ("admin", "cashier", "waiter", "account"):
        res = client.get("/api/root/audit-logs", headers=auth_headers(role))
        assert res.status_code == 403, f"{role} should not access audit logs"


def test_audit_logs_filter_by_action(client, auth_headers):
    create = client.post(
        "/api/admin/users",
        headers=auth_headers("admin"),
        json={"username": "auditfilter", "role": "waiter", "pin_code": "1212"},
    )
    assert create.status_code == 200

    all_logs = client.get("/api/root/audit-logs", headers=auth_headers("root"))
    assert all_logs.status_code == 200

    filtered = client.get(
        "/api/root/audit-logs?action=admin_create_staff",
        headers=auth_headers("root"),
    )
    assert filtered.status_code == 200
    rows = filtered.json()
    assert rows, "expected at least one admin_create_staff log"
    assert all(row["action"] == "admin_create_staff" for row in rows)
    assert any(row.get("target_username") == "auditfilter" for row in rows)


def test_audit_logs_invalid_date_range(client, auth_headers):
    res = client.get(
        "/api/root/audit-logs?start_date=2026-07-10&end_date=2026-07-01",
        headers=auth_headers("root"),
    )
    assert res.status_code == 400


def test_counter_audit_log_ui_contract():
    """Static UI contract: audit log tab exists and is root-gated in counter assets."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "counter.html").read_text(encoding="utf-8")
    js = (root / "static" / "counter.js").read_text(encoding="utf-8")

    assert 'id="tab-audit-logs"' in html
    assert 'id="panel-audit-logs"' in html
    assert 'id="audit-logs-table-body"' in html
    assert "admin_create_staff" in html

    assert "tabAuditLogs" in js
    assert "panelAuditLogs" in js
    assert "loadAuditLogs" in js
    assert "tabAuditLogs.classList.toggle('hidden', !isRoot)" in js
    assert "/api/root/audit-logs" in js


def test_phase4_dashboard_ui_contract():
    """Static UI contract: Phase 4 dashboards, account history, Take Orders nav."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    account_html = (root / "static" / "account.html").read_text(encoding="utf-8")
    account_js = (root / "static" / "account.js").read_text(encoding="utf-8")
    counter_html = (root / "static" / "counter.html").read_text(encoding="utf-8")
    counter_js = (root / "static" / "counter.js").read_text(encoding="utf-8")
    auth_js = (root / "static" / "auth.js").read_text(encoding="utf-8")

    assert 'id="account-monthly-chart"' in account_html
    assert 'id="account-start-date"' in account_html
    assert "ACCOUNT_MAX_DAYS = 93" in account_js
    assert "/api/reports/monthly-sales" in account_js

    assert 'id="dashboard-tab-staff"' in counter_html
    assert 'id="staffCashierChart"' in counter_html
    assert 'id="staffWaiterChart"' in counter_html
    assert 'id="staff-filter-start-date"' in counter_html
    assert 'id="staff-filter-end-date"' in counter_html
    assert 'id="btn-staff-preset-month"' in counter_html
    assert "applyDashboardRoleVisibility" in counter_js
    assert "loadStaffBreakdownCharts" in counter_js
    assert "getStaffReportDateRange" in counter_js
    assert "showDashboard = isAdminPanel || isCashier" in counter_js
    assert 'data-role-widget="cashier-breakdown"' in counter_html

    assert 'href="/waiter"' in auth_js
    assert 'role === "cashier" || role === "waiter"' in auth_js
    assert "pos-take-orders-link" in auth_js


def test_account_monthly_sales_access(client, auth_headers):
    res = client.get("/api/reports/monthly-sales", headers=auth_headers("account"))
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_cashier_cannot_access_monthly_store_sales(client, auth_headers):
    res = client.get("/api/reports/monthly-sales", headers=auth_headers("cashier"))
    assert res.status_code == 403


def test_promoted_items_full_flow(client, auth_headers, db_session, seed_users):
    """Mark item promoted → order → checkout → promoted-by-waiter report."""
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"P-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"Promo-{suffix}",
        price=15.0,
        category_id=cat.id,
        is_available=True,
        is_promoted=False,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    toggle = client.put(
        f"/api/menu-items/{item.id}/toggle-promoted",
        headers=auth_headers("admin"),
    )
    assert toggle.status_code == 200
    assert toggle.json()["is_promoted"] is True

    zone = Zone(name=f"PZ-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"PT-{suffix}", zone_id=zone.id, status="occupied")
    db_session.add(table)
    db_session.flush()
    order = Order(table_id=table.id, order_type="dine_in", status="open", total_amount=15.0)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=2,
            subtotal=30.0,
            batch_number=1,
            batch_status="pending",
            item_status="served",
            selected_modifiers=[],
            created_by_id=seed_users["waiter"].id,
        )
    )
    db_session.commit()

    checkout = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 50, "discount_type": None, "discount_value": 0},
    )
    assert checkout.status_code == 200, checkout.text

    today = datetime.utcnow().date().isoformat()
    report = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("root"),
    )
    assert report.status_code == 200
    rows = report.json()
    waiter_row = next((r for r in rows if r["user_id"] == seed_users["waiter"].id), None)
    assert waiter_row is not None
    assert waiter_row["quantity"] >= 2
    assert waiter_row["total_sales"] >= 30.0

    denied = client.get(
        f"/api/reports/sales/promoted-by-waiter?start_date={today}&end_date={today}",
        headers=auth_headers("account"),
    )
    assert denied.status_code == 403


def test_phase4b_promoted_ui_contract():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    counter_html = (root / "static" / "counter.html").read_text(encoding="utf-8")
    counter_js = (root / "static" / "counter.js").read_text(encoding="utf-8")
    waiter_js = (root / "static" / "waiter.js").read_text(encoding="utf-8")

    assert 'id="item-is-promoted"' in counter_html
    assert 'id="dashboard-tab-incentives"' in counter_html
    assert "toggle-promoted" in counter_js
    assert "loadPromotedIncentivesReport" in counter_js
    assert "data-role-section=\"incentives\"" in counter_html
    assert "★ Promo" in waiter_js


def test_seed_root_script_creates_first_root(db_session):
    from scripts.seed_root import root_exists, seed_root

    db_session.query(User).delete()
    db_session.commit()
    assert not root_exists(db_session)

    user = seed_root("root", "seedpass123", db=db_session)
    assert user.role == "root"
    assert user.username == "root"
    assert root_exists(db_session)

    again = seed_root("other", "otherpass123", db=db_session)
    assert again.id == user.id
    assert again.username == "root"
