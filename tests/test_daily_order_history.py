"""Daily paid-order history list + Excel export."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook

from models import Category, MenuItem, Order, OrderItem


def _seed_paid_with_lines(db_session, *, created_at: datetime, total: float = 3500.0):
    cat = Category(name=f"Hist-Cat-{created_at.timestamp()}")
    db_session.add(cat)
    db_session.flush()
    menu = MenuItem(
        name="မုန့်ဟင်းခါး",
        price=2000.0,
        category_id=cat.id,
        modifiers_config=[],
    )
    db_session.add(menu)
    db_session.flush()
    order = Order(
        table_id=None,
        order_type="takeaway",
        customer_name="Ko Aung",
        status="paid",
        total_amount=total,
        payment_method="cash",
        created_at=created_at,
    )
    db_session.add(order)
    db_session.flush()
    dine = OrderItem(
        order_id=order.id,
        menu_item_id=menu.id,
        quantity=1,
        subtotal=2000.0,
        batch_number=1,
        batch_status="pending",
        item_status="served",
        selected_modifiers=[],
        menu_item_name_at_sale=menu.name,
        is_takeaway=False,
    )
    take = OrderItem(
        order_id=order.id,
        menu_item_id=menu.id,
        quantity=1,
        subtotal=1500.0,
        batch_number=1,
        batch_status="pending",
        item_status="served",
        selected_modifiers=[{"name": "ပဲကြော်", "price": 500, "quantity": 1}],
        menu_item_name_at_sale=menu.name,
        is_takeaway=True,
    )
    cancelled = OrderItem(
        order_id=order.id,
        menu_item_id=menu.id,
        quantity=1,
        subtotal=999.0,
        batch_number=1,
        batch_status="pending",
        item_status="cancelled",
        selected_modifiers=[],
        menu_item_name_at_sale="Cancelled bowl",
        is_takeaway=False,
    )
    db_session.add_all([dine, take, cancelled])
    db_session.commit()
    db_session.refresh(order)
    return order


def test_daily_history_lists_paid_with_modifiers_and_takeaway(
    client, db_session, auth_headers
):
    day = datetime(2026, 11, 15, 10, 30, 0)
    order = _seed_paid_with_lines(db_session, created_at=day)

    # Open order same day — must not appear
    open_order = Order(
        table_id=None,
        order_type="takeaway",
        status="open",
        total_amount=100.0,
        created_at=day,
    )
    db_session.add(open_order)
    db_session.commit()

    res = client.get(
        "/api/orders/daily-history?date=2026-11-15",
        headers=auth_headers("cashier"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["date"] == "2026-11-15"
    assert body["order_count"] == 1
    assert body["grand_total"] == float(order.total_amount)
    row = body["orders"][0]
    assert row["id"] == order.id
    assert len(row["items"]) == 2
    take_line = next(i for i in row["items"] if i["is_takeaway"] is True)
    assert take_line["selected_modifiers"][0]["name"] == "ပဲကြော်"
    assert any(i["is_takeaway"] is False for i in row["items"])


def test_daily_history_waiter_forbidden(client, auth_headers):
    res = client.get(
        "/api/orders/daily-history?date=2026-11-15",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 403


def test_daily_history_export_xlsx(client, db_session, auth_headers):
    day = datetime(2026, 11, 15, 14, 0, 0)
    order = _seed_paid_with_lines(db_session, created_at=day, total=4000.0)

    res = client.get(
        "/api/orders/daily-history/export?date=2026-11-15",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 200, res.text
    assert (
        res.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "order-history-2026-11-15.xlsx" in res.headers.get("content-disposition", "")

    wb = load_workbook(BytesIO(res.content))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Order ID", "Voucher No", "Time", "Item Details", "Qty", "Total Price")
    data_rows = [r for r in rows[1:] if r and r[0] == order.id]
    assert len(data_rows) == 2
    details = " ".join(str(r[3]) for r in data_rows)
    assert "ပဲကြော်" in details
    assert "ပါဆယ်" in details


def test_order_history_page_routes():
    """Page routes live on the real FastAPI app (conftest mounts API routers only)."""
    from fastapi.testclient import TestClient

    from database import engine
    from main import app as real_app

    # The lifespan migrates whatever database the app engine points at; it must
    # be the throwaway file from conftest, never the real pos.db.
    assert "pos-tests-" in str(engine.url), engine.url

    with TestClient(real_app) as client:
        for path in ("/order-history", "/admin/sales-history", "/cashier/history"):
            res = client.get(path)
            assert res.status_code == 200, path
            assert "Daily Order History" in res.text
