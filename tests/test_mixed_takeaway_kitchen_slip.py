"""One dine-in table with some lines served at the table and some packed (takeaway).

The kitchen / packer must see which lines are takeaway, line by line, in both
kitchen slip modes (per item / combined), in image mode, on the receipt, in Table
Details and in Order History. The table header itself stays ``Table: N``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from models import (
    Category,
    KitchenPrinterSettings,
    MenuItem,
    Order,
    PrintJob,
    Table,
    Zone,
)
from services.printing.image_renderer import render_ticket_image
from services.printing.settings import seed_kitchen_printer_settings
from services.printing.ticket import build_batch_ticket_text

MARK = "(ပါဆယ်)"


def _mode(db_session, mode: str) -> None:
    seed_kitchen_printer_settings(db_session)
    row = db_session.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    row.kitchen_slip_mode = mode
    row.kitchen_slip_copies = 1
    row.backend = "file"
    row.render_mode = "text"
    db_session.commit()


@pytest.fixture()
def slip_mode(db_session):
    _mode(db_session, "per_item")
    yield lambda mode: _mode(db_session, mode)
    _mode(db_session, "per_item")


@pytest.fixture()
def slip_texts(monkeypatch):
    sent: list[tuple[str, str]] = []

    async def capture(*, route, ticket_text, **kwargs):
        sent.append((route, ticket_text))

    monkeypatch.setattr("services.printing.service._dispatch_payload", capture)
    return sent


def _seed(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"MT-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"MT-T-{suffix}", zone_id=zone.id, status="available")
    food = Category(name=f"MT-F-{suffix}", printer_route="food")
    db_session.add_all([table, food])
    db_session.flush()
    dine = MenuItem(name=f"Dine-{suffix}", price=3500.0, category_id=food.id, is_available=True, modifiers_config=[])
    pack = MenuItem(name=f"Pack-{suffix}", price=2000.0, category_id=food.id, is_available=True, modifiers_config=[])
    pack2 = MenuItem(name=f"Pack2-{suffix}", price=1000.0, category_id=food.id, is_available=True, modifiers_config=[])
    db_session.add_all([dine, pack, pack2])
    db_session.commit()
    for obj in (table, dine, pack, pack2):
        db_session.refresh(obj)
    return table, dine, pack, pack2


def _submit(client, auth_headers, table, lines):
    items = [
        {
            "menu_item_id": item.id,
            "quantity": qty,
            "selected_modifiers": mods,
            "is_takeaway": takeaway,
            **({"note": note} if note else {}),
        }
        for item, qty, takeaway, mods, note in lines
    ]
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={"table_id": table.id, "order_type": "dine_in", "items": items},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _mixed(client, auth_headers, table, dine, pack, pack2):
    return _submit(
        client,
        auth_headers,
        table,
        [
            (dine, 1, False, [], None),
            (pack, 2, True, [{"name": "Egg", "price": 500, "quantity": 1, "group": None}], "no salt"),
            (pack2, 3, True, [], None),
        ],
    )


def _line_of(text: str, name: str) -> str:
    return next(line for line in text.splitlines() if name in line)


# —— kitchen slip, both modes ——


def test_per_item_slips_mark_only_the_takeaway_lines(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("per_item")
    table, dine, pack, pack2 = _seed(db_session)
    _mixed(client, auth_headers, table, dine, pack, pack2)

    by_name = {}
    for _route, text in slip_texts:
        for item in (dine, pack, pack2):
            if item.name in text:
                by_name[item.name] = text
    assert set(by_name) == {dine.name, pack.name, pack2.name}
    assert MARK not in _line_of(by_name[dine.name], dine.name)
    assert _line_of(by_name[pack.name], pack.name).strip() == f"2x {pack.name} {MARK}"
    assert _line_of(by_name[pack2.name], pack2.name).strip() == f"3x {pack2.name} {MARK}"
    # One slip never mixes the table line with a marked line.
    assert MARK not in by_name[dine.name]
    for text in by_name.values():
        assert f"Table: {table.id}" in text or "Table:" in text  # header stays a table header
        assert "TAKEAWAY" not in text


def test_combined_slip_marks_line_by_line_and_header_stays_table(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined")
    table, dine, pack, pack2 = _seed(db_session)
    order = _mixed(client, auth_headers, table, dine, pack, pack2)

    assert len(slip_texts) == 1
    text = slip_texts[0][1]
    assert "Table:" in text and "TAKEAWAY" not in text
    assert f"Order: #{order['id']}" in text
    assert _line_of(text, dine.name).strip() == f"1x {dine.name}"
    assert _line_of(text, pack.name).strip() == f"2x {pack.name} {MARK}"
    assert _line_of(text, pack2.name).strip() == f"3x {pack2.name} {MARK}"
    assert text.count(MARK) == 2
    # Add-on and note sit under the marked parent line; the add-on itself is not marked again.
    block = text.split(f"2x {pack.name} {MARK}", 1)[1].split("-----", 1)[0]
    assert "+ Egg" in block and "Note: no salt" in block and MARK not in block


def test_later_batch_on_same_table_keeps_flags(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined")
    table, dine, pack, pack2 = _seed(db_session)
    first = _submit(client, auth_headers, table, [(dine, 1, False, [], None)])
    slip_texts.clear()
    second = _submit(client, auth_headers, table, [(pack, 1, True, [], None), (dine, 1, False, [], None)])
    assert second["id"] == first["id"]
    text = slip_texts[0][1]
    assert "Batch: #2" in text
    assert _line_of(text, pack.name).strip() == f"1x {pack.name} {MARK}"
    assert MARK not in _line_of(text, dine.name)


# —— image mode ——


def test_image_mode_ticket_differs_when_a_line_is_takeaway():
    def slip(flag: bool) -> str:
        return build_batch_ticket_text(
            route="food",
            table_number="5",
            order_id=1,
            created_at="2026-11-19 15:00",
            items=[
                {"item_name": "Mohinga", "quantity": 1, "is_takeaway": False},
                {"item_name": "Fried Egg", "quantity": 2, "is_takeaway": flag},
            ],
            batch_number=1,
        )

    with_mark, without = slip(True), slip(False)
    assert MARK in with_mark and MARK not in without
    img_with = render_ticket_image(with_mark)
    img_without = render_ticket_image(without)
    assert img_with.size[0] == img_without.size[0] == 576
    assert 0 in img_with.getdata()  # ink was drawn
    # The marker is really rasterised: same width, but the pixels differ.
    assert img_with.tobytes() != img_without.tobytes()


# —— receipt, Table Details, Order History ——


def test_table_details_receipt_and_history_keep_the_flag_per_line(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("per_item")
    table, dine, pack, pack2 = _seed(db_session)
    order = _mixed(client, auth_headers, table, dine, pack, pack2)

    active = client.get(f"/api/orders/active-by-table/{table.id}", headers=auth_headers("waiter"))
    assert active.status_code == 200, active.text
    flags = {i["menu_item_name"]: i["is_takeaway"] for i in active.json()["items"]}
    assert flags == {dine.name: False, pack.name: True, pack2.name: True}

    paid = client.put(
        f"/api/orders/{order['id']}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100000.0, "issue_receipt": True},
    )
    assert paid.status_code == 200, paid.text
    assert {i["menu_item_name"]: i["is_takeaway"] for i in paid.json()["items"]} == flags

    db_session.expire_all()
    receipt = (
        db_session.query(PrintJob)
        .filter(PrintJob.order_id == order["id"], PrintJob.kind == "receipt")
        .first()
    )
    assert receipt is not None
    receipt_flags = {i["name"]: i["is_takeaway"] for i in receipt.payload["items"]}
    assert receipt_flags == flags

    from services.printing.receipt import build_receipt_text

    text = build_receipt_text(**receipt.payload)
    assert _line_of(text, pack.name).strip().startswith(f"2x {pack.name} {MARK}")
    assert MARK not in _line_of(text, dine.name)

    day = db_session.query(Order).filter(Order.id == order["id"]).first().created_at
    hist = client.get(f"/api/orders/daily-history?date={day.strftime('%Y-%m-%d')}", headers=auth_headers("cashier"))
    assert hist.status_code == 200, hist.text
    entry = next(o for o in hist.json()["orders"] if o["id"] == order["id"])
    hist_flags = {}
    for line in entry["items"]:
        hist_flags[line["menu_item_name"]] = bool(line.get("is_takeaway")) or MARK in json.dumps(line, ensure_ascii=False)
    assert hist_flags == flags


# —— a real walk-in takeaway order keeps the big banner ——


def test_walk_in_takeaway_order_slip_has_banner(client, db_session, auth_headers, slip_mode, slip_texts):
    slip_mode("combined")
    _table, dine, _pack, _pack2 = _seed(db_session)
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Ko Aung",
            "items": [{"menu_item_id": dine.id, "quantity": 1, "selected_modifiers": [], "is_takeaway": True}],
        },
    )
    assert res.status_code == 200, res.text
    text = slip_texts[0][1]
    assert "TAKEAWAY" in text and "Ko Aung" in text
