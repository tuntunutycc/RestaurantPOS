"""
PUT /api/orders/{order_id}/items/{item_id}/status must answer with OrderDetailsResponse
(the same shape as GET /api/orders/{order_id}/details).

Why: the waiter "Table Details" panel redraws its list from this answer. The old answer
(OrderResponseDetail) had no item `id`, so the redrawn buttons pointed at item "undefined"
and the next "Mark as Served" failed with "Load Failed".
"""
import uuid

import pytest

from models import Category, MenuItem, Table, Zone

ITEM_COUNT = 6


def _make_order(client, db_session, auth_headers, count=ITEM_COUNT):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"IS-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"IS-T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    category = Category(name=f"IS-C-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu = []
    for i in range(count):
        m = MenuItem(
            name=f"IS-M{i}-{suffix}",
            price=1000.0 * (i + 1),
            category_id=category.id,
            is_available=True,
            modifiers_config=[],
        )
        db_session.add(m)
        menu.append(m)
    db_session.commit()
    res = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={
            "table_id": table.id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": m.id, "quantity": 1} for m in menu],
        },
    )
    assert res.status_code == 200, res.text
    order_id = res.json()["id"]
    details = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert details.status_code == 200, details.text
    return order_id, [i["id"] for i in details.json()["items"]]


def _put(client, headers, order_id, item_id, status):
    return client.put(
        f"/api/orders/{order_id}/items/{item_id}/status",
        headers=headers,
        json={"status": status},
    )


def test_every_item_in_the_answer_carries_its_id(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers)
    res = _put(client, auth_headers("waiter"), order_id, ids[0], "served")
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert [i["id"] for i in items] == ids
    for item in items:
        assert isinstance(item["id"], int)
        assert isinstance(item["menu_item_id"], int)


@pytest.mark.parametrize("status", ["served", "pending", "cooking"])
def test_answer_is_identical_to_get_details(client, db_session, auth_headers, status):
    order_id, ids = _make_order(client, db_session, auth_headers)
    headers = auth_headers("waiter")
    put = _put(client, headers, order_id, ids[1], status)
    assert put.status_code == 200, put.text
    get = client.get(f"/api/orders/{order_id}/details", headers=headers)
    assert put.json() == get.json()
    assert put.json()["items"][1]["item_status"] == status


def test_answer_has_breakdown_fields_for_the_panel(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers)
    body = _put(client, auth_headers("waiter"), order_id, ids[0], "served").json()
    for key in (
        "breakdown_subtotal",
        "breakdown_discount_total",
        "breakdown_tax_total",
        "breakdown_grand_total",
    ):
        assert key in body, key
    assert body["breakdown_grand_total"] == pytest.approx(body["total_amount"])


def test_waiter_can_serve_every_item_one_after_another(client, db_session, auth_headers):
    """The reported case: only ~3 clicks worked, the rest failed."""
    order_id, ids = _make_order(client, db_session, auth_headers)
    headers = auth_headers("waiter")
    for n, item_id in enumerate(ids, start=1):
        res = _put(client, headers, order_id, item_id, "served")
        assert res.status_code == 200, f"click {n}: {res.text}"
        body = res.json()
        statuses = [i["item_status"] for i in body["items"]]
        assert statuses.count("served") == n
        # Every id in the answer is usable for the next click.
        assert all(isinstance(i["id"], int) and i["id"] > 0 for i in body["items"])
    # Undo them all again.
    for n, item_id in enumerate(ids, start=1):
        res = _put(client, headers, order_id, item_id, "pending")
        assert res.status_code == 200, f"undo {n}: {res.text}"
        assert [i["item_status"] for i in res.json()["items"]].count("pending") == n


def test_serving_does_not_change_the_money(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers)
    headers = auth_headers("waiter")
    before = client.get(f"/api/orders/{order_id}/details", headers=headers).json()
    after = _put(client, headers, order_id, ids[2], "served").json()
    assert after["total_amount"] == before["total_amount"]
    assert after["breakdown_grand_total"] == before["breakdown_grand_total"]


def test_cancel_item_lowers_the_total_and_keeps_ids(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers)
    headers = auth_headers("waiter")
    before = client.get(f"/api/orders/{order_id}/details", headers=headers).json()
    price = before["items"][0]["subtotal"]
    res = _put(client, headers, order_id, ids[0], "cancelled")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] != "cancelled"  # other lines still active
    assert body["total_amount"] == pytest.approx(before["total_amount"] - price)
    assert body["breakdown_grand_total"] == pytest.approx(body["total_amount"])
    assert [i["id"] for i in body["items"]] == ids
    assert body["items"][0]["item_status"] == "cancelled"


def test_cancelling_the_last_active_item_cancels_the_order(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers, count=1)
    res = _put(client, auth_headers("waiter"), order_id, ids[0], "cancelled")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "cancelled"
    assert float(body["total_amount"]) == 0.0
    assert [i["id"] for i in body["items"]] == ids


@pytest.mark.parametrize("role", ["waiter", "cashier", "admin", "root"])
def test_pos_order_roles_may_update_item_status(client, db_session, auth_headers, role):
    order_id, ids = _make_order(client, db_session, auth_headers, count=2)
    res = _put(client, auth_headers(role), order_id, ids[0], "served")
    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["id"] == ids[0]


def test_requires_login(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers, count=1)
    res = client.put(
        f"/api/orders/{order_id}/items/{ids[0]}/status", json={"status": "served"}
    )
    assert res.status_code in (401, 403)


def test_invalid_status_and_unknown_ids_are_refused(client, db_session, auth_headers):
    order_id, ids = _make_order(client, db_session, auth_headers, count=1)
    headers = auth_headers("waiter")
    assert _put(client, headers, order_id, ids[0], "eaten").status_code == 422
    assert _put(client, headers, order_id, ids[0] + 9999, "served").status_code == 404
    assert _put(client, headers, order_id + 9999, ids[0], "served").status_code == 404
    # A refused update changed nothing.
    after = client.get(f"/api/orders/{order_id}/details", headers=headers).json()
    assert after["items"][0]["item_status"] == "pending"
