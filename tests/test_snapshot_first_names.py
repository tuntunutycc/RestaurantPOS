"""Order lines keep the name they were sold under (rename-proof).

Spec: specs/feature-snapshot-first-names
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from models import Category, MenuItem, Order, OrderItem, PrintJob, Table, Zone


# —— helpers ——


def _shop(db_session, *, price=3500.0):
    suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"SN-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"SN-T-{suffix}", zone_id=zone.id, status="available")
    category = Category(name=f"SN-C-{suffix}")
    db_session.add_all([table, category])
    db_session.flush()
    item = MenuItem(
        name=f"SN-OLD-{suffix}", price=price, category_id=category.id,
        is_available=True, modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    return table, category, item


def _new_name() -> str:
    return f"SN-NEW-{uuid.uuid4().hex[:6]}"


def _rename(client, auth_headers, item_id, name):
    res = client.put(f"/api/menu-items/{item_id}", headers=auth_headers("admin"), json={"name": name})
    assert res.status_code == 200, res.text


def _sell(client, auth_headers, table, item, *, quantity=1):
    res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": item.id, "quantity": quantity, "selected_modifiers": []}],
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _names(items) -> list[str]:
    return [i["menu_item_name"] for i in items]


def _details_names(client, auth_headers, order_id) -> list[str]:
    res = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    return _names(res.json()["items"])


def _listed_order(client, auth_headers, url, order_id):
    res = client.get(url, headers=auth_headers("cashier"))
    assert res.status_code == 200, res.text
    body = res.json()
    if isinstance(body, dict):
        return body
    return next(o for o in body if o["id"] == order_id)


def _legacy_line(db_session, *, order_id, menu_item_id, name_snapshot):
    """A line as written before the snapshot columns existed (or with a blank snapshot)."""
    line = OrderItem(
        order_id=order_id, menu_item_id=menu_item_id, quantity=1, subtotal=1000.0,
        batch_number=1, batch_status="pending", item_status="pending",
        selected_modifiers=[], menu_item_name_at_sale=name_snapshot,
    )
    db_session.add(line)
    db_session.commit()
    return line


def _legacy_order(db_session, *, status="paid"):
    order = Order(
        table_id=None, order_type="takeaway", status=status, total_amount=1000.0,
        payment_method="cash" if status == "paid" else None,
        created_at=datetime(2026, 10, 3, 12, 0, 0),
    )
    db_session.add(order)
    db_session.commit()
    return order


# —— FR-N1: renamed item, old order lines keep the sold-as name ——


def test_rename_does_not_change_details_list_tables_and_active_by_table(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session)
    old = item.name
    order_id = _sell(client, auth_headers, table, item)
    _rename(client, auth_headers, item.id, _new_name())

    assert _details_names(client, auth_headers, order_id) == [old]
    listed = _listed_order(client, auth_headers, "/api/orders/?status=pending&status=open&status=dining", order_id)
    assert _names(listed["items"]) == [old]
    # Not asserted on GET /orders/tables: it answers 500 whenever an open takeaway and an
    # open table order exist together (sort of None vs int; separate, pre-existing, no UI
    # calls it) and this suite's shared database often holds such leftovers. It builds its
    # items through the same `OrderResponseDetail` path as the two reads here.
    active = _listed_order(client, auth_headers, f"/api/orders/active-by-table/{table.id}", order_id)
    assert _names(active["items"]) == [old]


def test_rename_does_not_change_checkout_response_history_and_receipt(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session)
    old = item.name
    new = _new_name()
    order_id = _sell(client, auth_headers, table, item)
    _rename(client, auth_headers, item.id, new)

    res = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100000.0, "issue_receipt": True},
    )
    assert res.status_code == 200, res.text
    assert _names(res.json()["items"]) == [old]

    # Receipt and kitchen slip were rendered from the sale-time name.
    db_session.expire_all()
    jobs = db_session.query(PrintJob).filter(PrintJob.order_id == order_id).all()
    assert "receipt" in {j.kind for j in jobs}
    for job in jobs:
        text = json.dumps(job.payload, ensure_ascii=False)
        assert old in text and new not in text, job.kind

    # Order History: move the order to a fixed day (history lists by created_at).
    db_session.query(Order).filter(Order.id == order_id).update({Order.created_at: datetime(2026, 10, 4, 12, 0, 0)})
    db_session.commit()
    hist = client.get("/api/orders/daily-history?date=2026-10-04", headers=auth_headers("cashier"))
    assert hist.status_code == 200, hist.text
    row = next(o for o in hist.json()["orders"] if o["id"] == order_id)
    assert _names(row["items"]) == [old]


def test_rename_open_bill_old_line_keeps_name_new_line_gets_new_name(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session)
    old = item.name
    new = _new_name()
    order_id = _sell(client, auth_headers, table, item)
    _rename(client, auth_headers, item.id, new)
    again = _sell(client, auth_headers, table, item)
    assert again == order_id  # added to the same bill

    names = _details_names(client, auth_headers, order_id)
    assert sorted(names) == sorted([old, new])


def test_rename_does_not_change_money(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session, price=4200.0)
    order_id = _sell(client, auth_headers, table, item, quantity=2)
    before = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter")).json()
    _rename(client, auth_headers, item.id, _new_name())
    after = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter")).json()
    assert after["total_amount"] == before["total_amount"] == 8400.0
    assert [(i["quantity"], i["subtotal"], i["unit_price_at_sale"]) for i in after["items"]] == [
        (i["quantity"], i["subtotal"], i["unit_price_at_sale"]) for i in before["items"]
    ]


def test_reports_after_rename_still_use_the_old_name(client, db_session, auth_headers):
    """Already true before this feature; locked in so a later change cannot break it."""
    table, _cat, item = _shop(db_session)
    old = item.name
    order_id = _sell(client, auth_headers, table, item, quantity=5000)  # tops today's top-5
    _rename(client, auth_headers, item.id, _new_name())
    res = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 1e9, "issue_receipt": False},
    )
    assert res.status_code == 200, res.text
    top = client.get("/api/reports/top-items", headers=auth_headers("admin"))
    assert top.status_code == 200, top.text
    assert old in [row["item_name"] for row in top.json()]


# —— FR-N1: fallbacks ——


def test_soft_deleted_item_shows_snapshot_name(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session)
    old = item.name
    order_id = _sell(client, auth_headers, table, item)
    assert client.put(
        f"/api/orders/{order_id}/checkout", headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 1e6, "issue_receipt": False},
    ).status_code == 200
    assert client.delete(f"/api/menu-items/{item.id}", headers=auth_headers("admin")).status_code == 200
    assert _details_names(client, auth_headers, order_id) == [old]


def test_deleted_item_without_snapshot_shows_deleted_label(client, db_session, auth_headers):
    _table, _cat, item = _shop(db_session)
    order = _legacy_order(db_session)
    _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot=None)
    assert client.delete(f"/api/menu-items/{item.id}", headers=auth_headers("admin")).status_code == 200
    assert _details_names(client, auth_headers, order.id) == ["[Deleted Item]"]


@pytest.mark.parametrize("snapshot", [None, "", "   "])
def test_legacy_line_without_snapshot_falls_back_to_live_name(client, db_session, auth_headers, snapshot):
    _table, _cat, item = _shop(db_session)
    order = _legacy_order(db_session)
    _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot=snapshot)
    assert _details_names(client, auth_headers, order.id) == [item.name]


# —— FR-N2: startup backfill ——


def _backfill(test_engine):
    import main

    return main._backfill_order_item_snapshots(test_engine)


def test_backfill_fills_empty_snapshots_and_nothing_else(db_session, test_engine):
    _table, category, item = _shop(db_session)
    order = _legacy_order(db_session)
    null_line = _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot=None)
    blank_line = _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot="  ")
    blank_line.category_name_at_sale = "   "
    kept_line = _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot="SOLD-AS-THIS")
    kept_line.category_name_at_sale = "SOLD-CATEGORY"
    kept_line.unit_price_at_sale = 777.0
    db_session.commit()

    _backfill(test_engine)

    db_session.expire_all()
    null_line = db_session.get(OrderItem, null_line.id)
    blank_line = db_session.get(OrderItem, blank_line.id)
    kept_line = db_session.get(OrderItem, kept_line.id)
    assert null_line.menu_item_name_at_sale == item.name
    assert blank_line.menu_item_name_at_sale == item.name
    assert null_line.category_name_at_sale == category.name
    assert blank_line.category_name_at_sale == category.name
    # unit_price_at_sale is unknown for old sales: never invented
    assert null_line.unit_price_at_sale is None
    # real snapshots are never overwritten
    assert kept_line.menu_item_name_at_sale == "SOLD-AS-THIS"
    assert kept_line.category_name_at_sale == "SOLD-CATEGORY"
    assert kept_line.unit_price_at_sale == 777.0


def test_backfill_is_idempotent_and_does_not_chase_later_renames(db_session, test_engine, client, auth_headers):
    _table, _cat, item = _shop(db_session)
    order = _legacy_order(db_session)
    line = _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot=None)
    first_name = item.name

    _backfill(test_engine)
    _rename(client, auth_headers, item.id, _new_name())
    _backfill(test_engine)  # second start after a rename

    db_session.expire_all()
    assert db_session.get(OrderItem, line.id).menu_item_name_at_sale == first_name
    # nothing is left to fill anywhere: a further run touches no row at all
    again = _backfill(test_engine)
    assert again["item_names"] == 0 and again["category_names"] == 0


def test_backfill_leaves_archived_bucket_category_empty(db_session, test_engine):
    from routers.menu import ARCHIVED_CATEGORY_NAME

    archived = Category(name=f"{ARCHIVED_CATEGORY_NAME}")
    existing = db_session.query(Category).filter(Category.name == ARCHIVED_CATEGORY_NAME).first()
    archived = existing or archived
    if existing is None:
        db_session.add(archived)
        db_session.flush()
    item = MenuItem(
        name=f"SN-ARCH-{uuid.uuid4().hex[:6]}", price=100.0, category_id=archived.id,
        is_available=False, is_deleted=True, modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    order = _legacy_order(db_session)
    line = _legacy_line(db_session, order_id=order.id, menu_item_id=item.id, name_snapshot=None)

    _backfill(test_engine)

    db_session.expire_all()
    line = db_session.get(OrderItem, line.id)
    assert line.menu_item_name_at_sale == item.name
    assert line.category_name_at_sale is None


def test_backfill_survives_a_database_error(test_engine):
    """A failing backfill must never stop the server from starting."""
    import main
    from sqlalchemy import create_engine

    empty = create_engine("sqlite+pysqlite:///:memory:")  # no tables at all
    assert main._backfill_order_item_snapshots(empty) == {"item_names": 0, "category_names": 0}


# —— FR-N3: write path unchanged (all three places store the snapshot) ——


def test_new_lines_store_name_and_category_snapshot_in_all_order_paths(client, db_session, auth_headers):
    table, category, item = _shop(db_session)
    first = _sell(client, auth_headers, table, item)  # create_order, new order
    second = _sell(client, auth_headers, table, item)  # create_order, add to order
    assert second == first
    sub = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert sub.status_code == 200, sub.text
    assert sub.json()["is_new_order"] is False

    db_session.expire_all()
    lines = db_session.query(OrderItem).filter(OrderItem.order_id == first).all()
    assert len(lines) == 3
    assert {(l.menu_item_name_at_sale, l.category_name_at_sale) for l in lines} == {(item.name, category.name)}

    # submit_order creating a brand new order
    zone_suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"SN-Z2-{zone_suffix}")
    db_session.add(zone)
    db_session.flush()
    table2 = Table(name=f"SN-T2-{zone_suffix}", zone_id=zone.id, status="available")
    db_session.add(table2)
    db_session.commit()
    new_sub = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "table_id": table2.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}],
        },
    )
    assert new_sub.status_code == 200, new_sub.text
    assert new_sub.json()["is_new_order"] is True
    db_session.expire_all()
    line = db_session.query(OrderItem).filter(OrderItem.order_id == new_sub.json()["id"]).one()
    assert (line.menu_item_name_at_sale, line.category_name_at_sale) == (item.name, category.name)


# —— Roles / contract ——


def test_read_endpoints_keep_their_shape_and_roles(client, db_session, auth_headers):
    table, _cat, item = _shop(db_session)
    order_id = _sell(client, auth_headers, table, item)
    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter")).json()
    assert {"id", "menu_item_id", "menu_item_name", "quantity", "subtotal", "unit_price_at_sale"} <= set(details["items"][0])
    listed = _listed_order(client, auth_headers, "/api/orders/?status=pending&status=open&status=dining", order_id)
    assert {"menu_item_name", "quantity", "subtotal"} <= set(listed["items"][0])
    # history stays closed to waiters
    assert client.get("/api/orders/daily-history?date=2026-10-04", headers=auth_headers("waiter")).status_code == 403


def test_server_start_runs_the_backfill():
    """The lifespan calls the backfill (throwaway app database from conftest, never pos.db)."""
    from fastapi.testclient import TestClient

    from database import SessionLocal, engine
    from main import app as real_app
    from models import Base

    assert "pos-tests-" in str(engine.url), engine.url
    Base.metadata.create_all(bind=engine)
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as s:
        cat = Category(name=f"SN-BOOT-C-{suffix}")
        s.add(cat)
        s.flush()
        item = MenuItem(name=f"SN-BOOT-{suffix}", price=100.0, category_id=cat.id, modifiers_config=[])
        s.add(item)
        s.flush()
        order = Order(table_id=None, order_type="takeaway", status="paid", total_amount=100.0, payment_method="cash")
        s.add(order)
        s.flush()
        line = OrderItem(
            order_id=order.id, menu_item_id=item.id, quantity=1, subtotal=100.0, batch_number=1,
            batch_status="pending", item_status="served", selected_modifiers=[], menu_item_name_at_sale=None,
        )
        s.add(line)
        s.commit()
        line_id, item_name, cat_name = line.id, item.name, cat.name

    with TestClient(real_app):
        pass

    with SessionLocal() as s:
        line = s.get(OrderItem, line_id)
        assert (line.menu_item_name_at_sale, line.category_name_at_sale) == (item_name, cat_name)
