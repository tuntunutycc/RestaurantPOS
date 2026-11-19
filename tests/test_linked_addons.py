"""Linked add-ons: an add-on option may follow a main menu item's price.

Spec: specs/feature-linked-addons
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from models import Category, MenuItem, Order, OrderItem, PrintJob, Table, Zone

GROUP = "Extras"


# —— helpers ——


def _uid() -> str:
    return uuid.uuid4().hex[:6]


class Shop:
    """A category, a table and helpers to build menu items for one test."""

    def __init__(self, db_session):
        self.db = db_session
        suffix = _uid()
        zone = Zone(name=f"LA-Z-{suffix}")
        db_session.add(zone)
        db_session.flush()
        self.table = Table(name=f"LA-T-{suffix}", zone_id=zone.id, status="available")
        self.category = Category(name=f"LA-C-{suffix}")
        db_session.add_all([self.table, self.category])
        db_session.commit()
        self.created: list[int] = []

    def item(self, name=None, price=1000.0, modifiers=None) -> MenuItem:
        item = MenuItem(
            name=name or f"LA-M-{_uid()}", price=price, category_id=self.category.id,
            is_available=True, modifiers_config=modifiers or [],
        )
        self.db.add(item)
        self.db.commit()
        self.created.append(item.id)
        return item

    def new_table(self) -> Table:
        suffix = _uid()
        table = Table(name=f"LA-T2-{suffix}", zone_id=self.table.zone_id, status="available")
        self.db.add(table)
        self.db.commit()
        return table


def _groups(*options, group=GROUP):
    return [{"group": group, "is_required": False, "options": list(options)}]


def _opt(name, price=0.0, link=None, override=None):
    option = {"name": name, "price": price}
    if link is not None:
        option["linked_menu_item_id"] = link
    if override is not None:
        option["price_override"] = override
    return option


def _create(client, auth_headers, shop, options, *, name=None, price=1000.0):
    return client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json={
            "name": name or f"LA-H-{_uid()}", "price": price, "category_id": shop.category.id,
            "modifiers_config": _groups(*options),
        },
    )


def _created(client, auth_headers, shop, options, **kw) -> dict:
    res = _create(client, auth_headers, shop, options, **kw)
    assert res.status_code == 200, res.text
    shop.created.append(res.json()["id"])
    return res.json()


def _put(client, auth_headers, item_id, body, role="admin"):
    return client.put(f"/api/menu-items/{item_id}", headers=auth_headers(role), json=body)


def _options(item_json) -> list[dict]:
    return [o for g in item_json["modifiers_config"] for o in g["options"]]


def _stored(db_session, item_id) -> list:
    db_session.expire_all()
    return db_session.get(MenuItem, item_id).modifiers_config


def _stored_options(db_session, item_id) -> list[dict]:
    return [o for g in _stored(db_session, item_id) for o in g["options"]]


def _order(client, auth_headers, table, item, modifiers, *, quantity=1, path="create"):
    line = {"menu_item_id": item.id if hasattr(item, "id") else item, "quantity": quantity,
            "selected_modifiers": modifiers}
    if path == "submit":
        return client.post(
            "/api/orders/submit", headers=auth_headers("waiter"),
            json={"table_id": table.id, "order_type": "dine_in", "items": [line]},
        )
    return client.post(
        "/api/orders/", headers=auth_headers("waiter"),
        json={"table_id": table.id, "order_type": "dine_in", "items": [line]},
    )


def _mod(name, price=0.0, qty=1, group=GROUP, **extra):
    return {"name": name, "price": price, "quantity": qty, "group": group, **extra}


def _details(client, auth_headers, order_id) -> dict:
    res = client.get(f"/api/orders/{order_id}/details", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    return res.json()


def _line_mods(db_session, order_id) -> list[list[dict]]:
    db_session.expire_all()
    return [oi.selected_modifiers for oi in db_session.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id)]


def _holder_with_link(client, auth_headers, shop, target, *, price=2000.0, name="Egg", override=None, link_price=0.0):
    return _created(client, auth_headers, shop, [_opt(name, link_price, link=target.id, override=override)], price=price)


@pytest.fixture()
def broadcasts(client):
    manager = client.app.state.ws_manager
    mock = AsyncMock()
    original = manager.broadcast
    manager.broadcast = mock
    try:
        yield mock
    finally:
        manager.broadcast = original


def _updated_ids(mock) -> list[int]:
    return [call.args[1]["id"] for call in mock.await_args_list if call.args and call.args[0] == "menu_item_updated"]


# —— contract / backward compatibility ——


def test_unlinked_option_response_has_null_link_fields_and_stores_no_extra_keys(client, db_session, auth_headers):
    shop = Shop(db_session)
    item = _created(client, auth_headers, shop, [_opt("Plain", 500)])
    option = _options(item)[0]
    assert option["linked_menu_item_id"] is None and option["price_override"] is None
    assert option["price"] == 500
    assert _stored_options(db_session, item["id"]) == [{"name": "Plain", "price": 500.0}]


def test_old_row_without_link_keys_reads_as_unlinked(client, db_session, auth_headers):
    shop = Shop(db_session)
    legacy = shop.item(modifiers=[{"group": "", "is_required": False, "options": [{"name": "Old", "price": 300}]}])
    res = client.get("/api/menu-items/", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    row = next(i for i in res.json() if i["id"] == legacy.id)
    assert _options(row) == [{"name": "Old", "price": 300.0, "linked_menu_item_id": None, "price_override": None}]


def test_unlinked_ordering_is_unchanged(client, db_session, auth_headers):
    shop = Shop(db_session)
    item = shop.item(price=2000.0, modifiers=_groups({"name": "Plain", "price": 500}))
    res = _order(client, auth_headers, shop.table, item, [_mod("Plain", 500, qty=2)])
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 3000.0
    assert _line_mods(db_session, res.json()["id"]) == [
        [{"name": "Plain", "price": 500.0, "group": GROUP, "quantity": 2}]
    ]


# —— FR-L1: saving ——


def test_link_to_missing_or_deleted_item_is_404_and_nothing_is_saved(client, db_session, auth_headers):
    shop = Shop(db_session)
    gone = shop.item()
    assert client.delete(f"/api/menu-items/{gone.id}", headers=auth_headers("admin")).status_code == 200
    for target_id in (987654321, gone.id):
        name = f"LA-NO-{_uid()}"
        res = _create(client, auth_headers, shop, [_opt("X", 1, link=target_id)], name=name)
        assert res.status_code == 404, res.text
        assert f"Menu item id {target_id} not found" in res.text
        assert db_session.query(MenuItem).filter(MenuItem.name == name).count() == 0
    holder = shop.item(modifiers=_groups({"name": "Keep", "price": 5}))
    before = _stored(db_session, holder.id)
    res = _put(client, auth_headers, holder.id, {"modifiers_config": _groups(_opt("X", 1, link=gone.id))})
    assert res.status_code == 404
    assert _stored(db_session, holder.id) == before


def test_link_to_itself_is_422(client, db_session, auth_headers):
    shop = Shop(db_session)
    holder = shop.item(modifiers=_groups({"name": "Keep", "price": 5}))
    before = _stored(db_session, holder.id)
    res = _put(client, auth_headers, holder.id, {"modifiers_config": _groups(_opt("Me", 1, link=holder.id))})
    assert res.status_code == 422, res.text
    assert _stored(db_session, holder.id) == before


def test_price_override_without_link_is_422(client, db_session, auth_headers):
    shop = Shop(db_session)
    name = f"LA-OV-{_uid()}"
    res = _create(client, auth_headers, shop, [_opt("X", 1, override=100)], name=name)
    assert res.status_code == 422, res.text
    assert db_session.query(MenuItem).filter(MenuItem.name == name).count() == 0


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity", "1e12", '"abc"'])
def test_bad_price_override_is_422(client, db_session, auth_headers, bad):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    name = f"LA-BAD-{_uid()}"
    raw = (
        '{"name": "%s", "price": 1000, "category_id": %d, "modifiers_config": [{"group": "G", "options": '
        '[{"name": "X", "price": 1, "linked_menu_item_id": %d, "price_override": %s}]}]}'
    ) % (name, shop.category.id, target.id, bad)
    res = client.post("/api/menu-items/", headers={**auth_headers("admin"), "Content-Type": "application/json"}, content=raw)
    assert res.status_code == 422, res.text
    assert db_session.query(MenuItem).filter(MenuItem.name == name).count() == 0


def test_stored_price_is_overwritten_by_the_server(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    followed = _created(client, auth_headers, shop, [_opt("Follow", 1, link=target.id)])
    assert _options(followed)[0]["price"] == 700.0
    over = _created(client, auth_headers, shop, [_opt("Over", 1, link=target.id, override=300)])
    assert _options(over)[0]["price"] == 300.0
    free = _created(client, auth_headers, shop, [_opt("Free", 99, link=target.id, override=0)])
    assert _options(free)[0]["price"] == 0.0 and _options(free)[0]["price_override"] == 0.0
    assert [o["price"] for o in _stored_options(db_session, followed["id"])] == [700.0]


def test_blank_name_is_filled_from_the_target_and_a_given_name_is_kept(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(name=f"LA-TARGET-{_uid()}", price=700.0)
    filled = _created(client, auth_headers, shop, [_opt("   ", 0, link=target.id)])
    assert _options(filled)[0]["name"] == target.name
    kept = _created(client, auth_headers, shop, [_opt("My own name", 0, link=target.id)])
    assert _options(kept)[0]["name"] == "My own name"


def test_duplicate_group_and_name_refused_only_when_a_link_is_involved(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    res = _create(client, auth_headers, shop, [_opt("Dup", 1, link=target.id), _opt("Dup", 5)])
    assert res.status_code == 422, res.text
    ok = _create(client, auth_headers, shop, [_opt("Same", 1), _opt("Same", 2)])
    assert ok.status_code == 200, ok.text
    shop.created.append(ok.json()["id"])


def test_put_without_modifiers_config_keeps_links(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    holder = _holder_with_link(client, auth_headers, shop, target)
    res = _put(client, auth_headers, holder["id"], {"name": f"LA-REN-{_uid()}"})
    assert res.status_code == 200, res.text
    assert _options(res.json())[0]["linked_menu_item_id"] == target.id
    assert _stored_options(db_session, holder["id"])[0]["linked_menu_item_id"] == target.id


def test_form_round_trip_name_autofill_override_and_unlink(client, db_session, auth_headers):
    """The payload shape counter.js sends: link -> override -> follow -> None."""
    shop = Shop(db_session)
    target = shop.item(name=f"LA-RT-{_uid()}", price=900.0)
    holder = _created(client, auth_headers, shop, [_opt(target.name, 900, link=target.id)])
    assert _options(holder)[0]["linked_menu_item_id"] == target.id
    res = _put(client, auth_headers, holder["id"], {"modifiers_config": _groups(_opt(target.name, 0, link=target.id, override=250))})
    assert _options(res.json())[0]["price"] == 250.0
    res = _put(client, auth_headers, holder["id"], {"modifiers_config": _groups(_opt(target.name, 0, link=target.id))})
    assert _options(res.json())[0]["price"] == 900.0 and _options(res.json())[0]["price_override"] is None
    res = _put(client, auth_headers, holder["id"], {"modifiers_config": _groups(_opt(target.name, 900))})
    assert _options(res.json())[0]["linked_menu_item_id"] is None
    assert _stored_options(db_session, holder["id"]) == [{"name": target.name, "price": 900.0}]


# —— FR-L2: delete ——


def test_delete_of_a_linked_target_is_refused_and_lists_the_holders(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(name=f"LA-EGG-{_uid()}", price=700.0)
    h1 = _holder_with_link(client, auth_headers, shop, target)
    h2 = _holder_with_link(client, auth_headers, shop, target)
    res = client.delete(f"/api/menu-items/{target.id}", headers=auth_headers("admin"))
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert target.name in detail and "linked as an add-on by" in detail
    for h in (h1, h2):
        assert f"{h['name']} (id {h['id']})" in detail
    db_session.expire_all()
    assert db_session.get(MenuItem, target.id).is_deleted is False
    assert _stored_options(db_session, h1["id"])[0]["linked_menu_item_id"] == target.id


def test_delete_message_is_cut_after_twenty_holders(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    for i in range(23):
        shop.item(name=f"LA-MANY-{i:02d}-{_uid()}", modifiers=_groups(_opt("E", 700, link=target.id)))
    res = client.delete(f"/api/menu-items/{target.id}", headers=auth_headers("admin"))
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "and 3 more" in detail
    assert detail.count("(id ") == 20


def test_delete_works_after_the_link_is_removed_or_the_holder_is_deleted(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    holder = _holder_with_link(client, auth_headers, shop, target)
    assert client.delete(f"/api/menu-items/{target.id}", headers=auth_headers("admin")).status_code == 400
    # a soft-deleted holder does not block
    assert client.delete(f"/api/menu-items/{holder['id']}", headers=auth_headers("admin")).status_code == 200
    assert client.delete(f"/api/menu-items/{target.id}", headers=auth_headers("admin")).status_code == 200
    # unlinking also frees the target
    target2 = shop.item(price=800.0)
    holder2 = _holder_with_link(client, auth_headers, shop, target2)
    assert _put(client, auth_headers, holder2["id"], {"modifiers_config": []}).status_code == 200
    assert client.delete(f"/api/menu-items/{target2.id}", headers=auth_headers("admin")).status_code == 200
    # a holder (which owns links) can be deleted freely
    target3 = shop.item(price=800.0)
    holder3 = _holder_with_link(client, auth_headers, shop, target3)
    assert client.delete(f"/api/menu-items/{holder3['id']}", headers=auth_headers("admin")).status_code == 200


def test_active_order_rule_for_delete_is_unchanged(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    assert _order(client, auth_headers, shop.table, target, []).status_code == 200
    res = client.delete(f"/api/menu-items/{target.id}", headers=auth_headers("admin"))
    assert res.status_code == 400
    assert "active order" in res.json()["detail"]


# —— FR-L3: sync ——


def test_target_price_change_updates_followers_only_and_broadcasts(client, db_session, auth_headers, broadcasts):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    follower = _holder_with_link(client, auth_headers, shop, target)
    overrider = _holder_with_link(client, auth_headers, shop, target, override=250)
    plain = shop.item(modifiers=_groups({"name": "Plain", "price": 123}))
    mixed = _created(client, auth_headers, shop, [_opt("Link", 0, link=target.id), _opt("Own", 77)])
    broadcasts.reset_mock()

    res = _put(client, auth_headers, target.id, {"price": 900})
    assert res.status_code == 200, res.text

    assert _stored_options(db_session, follower["id"])[0]["price"] == 900.0
    assert _stored_options(db_session, overrider["id"])[0]["price"] == 250.0
    assert _stored_options(db_session, plain.id) == [{"name": "Plain", "price": 123}]
    mixed_opts = {o["name"]: o["price"] for o in _stored_options(db_session, mixed["id"])}
    assert mixed_opts == {"Link": 900.0, "Own": 77.0}
    ids = _updated_ids(broadcasts)
    assert sorted(ids) == sorted([target.id, follower["id"], mixed["id"]])
    assert overrider["id"] not in ids and plain.id not in ids


def test_unchanged_price_does_not_touch_followers(client, db_session, auth_headers, broadcasts):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    follower = _holder_with_link(client, auth_headers, shop, target)
    broadcasts.reset_mock()
    assert _put(client, auth_headers, target.id, {"price": 700, "description": "x"}).status_code == 200
    assert _updated_ids(broadcasts) == [target.id]


def test_failed_update_changes_neither_target_nor_followers(client, db_session, auth_headers, broadcasts):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    follower = _holder_with_link(client, auth_headers, shop, target)
    broadcasts.reset_mock()
    res = _put(client, auth_headers, target.id, {"price": 900, "category_id": 987654321})
    assert res.status_code == 404
    db_session.expire_all()
    assert db_session.get(MenuItem, target.id).price == 700.0
    assert _stored_options(db_session, follower["id"])[0]["price"] == 700.0
    assert _updated_ids(broadcasts) == []


# —— FR-L4: ordering (three code paths) ——


def _setup_linked(client, auth_headers, db_session, *, target_price=700.0, holder_price=2000.0, override=None):
    shop = Shop(db_session)
    target = shop.item(name=f"LA-EGG-{_uid()}", price=target_price)
    holder = _holder_with_link(client, auth_headers, shop, target, price=holder_price, override=override)
    return shop, target, holder


@pytest.mark.parametrize("path", ["create", "add", "submit", "submit_new"])
def test_stale_client_price_is_replaced_by_the_live_target_price(client, db_session, auth_headers, path):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    # The target moves WITHOUT the sync (direct DB edit): the stored option price is stale.
    db_session.query(MenuItem).filter(MenuItem.id == target.id).update({MenuItem.price: 950.0})
    db_session.commit()
    stale = _mod("Egg", 1.0, qty=2)  # the waiter's screen says 1, the stored fallback says 700
    first = None
    if path in ("add", "submit"):
        first = _order(client, auth_headers, shop.table, shop.item(price=100.0), [])
        assert first.status_code == 200, first.text
    table = shop.new_table() if path == "submit_new" else shop.table
    res = _order(client, auth_headers, table, holder["id"], [stale], path="submit" if path.startswith("submit") else "create")
    assert res.status_code == 200, res.text
    order_id = res.json()["id"]
    if first is not None:
        assert order_id == first.json()["id"]
    last_line = _line_mods(db_session, order_id)[-1]
    assert last_line == [{"name": "Egg", "price": 950.0, "group": GROUP, "quantity": 2, "linked_menu_item_id": target.id}]
    # (holder 2000 + 2 x 950) for the new line
    new_total = float(db_session.get(Order, order_id).total_amount)
    expected_new_line = 2000.0 + 2 * 950.0
    assert new_total == pytest.approx(expected_new_line + (100.0 if first is not None else 0.0))


def test_override_price_is_used_and_free_override_is_zero(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session, override=300)
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 9999)])
    assert res.json()["total_amount"] == 2300.0
    shop2, _t2, holder2 = _setup_linked(client, auth_headers, db_session, override=0)
    res2 = _order(client, auth_headers, shop2.table, holder2["id"], [_mod("Egg", 9999)])
    assert res2.json()["total_amount"] == 2000.0


def test_target_priced_zero_gives_a_free_addon_without_error(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    assert _put(client, auth_headers, target.id, {"price": 0}).status_code == 200
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 700)])
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 2000.0


def test_deleted_target_falls_back_to_the_stored_price(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    db_session.query(MenuItem).filter(MenuItem.id == target.id).update({MenuItem.is_deleted: True})
    db_session.commit()  # forced: the delete rule makes this impossible through the API
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 1)])
    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] == 2700.0


def test_snapshot_key_only_for_linked_and_client_link_ids_are_ignored(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    other = shop.item(price=5.0)
    holder = _created(client, auth_headers, shop, [_opt("Linked", 0, link=target.id), _opt("Own", 40)], price=1000.0)
    res = _order(client, auth_headers, shop.table, holder["id"], [
        _mod("Linked", 1, linked_menu_item_id=other.id),   # wrong id from the client: replaced
        _mod("Own", 40, linked_menu_item_id=other.id),     # unlinked option: id dropped
        _mod("Not on the menu", 15, linked_menu_item_id=other.id),  # no match: client price, id dropped
    ])
    assert res.status_code == 200, res.text
    mods = _line_mods(db_session, res.json()["id"])[0]
    assert mods == [
        {"name": "Linked", "price": 700.0, "group": GROUP, "quantity": 1, "linked_menu_item_id": target.id},
        {"name": "Own", "price": 40.0, "group": GROUP, "quantity": 1},
        {"name": "Not on the menu", "price": 15.0, "group": GROUP, "quantity": 1},
    ]
    assert res.json()["total_amount"] == 1000.0 + 700.0 + 40.0 + 15.0


def test_wrong_group_means_no_match_and_the_client_price_is_used(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 123, group="Other group")])
    assert res.json()["total_amount"] == 2123.0
    assert "linked_menu_item_id" not in _line_mods(db_session, res.json()["id"])[0][0]


def test_bad_computed_price_is_refused_before_anything_is_saved(client, db_session, auth_headers):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    for bad in (-50000.0, 1e12):
        holder = shop.item(price=1000.0, modifiers=_groups(
            {"name": "Egg", "price": 5, "linked_menu_item_id": target.id, "price_override": bad}
        ))
        try:
            before = db_session.query(Order).count()
            res = _order(client, auth_headers, shop.table, holder, [_mod("Egg", 5)])
            assert res.status_code == 400, res.text
            assert "Egg" in res.text or holder.name in res.text
            assert db_session.query(Order).count() == before
            db_session.refresh(shop.table)
            assert shop.table.status == "available"
        finally:
            # bad data in the shared database would break menu listings of later tests
            db_session.query(MenuItem).filter(MenuItem.id == holder.id).delete()
            db_session.commit()


# —— FR-L5: recorded money never changes ——


def test_target_price_rise_changes_no_recorded_money(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 0, qty=2)])
    order_id = res.json()["id"]
    assert res.json()["total_amount"] == 3400.0
    pay = client.put(
        f"/api/orders/{order_id}/checkout", headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100000.0, "issue_receipt": True},
    )
    assert pay.status_code == 200, pay.text
    db_session.query(Order).filter(Order.id == order_id).update({Order.created_at: datetime(2026, 10, 5, 12, 0, 0)})
    db_session.commit()

    def snapshot():
        details = _details(client, auth_headers, order_id)
        hist = client.get("/api/orders/daily-history?date=2026-10-05", headers=auth_headers("cashier")).json()
        row = next(o for o in hist["orders"] if o["id"] == order_id)
        db_session.expire_all()
        receipts = [json.dumps(j.payload, ensure_ascii=False, sort_keys=True)
                    for j in db_session.query(PrintJob).filter(PrintJob.order_id == order_id).order_by(PrintJob.id)]
        return (
            details["total_amount"], [(i["subtotal"], i["selected_modifiers"]) for i in details["items"]],
            row["total_amount"] if "total_amount" in row else None, [(i["subtotal"], [m["price"] for m in i["selected_modifiers"]]) for i in row["items"]],
            receipts,
        )

    before = snapshot()
    assert _put(client, auth_headers, target.id, {"price": 1500}).status_code == 200
    assert snapshot() == before
    # the history response carries the snapshot key
    hist = client.get("/api/orders/daily-history?date=2026-10-05", headers=auth_headers("cashier")).json()
    row = next(o for o in hist["orders"] if o["id"] == order_id)
    assert row["items"][0]["selected_modifiers"][0]["linked_menu_item_id"] == target.id
    # a new order uses the new price
    shop2 = Shop(db_session)
    again = _order(client, auth_headers, shop2.table, holder["id"], [_mod("Egg", 0, qty=2)])
    assert again.json()["total_amount"] == 2000.0 + 2 * 1500.0


def test_open_order_keeps_old_addon_price_and_cancel_removes_what_was_sold(client, db_session, auth_headers):
    shop, target, holder = _setup_linked(client, auth_headers, db_session)
    res = _order(client, auth_headers, shop.table, holder["id"], [_mod("Egg", 0)])
    order_id = res.json()["id"]
    assert _put(client, auth_headers, target.id, {"price": 1500}).status_code == 200
    details = _details(client, auth_headers, order_id)
    assert details["total_amount"] == 2700.0
    item_id = details["items"][0]["id"]
    cancel = client.put(
        f"/api/orders/{order_id}/items/{item_id}/status", headers=auth_headers("waiter"), json={"status": "cancelled"}
    )
    assert cancel.status_code == 200, cancel.text
    db_session.expire_all()
    assert float(db_session.get(Order, order_id).total_amount) == 0.0


# —— roles ——


@pytest.mark.parametrize("role", ["waiter", "cashier"])
def test_only_admins_can_save_links(client, db_session, auth_headers, role):
    shop = Shop(db_session)
    target = shop.item(price=700.0)
    holder = shop.item()
    res = _put(client, auth_headers, holder.id, {"modifiers_config": _groups(_opt("E", 0, link=target.id))}, role=role)
    assert res.status_code == 403
    assert _stored(db_session, holder.id) == []
    assert client.delete(f"/api/menu-items/{target.id}", headers=auth_headers(role)).status_code == 403
