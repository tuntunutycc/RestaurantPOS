"""Changing menu prices: never a system error, never changes recorded money.

Spec: specs/feature-menu-price-safety
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from models import Category, MenuItem, Order, OrderItem, Table, Zone
from test_payment_kpay_mmqr import _checkout


# —— helpers ——

# The test database is shared by the whole suite and a menu item with an infinite
# or negative price would break every later test that lists the menu, so those
# rows are removed after each test (none of them has order lines).
_BAD_ITEM_IDS: list[int] = []


@pytest.fixture(autouse=True)
def _remove_bad_menu_items(db_session):
    yield
    db_session.rollback()
    if _BAD_ITEM_IDS:
        # Only rows nothing refers to (items with order lines stay, like any sold item).
        used = {row[0] for row in db_session.query(OrderItem.menu_item_id).filter(OrderItem.menu_item_id.in_(_BAD_ITEM_IDS))}
        unused = [i for i in _BAD_ITEM_IDS if i not in used]
        if unused:
            db_session.query(MenuItem).filter(MenuItem.id.in_(unused)).delete(synchronize_session=False)
            db_session.commit()
        _BAD_ITEM_IDS.clear()


def _shop(db_session, *, price=3500.0, **menu_kwargs):
    suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"PS-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"PS-T-{suffix}", zone_id=zone.id, status="available")
    category = Category(name=f"PS-C-{suffix}")
    db_session.add_all([table, category])
    db_session.flush()
    item = MenuItem(
        name=f"PS-M-{suffix}", price=price, category_id=category.id,
        is_available=True, modifiers_config=[], **menu_kwargs,
    )
    db_session.add(item)
    db_session.commit()
    _BAD_ITEM_IDS.append(item.id)
    return table, category, item


def _put_raw(client, headers, item_id, raw: str):
    return client.put(
        f"/api/menu-items/{item_id}",
        headers={**headers, "Content-Type": "application/json"},
        content=raw,
    )


def _set_price(client, auth_headers, item_id, price):
    res = client.put(f"/api/menu-items/{item_id}", headers=auth_headers("admin"), json={"price": price})
    assert res.status_code == 200, res.text
    return res.json()


def _order(client, auth_headers, table, item, *, quantity=1, takeaway=False, modifiers=None):
    body = {
        "table_id": None if takeaway else table.id,
        "order_type": "takeaway" if takeaway else "dine_in",
        "items": [{
            "menu_item_id": item.id, "quantity": quantity, "is_takeaway": takeaway,
            "selected_modifiers": modifiers or [],
        }],
    }
    return client.post("/api/orders/", headers=auth_headers("waiter"), json=body)


def _details(client, auth_headers, order_id):
    res = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    return res.json()


def _stored(db_session, item_id) -> MenuItem:
    db_session.expire_all()
    return db_session.query(MenuItem).filter(MenuItem.id == item_id).one()


# —— a price change does not touch money that was already recorded ——


def test_open_order_keeps_the_old_price_and_new_items_use_the_new_price(
    client, db_session, auth_headers
):
    table, _, item = _shop(db_session, price=3500.0)
    first = _order(client, auth_headers, table, item)
    assert first.status_code == 200, first.text
    order_id = first.json()["id"]

    _set_price(client, auth_headers, item.id, 4000.0)

    before_add = _details(client, auth_headers, order_id)
    assert before_add["total_amount"] == 3500.0  # the price rise did not touch the open bill
    assert before_add["items"][0]["unit_price_at_sale"] == 3500.0

    second = _order(client, auth_headers, table, item)  # add-on to the same table
    assert second.status_code == 200 and second.json()["id"] == order_id

    after_add = _details(client, auth_headers, order_id)
    assert [i["unit_price_at_sale"] for i in after_add["items"]] == [3500.0, 4000.0]
    assert [i["subtotal"] for i in after_add["items"]] == [3500.0, 4000.0]
    assert after_add["total_amount"] == 7500.0
    assert after_add["breakdown_grand_total"] == 7500.0

    paid = _checkout(client, auth_headers("cashier"), order_id, payment_method="cash", amount_tendered=7500.0)
    assert paid.status_code == 200, paid.text
    assert paid.json()["total_amount"] == 7500.0
    assert paid.json()["cash_amount"] == 7500.0


def test_cancelling_a_line_after_a_price_change_uses_the_price_it_was_sold_at(
    client, db_session, auth_headers
):
    table, _, item = _shop(db_session, price=3500.0)
    order_id = _order(client, auth_headers, table, item).json()["id"]
    _set_price(client, auth_headers, item.id, 5000.0)
    assert _order(client, auth_headers, table, item).status_code == 200  # 5000 line
    lines = _details(client, auth_headers, order_id)["items"]
    assert [i["subtotal"] for i in lines] == [3500.0, 5000.0]

    res = client.put(
        f"/api/orders/{order_id}/items/{lines[0]['id']}/status",
        headers=auth_headers("waiter"), json={"status": "cancelled"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 5000.0  # 8500 - 3500 (its own price, not 5000)


def test_a_paid_order_and_the_reports_do_not_change_when_the_price_changes(
    client, db_session, auth_headers, seed_users
):
    table, _, item = _shop(db_session, price=3500.0)
    order_id = _order(client, auth_headers, table, item, quantity=2).json()["id"]
    paid = _checkout(client, auth_headers("cashier"), order_id, payment_method="cash", amount_tendered=7000.0)
    assert paid.status_code == 200, paid.text
    day = datetime(2035, 5, 6, 10, 0, 0)
    db_session.query(Order).filter(Order.id == order_id).update({Order.created_at: day})
    db_session.commit()

    def snapshot():
        hist = client.get("/api/orders/daily-history?date=2035-05-06", headers=auth_headers("admin")).json()
        report = client.get(
            "/api/reports/sales/by-cashier?start_date=2035-05-06&end_date=2035-05-06",
            headers=auth_headers("admin"),
        ).json()
        return hist, report, _details(client, auth_headers, order_id)

    before = snapshot()
    assert before[0]["grand_total"] == 7000.0
    for new_price in (4000.0, 9999.0, 1.0, 0.0):
        _set_price(client, auth_headers, item.id, new_price)
    assert snapshot() == before


def test_changing_tax_discount_or_modifiers_does_not_touch_an_open_order(client, db_session, auth_headers):
    table, _, item = _shop(db_session, price=1000.0, tax_type="percentage", tax_value=5.0)
    order_id = _order(client, auth_headers, table, item).json()["id"]
    before = _details(client, auth_headers, order_id)
    assert before["total_amount"] == 1050.0

    res = client.put(
        f"/api/menu-items/{item.id}", headers=auth_headers("admin"),
        json={"price": 2000.0, "tax_type": "percentage", "tax_value": 10.0,
              "discount_type": "percentage", "discount_value": 50.0},
    )
    assert res.status_code == 200, res.text
    assert _details(client, auth_headers, order_id) == before


def test_a_price_below_a_fixed_discount_gives_a_free_item_not_an_error(client, db_session, auth_headers):
    table, _, item = _shop(db_session, price=1000.0, discount_type="fixed", discount_value=500.0)
    _set_price(client, auth_headers, item.id, 300.0)
    res = _order(client, auth_headers, table, item)
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 0.0


def test_a_percentage_discount_cannot_push_an_item_below_zero(client, db_session, auth_headers):
    """Bad data from before validation existed (150 %) now means a free item, not a 500."""
    table, _, item = _shop(db_session, price=1000.0, discount_type="percentage", discount_value=150.0)
    res = _order(client, auth_headers, table, item)
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 0.0


# —— menu input is validated ——


@pytest.mark.parametrize(
    "raw",
    [
        '{"price": null}',
        '{"price": NaN}',
        '{"price": Infinity}',
        '{"price": -Infinity}',
        '{"price": -5}',
        '{"price": 1e308}',
        '{"price": 1000000000.01}',
        '{"price": "abc"}',
        '{"name": null}',
        '{"name": ""}',
        '{"name": "   "}',
        '{"category_id": null}',
        '{"discount_type": null}',
        '{"discount_value": null}',
        '{"discount_value": NaN}',
        '{"discount_value": -1}',
        '{"discount_type": "percentage", "discount_value": 100.5}',
        '{"discount_type": "percentage", "discount_value": 150}',
        '{"tax_type": null}',
        '{"tax_value": null}',
        '{"tax_value": -1}',
        '{"tax_type": "percentage", "tax_value": 500}',
        '{"takeaway_price": -1}',
        '{"takeaway_price": NaN}',
        '{"discount_price": -1}',
        '{"is_available": null}',
        '{"is_promoted": null}',
        '{"modifiers_config": null}',
        '{"modifiers_config": [{"group": "g", "options": [{"name": "x", "price": NaN}]}]}',
        '{"modifiers_config": [{"group": "g", "options": [{"name": "x", "price": Infinity}]}]}',
        '{"modifiers_config": [{"group": "g", "options": [{"name": "x", "price": 1e12}]}]}',
    ],
)
def test_a_bad_menu_update_is_422_and_changes_nothing(client, db_session, auth_headers, raw):
    _, _, item = _shop(db_session, price=3500.0)
    res = _put_raw(client, auth_headers("admin"), item.id, raw)
    assert res.status_code == 422, res.text
    stored = _stored(db_session, item.id)
    assert stored.price == 3500.0 and stored.name == item.name
    assert (stored.discount_type, stored.discount_value, stored.tax_type, stored.tax_value) == ("none", 0.0, "none", 0.0)
    assert stored.modifiers_config == [] and stored.takeaway_price is None


def test_a_percentage_over_100_is_judged_on_the_values_after_a_partial_update(client, db_session, auth_headers):
    _, _, item = _shop(db_session, price=1000.0, discount_type="percentage", discount_value=20.0)
    only_value = client.put(f"/api/menu-items/{item.id}", headers=auth_headers("admin"), json={"discount_value": 150})
    assert only_value.status_code == 422, only_value.text
    assert _stored(db_session, item.id).discount_value == 20.0

    # The other way round: the stored value is already above 100 (old data).
    _, _, other = _shop(db_session, price=1000.0, discount_type="fixed", discount_value=150.0, tax_type="fixed", tax_value=150.0)
    only_type = client.put(f"/api/menu-items/{other.id}", headers=auth_headers("admin"), json={"discount_type": "percentage"})
    assert only_type.status_code == 422, only_type.text
    tax_type = client.put(f"/api/menu-items/{other.id}", headers=auth_headers("admin"), json={"tax_type": "percentage"})
    assert tax_type.status_code == 422, tax_type.text
    assert _stored(db_session, other.id).discount_type == "fixed"


def test_unknown_category_is_404_on_update_and_create(client, db_session, auth_headers):
    _, category, item = _shop(db_session)
    upd = client.put(f"/api/menu-items/{item.id}", headers=auth_headers("admin"), json={"category_id": 999999})
    assert upd.status_code == 404 and "999999" in upd.json()["detail"]
    assert _stored(db_session, item.id).category_id == category.id
    create = client.post(
        "/api/menu-items/", headers=auth_headers("admin"),
        json={"name": "Ghost", "price": 10, "category_id": 999999},
    )
    assert create.status_code == 404
    assert db_session.query(MenuItem).filter(MenuItem.name == "Ghost").count() == 0


@pytest.mark.parametrize(
    "body",
    [
        {"name": "n", "price": -1},
        {"name": "n", "price": None},
        {"name": "  ", "price": 1},
        {"name": "x" * 256, "price": 1},
        {"name": "n", "price": 1e12},
        {"name": "n", "price": 1, "discount_type": "percentage", "discount_value": 101},
        {"name": "n", "price": 1, "tax_type": "percentage", "tax_value": 101},
        {"name": "n", "price": 1, "takeaway_price": -2},
    ],
)
def test_a_bad_new_menu_item_is_422(client, db_session, auth_headers, body):
    _, category, _ = _shop(db_session)
    res = client.post("/api/menu-items/", headers=auth_headers("admin"), json={**body, "category_id": category.id})
    assert res.status_code == 422, res.text


def test_new_menu_item_name_is_trimmed(client, db_session, auth_headers):
    _, category, _ = _shop(db_session)
    res = client.post(
        "/api/menu-items/", headers=auth_headers("admin"),
        json={"name": "  Tea Leaf Salad  ", "price": 3000, "category_id": category.id},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Tea Leaf Salad"


@pytest.mark.parametrize("price", ["nan", "inf", "-inf", "-1", "1e12"])
def test_upload_form_refuses_bad_prices(client, db_session, auth_headers, price):
    _, category, _ = _shop(db_session)
    res = client.post(
        "/api/menu-items/upload", headers=auth_headers("admin"),
        data={"name": "Upload", "price": price, "category_id": str(category.id)},
    )
    assert res.status_code == 422, res.text
    assert db_session.query(MenuItem).filter(MenuItem.name == "Upload").count() == 0


def test_upload_form_refuses_blank_name_and_unknown_category(client, db_session, auth_headers):
    _, category, _ = _shop(db_session)
    blank = client.post(
        "/api/menu-items/upload", headers=auth_headers("admin"),
        data={"name": "   ", "price": "10", "category_id": str(category.id)},
    )
    assert blank.status_code == 422
    ghost = client.post(
        "/api/menu-items/upload", headers=auth_headers("admin"),
        data={"name": "Upload2", "price": "10", "category_id": "999999"},
    )
    assert ghost.status_code == 404


# —— what stays allowed ——


@pytest.mark.parametrize(
    "body",
    [
        {"price": 0},
        {"price": 4000.5},
        {"price": 1000000000},
        {"discount_price": None},
        {"takeaway_price": None},
        {"description": None},
        {"image_url": None},
        {"discount_type": "percentage", "discount_value": 100},
        {"tax_type": "percentage", "tax_value": 100},
        {"discount_type": "fixed", "discount_value": 99999},  # more than the price: capped when ordering
        {"modifiers_config": [{"group": "Size", "options": [{"name": "No meat", "price": -500}, {"name": "Big", "price": 300}]}]},
        {"modifiers_config": []},
    ],
)
def test_valid_updates_still_work(client, db_session, auth_headers, body):
    _, _, item = _shop(db_session, price=3500.0)
    res = client.put(f"/api/menu-items/{item.id}", headers=auth_headers("admin"), json=body)
    assert res.status_code == 200, res.text


def test_a_field_that_is_not_sent_is_left_alone(client, db_session, auth_headers):
    _, _, item = _shop(db_session, price=3500.0, tax_type="percentage", tax_value=5.0)
    res = client.put(f"/api/menu-items/{item.id}", headers=auth_headers("admin"), json={"price": 3800.0})
    assert res.status_code == 200
    stored = _stored(db_session, item.id)
    assert (stored.price, stored.tax_type, stored.tax_value, stored.name) == (3800.0, "percentage", 5.0, item.name)


@pytest.mark.parametrize("role, status", [("admin", 200), ("root", 200), ("cashier", 403), ("waiter", 403)])
def test_only_the_admin_panel_roles_may_change_a_price(client, db_session, auth_headers, role, status):
    _, _, item = _shop(db_session, price=3500.0)
    res = client.put(f"/api/menu-items/{item.id}", headers=auth_headers(role), json={"price": 3600.0})
    assert res.status_code == status, res.text
    assert _stored(db_session, item.id).price == (3600.0 if status == 200 else 3500.0)


# —— ordering with bad data that is already in a database ——


def _no_new_order(db_session, table_id, call):
    before = db_session.query(Order).count()
    res = call()
    db_session.expire_all()
    assert db_session.query(Order).count() == before
    return res


@pytest.mark.parametrize(
    "menu_kwargs",
    [
        {"price": -5.0},
        {"price": float("inf")},
        {"price": 1e12},
        {"price": 100.0, "tax_type": "fixed", "tax_value": float("inf")},
    ],
)
def test_ordering_an_item_with_a_bad_stored_price_is_400_and_saves_nothing(
    client, db_session, auth_headers, menu_kwargs
):
    table, _, item = _shop(db_session, **menu_kwargs)
    res = _no_new_order(db_session, table.id, lambda: _order(client, auth_headers, table, item))
    assert res.status_code == 400, res.text
    assert item.name in res.json()["detail"]
    db_session.refresh(table)
    assert str(getattr(table.status, "value", table.status)) == "available"


def test_a_bad_takeaway_price_is_refused_only_for_takeaway_lines(client, db_session, auth_headers):
    table, _, item = _shop(db_session, price=1000.0, takeaway_price=-1.0)
    refused = _no_new_order(
        db_session, None, lambda: _order(client, auth_headers, table, item, takeaway=True)
    )
    assert refused.status_code == 400, refused.text
    dine_in = _order(client, auth_headers, table, item)
    assert dine_in.status_code == 200 and dine_in.json()["total_amount"] == 1000.0


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-Infinity", "1e12", "-1e12", '"abc"'])
def test_a_waiter_screen_cannot_send_a_broken_modifier_price(client, db_session, auth_headers, price):
    table, _, item = _shop(db_session)
    raw = (
        '{"table_id": %d, "order_type": "dine_in", "items": [{"menu_item_id": %d, "quantity": 1, '
        '"selected_modifiers": [{"name": "x", "price": %s}]}]}' % (table.id, item.id, price)
    )
    before = db_session.query(Order).count()
    res = client.post(
        "/api/orders/", headers={**auth_headers("waiter"), "Content-Type": "application/json"}, content=raw
    )
    assert res.status_code == 422, res.text
    db_session.expire_all()
    assert db_session.query(Order).count() == before


def test_a_modifier_that_would_make_the_line_negative_is_400_and_saves_nothing(client, db_session, auth_headers):
    table, _, item = _shop(db_session, price=1000.0)
    res = _no_new_order(
        db_session, table.id,
        lambda: _order(client, auth_headers, table, item, modifiers=[{"name": "Free!", "price": -999999}]),
    )
    assert res.status_code == 400, res.text


def test_a_small_negative_modifier_still_works(client, db_session, auth_headers):
    table, _, item = _shop(db_session, price=1000.0)
    res = _order(client, auth_headers, table, item, modifiers=[{"name": "No meat", "price": -200}])
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 800.0


def test_an_add_on_to_an_open_order_with_a_bad_item_is_refused_and_keeps_the_bill(client, db_session, auth_headers):
    table, category, good = _shop(db_session, price=1000.0)
    order_id = _order(client, auth_headers, table, good).json()["id"]
    bad = MenuItem(name=f"Bad-{uuid.uuid4().hex[:5]}", price=-1.0, category_id=category.id, is_available=True, modifiers_config=[])
    db_session.add(bad)
    db_session.commit()
    _BAD_ITEM_IDS.append(bad.id)

    res = _order(client, auth_headers, table, bad)
    assert res.status_code == 400, res.text
    db_session.expire_all()
    assert db_session.query(OrderItem).filter(OrderItem.order_id == order_id).count() == 1
    assert _details(client, auth_headers, order_id)["total_amount"] == 1000.0


def test_the_answer_is_still_json_after_a_valid_update(client, db_session, auth_headers):
    """An infinite price used to be saved and then crash the answer."""
    _, _, item = _shop(db_session, price=3500.0)
    res = client.put(f"/api/menu-items/{item.id}", headers=auth_headers("admin"), json={"price": 3600.0})
    assert json.loads(res.text)["price"] == 3600.0
