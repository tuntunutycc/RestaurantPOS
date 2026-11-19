"""GET /api/orders/tables: one canonical order per table, never a 500.

Bug fixed: an open takeaway order (no table) next to an open table order made the
endpoint answer 500 (sorting None against an int). Takeaways are not tables; they are
listed by GET /api/orders/active-takeaways.
"""

from __future__ import annotations

import uuid

from models import Category, MenuItem, Order, OrderItem, Table, Zone


def _table(db_session):
    suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"OT-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"OT-T-{suffix}", zone_id=zone.id, status="available")
    category = Category(name=f"OT-C-{suffix}")
    db_session.add_all([table, category])
    db_session.flush()
    item = MenuItem(
        name=f"OT-I-{suffix}", price=1000.0, category_id=category.id,
        is_available=True, modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    return table, item


def _order(db_session, item, *, table=None, status="open", order_type="dine_in"):
    order = Order(
        table_id=table.id if table else None,
        order_type=order_type,
        status=status,
        total_amount=1000.0,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderItem(
        order_id=order.id, menu_item_id=item.id, quantity=1, subtotal=1000.0,
        batch_number=1, batch_status="pending", item_status="pending",
        selected_modifiers=[], menu_item_name_at_sale=item.name,
    ))
    db_session.commit()
    return order


def _get(client, auth_headers, role="cashier"):
    res = client.get("/api/orders/tables", headers=auth_headers(role))
    assert res.status_code == 200, res.text
    return res.json()


def test_takeaway_open_next_to_table_order_does_not_break_the_endpoint(client, db_session, auth_headers):
    table, item = _table(db_session)
    dine = _order(db_session, item, table=table)
    take = _order(db_session, item, table=None, order_type="takeaway", status="open")

    body = _get(client, auth_headers)

    ids = [o["id"] for o in body]
    assert dine.id in ids
    assert take.id not in ids  # takeaways are not tables
    assert all(o["table_id"] is not None for o in body)


def test_several_open_takeaways_alone_return_200_and_no_rows_from_them(client, db_session, auth_headers):
    _table_unused, item = _table(db_session)
    t1 = _order(db_session, item, table=None, order_type="takeaway", status="open")
    t2 = _order(db_session, item, table=None, order_type="takeaway", status="pending")

    body = _get(client, auth_headers)

    ids = {o["id"] for o in body}
    assert t1.id not in ids and t2.id not in ids


def test_one_row_per_table_sorted_by_table_and_canonical_order_kept(client, db_session, auth_headers):
    table, item = _table(db_session)
    pending = _order(db_session, item, table=table, status="pending")
    live = _order(db_session, item, table=table, status="open")

    body = _get(client, auth_headers)

    rows = [o for o in body if o["table_id"] == table.id]
    assert len(rows) == 1
    assert rows[0]["id"] == live.id  # open tab wins over a pending one
    assert pending.id not in {o["id"] for o in body if o["table_id"] == table.id}
    keys = [o["table_id"] for o in body]
    assert keys == sorted(keys)


def test_response_shape_and_roles(client, db_session, auth_headers):
    table, item = _table(db_session)
    order = _order(db_session, item, table=table)

    for role in ("admin", "cashier", "waiter"):
        body = _get(client, auth_headers, role)
        row = next(o for o in body if o["id"] == order.id)
        assert {"id", "table_id", "status", "total_amount", "items"} <= set(row)
        assert row["items"][0]["menu_item_name"] == item.name

    res = client.get("/api/orders/tables")
    assert res.status_code in (401, 403)
