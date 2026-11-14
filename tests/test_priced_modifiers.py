"""Priced modifiers: qty pricing, kitchen Pattern A, cashier details, menu config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from models import Category, KitchenPrinterSettings, MenuItem, Order, OrderItem
from routers.orders import _selected_modifiers_payload, _selected_modifiers_total
from schemas import SelectedModifier
from services.printing.receipt import build_receipt_text
from services.printing.settings import seed_kitchen_printer_settings
from services.printing.ticket import build_ticket_text


def _seed_mohinga(db_session, *, name: str = "မုန့်ဟင်းခါး", price: float = 2000.0) -> MenuItem:
    cat = Category(name=f"Noodles-{name}-{price}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=name,
        price=price,
        category_id=cat.id,
        modifiers_config=[
            {
                "group": "အကြော်",
                "is_required": False,
                "options": [
                    {"name": "ပဲကြော်", "price": 500},
                    {"name": "အိုးဘဲဥ", "price": 700},
                    {"name": "ငါးဖယ်", "price": 800},
                ],
            }
        ],
        is_available=True,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_selected_modifiers_total_uses_quantity():
    mods = _selected_modifiers_payload(
        [
            {"name": "ပဲကြော်", "price": 500, "quantity": 2, "group": "အကြော်"},
            {"name": "အိုးဘဲဥ", "price": 700, "group": "အကြော်"},  # default qty 1
        ]
    )
    assert mods[0]["quantity"] == 2
    assert mods[1]["quantity"] == 1
    assert _selected_modifiers_total(mods) == 1700.0


def test_selected_modifiers_quantity_below_one_normalized():
    mods = _selected_modifiers_payload(
        [{"name": "ပဲကြော်", "price": 500, "quantity": 0}]
    )
    assert mods == [
        {"name": "ပဲကြော်", "price": 500.0, "group": None, "quantity": 1}
    ]
    assert _selected_modifiers_total(mods) == 500.0


def test_selected_modifier_schema_rejects_quantity_zero():
    try:
        SelectedModifier(name="ပဲကြော်", price=500, quantity=0)
        assert False, "expected validation error"
    except Exception as exc:
        assert "quantity" in str(exc).lower() or "greater" in str(exc).lower()


def test_kitchen_ticket_pattern_a_lists_modifiers():
    text = build_ticket_text(
        route="food",
        item_name="မုန့်ဟင်းခါး",
        quantity=1,
        note="နံနံပင်ရှောင်",
        table_number="A1",
        order_id=42,
        created_at="2026-11-13T12:00:00",
        selected_modifiers=[
            {"name": "ပဲကြော်", "price": 500, "quantity": 2},
            {"name": "အိုးဘဲဥ", "price": 700, "quantity": 1},
        ],
    )
    assert "1x မုန့်ဟင်းခါး" in text
    assert "+ ပဲကြော် x2" in text
    assert "+ အိုးဘဲဥ" in text
    assert "*** Note: နံနံပင်ရှောင် ***" in text
    # Pattern A: parent item before toppings
    assert text.index("1x မုန့်ဟင်းခါး") < text.index("+ ပဲကြော် x2")


def test_kitchen_ticket_without_modifiers_unchanged_shape():
    text = build_ticket_text(
        route="food",
        item_name="မုန့်ဟင်းခါး",
        quantity=2,
        note=None,
        table_number="B2",
        order_id=9,
        created_at="2026-11-13T12:00:00",
        selected_modifiers=[],
    )
    assert "2x မုန့်ဟင်းခါး" in text
    assert "+ " not in text


def test_receipt_text_lists_modifiers():
    text = build_receipt_text(
        order_id=7,
        served_by="waiter1",
        location_label="Table A1",
        items=[
            {
                "name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "subtotal": 2700,
                "selected_modifiers": [
                    {"name": "ပဲကြော်", "price": 500, "quantity": 2},
                ],
            }
        ],
        subtotal=2700,
        discount_amount=0,
        tax_amount=0,
        grand_total=2700,
        payment_method="cash",
        amount_tendered=3000,
        change_amount=300,
    )
    assert "1x မုန့်ဟင်းခါး" in text
    assert "+ ပဲကြော် x2" in text
    assert "1000.00" in text


def test_menu_item_modifiers_config_round_trip(client, db_session, auth_headers):
    cat = Category(name="Noodles-RT")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)

    # Admin UI saves options under one blank group name (no group label required).
    payload = {
        "name": "မုန့်ဟင်းခါး",
        "price": 2000,
        "category_id": cat.id,
        "modifiers_config": [
            {
                "group": "",
                "is_required": False,
                "options": [
                    {"name": "ပဲကြော်", "price": 500},
                    {"name": "အိုးဘဲဥ", "price": 700},
                ],
            }
        ],
    }
    create = client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json=payload,
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["modifiers_config"][0]["group"] == ""
    assert len(body["modifiers_config"][0]["options"]) == 2

    item_id = body["id"]
    update = client.put(
        f"/api/menu-items/{item_id}",
        headers=auth_headers("admin"),
        json={
            **payload,
            "modifiers_config": [
                {
                    "group": "",
                    "is_required": False,
                    "options": [
                        {"name": "ပဲကြော်", "price": 500},
                        {"name": "အိုးဘဲဥ", "price": 700},
                        {"name": "ငါးဖယ်", "price": 800},
                    ],
                }
            ],
        },
    )
    assert update.status_code == 200, update.text
    assert len(update.json()["modifiers_config"][0]["options"]) == 3

    stored = db_session.query(MenuItem).filter(MenuItem.id == item_id).first()
    assert stored is not None
    assert len(stored.modifiers_config[0]["options"]) == 3


def test_order_submit_line_subtotal_includes_modifier_qty(
    client, db_session, auth_headers
):
    item = _seed_mohinga(db_session)
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Test",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {
                            "name": "ပဲကြော်",
                            "price": 500,
                            "quantity": 2,
                            "group": "အကြော်",
                        }
                    ],
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    # 2000 base + 500*2 modifiers = 3000
    assert float(res.json()["total_amount"]) == 3000.0


def test_note_only_does_not_change_price(client, db_session, auth_headers):
    item = _seed_mohinga(db_session, name="မုန့်ဟင်းခါး-note", price=2000)
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "NoteOnly",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [],
                    "special_instructions": "နံနံပင်ရှောင်",
                    "note": "နံနံပင်ရှောင်",
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert float(res.json()["total_amount"]) == 2000.0


def test_two_bowls_different_toppings_cashier_details(
    client, db_session, auth_headers, monkeypatch
):
    """Friend scenario: bowl A pea fritters, bowl B duck egg — totals + composition."""
    item = _seed_mohinga(db_session, name="မုန့်ဟင်းခါး-2bowls", price=2000)
    monkeypatch.setattr(
        "routers.orders.dispatch_kitchen_ticket",
        AsyncMock(return_value=None),
    )
    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "TwoBowls",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "ပဲကြော်", "price": 500, "quantity": 1, "group": "အကြော်"}
                    ],
                },
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "အိုးဘဲဥ", "price": 700, "quantity": 1, "group": "အကြော်"}
                    ],
                },
            ],
        },
    )
    assert res.status_code == 200, res.text
    # 2000+500 + 2000+700 = 5200
    assert float(res.json()["total_amount"]) == 5200.0
    order_id = res.json()["id"]

    details = client.get(
        f"/api/orders/{order_id}/details",
        headers=auth_headers("cashier"),
    )
    assert details.status_code == 200, details.text
    body = details.json()
    lines = body.get("items") or body.get("order_items") or []
    assert len(lines) == 2
    mod_names = {
        tuple(sorted(m["name"] for m in (line.get("selected_modifiers") or [])))
        for line in lines
    }
    assert ("ပဲကြော်",) in mod_names
    assert ("အိုးဘဲဥ",) in mod_names
    assert float(body["total_amount"]) == 5200.0


def test_kitchen_dispatch_receives_selected_modifiers(
    client, db_session, auth_headers, monkeypatch
):
    item = _seed_mohinga(db_session, name="မုန့်ဟင်းခါး-print", price=2000)
    captured: list[dict] = []

    async def _fake_dispatch(route, item_ticket, **kwargs):
        captured.append({"route": route, "ticket": dict(item_ticket)})

    monkeypatch.setattr("routers.orders.dispatch_kitchen_ticket", _fake_dispatch)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Print",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "ပဲကြော်", "price": 500, "quantity": 2, "group": "အကြော်"}
                    ],
                    "special_instructions": "နံနံပင်ရှောင်",
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert len(captured) == 1
    ticket = captured[0]["ticket"]
    assert len(ticket["items"]) == 1
    line = ticket["items"][0]
    assert line["item_name"] == "မုန့်ဟင်းခါး-print"
    assert line["selected_modifiers"][0]["name"] == "ပဲကြော်"
    assert line["selected_modifiers"][0]["quantity"] == 2
    assert line["note"] == "နံနံပင်ရှောင်"


def test_kitchen_batch_one_slip_for_same_route(
    client, db_session, auth_headers, monkeypatch
):
    """Two food lines in one submit → one kitchen dispatch (combined slip)."""
    item = _seed_mohinga(db_session, name="မုန့်ဟင်းခါး-batch", price=2000)
    captured: list[dict] = []

    async def _fake_dispatch(route, item_ticket, **kwargs):
        captured.append({"route": route, "ticket": dict(item_ticket)})

    monkeypatch.setattr("routers.orders.dispatch_kitchen_ticket", _fake_dispatch)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "Batch",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "ပဲကြော်", "price": 500, "quantity": 1}
                    ],
                },
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "အိုးဘဲဥ", "price": 700, "quantity": 1}
                    ],
                },
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert len(captured) == 1
    assert len(captured[0]["ticket"]["items"]) == 2


def test_build_batch_ticket_text_combined_no_prices():
    from services.printing.ticket import build_batch_ticket_text

    text = build_batch_ticket_text(
        route="food",
        table_number="A3",
        order_id=128,
        created_at="2026-11-13T15:10:00",
        batch_number=1,
        items=[
            {
                "item_name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "selected_modifiers": [{"name": "ပဲကြော်", "quantity": 2}],
            },
            {
                "item_name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "note": "နံနံပင်ရှောင်",
                "selected_modifiers": [{"name": "အိုးဘဲဥ", "quantity": 1}],
            },
        ],
    )
    assert "=== KITCHEN TICKET ===" in text
    assert "Batch: #1" in text
    assert "1x မုန့်ဟင်းခါး" in text
    assert "+ ပဲကြော် x2" in text
    assert "+ အိုးဘဲဥ" in text
    assert "နံနံပင်ရှောင်" in text
    assert "1000" not in text
    assert "500" not in text
    assert "Grand Total" not in text


def test_checkout_receipt_file_includes_modifiers(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_RENDER_MODE", "text")
    monkeypatch.setenv("KITCHEN_PRINT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_NAME", "Modifier Cafe")
    monkeypatch.delenv("PRINTER_CASHIER_HOST", raising=False)
    seed_kitchen_printer_settings(db_session)
    settings = (
        db_session.query(KitchenPrinterSettings)
        .filter(KitchenPrinterSettings.id == 1)
        .first()
    )
    settings.backend = "file"
    settings.render_mode = "text"
    db_session.commit()

    item = _seed_mohinga(db_session, name="မုန့်ဟင်းခါး-checkout", price=2000)
    order = Order(
        order_type="takeaway",
        customer_name="Checkout",
        status="open",
        total_amount=3000,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=3000,
            batch_number=1,
            batch_status="pending",
            item_status="pending",
            selected_modifiers=[
                {"name": "ပဲကြော်", "price": 500, "quantity": 2, "group": "အကြော်"}
            ],
            menu_item_name_at_sale=item.name,
            unit_price_at_sale=2000,
            unit_tax_at_sale=0.0,
        )
    )
    db_session.commit()
    db_session.refresh(order)

    res = client.put(
        f"/api/orders/{order.id}/checkout",
        headers=auth_headers("cashier"),
        json={
            "payment_method": "cash",
            "amount_tendered": 3000,
            "discount_type": None,
            "discount_value": 0,
            "issue_receipt": True,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "paid"
    out = Path(tmp_path) / "cashier_printer_output.txt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "ပဲကြော် x2" in text or "+ ပဲကြော် x2" in text
    assert "3000.00" in text or "Grand Total:" in text


def test_other_menu_item_can_use_same_modifier_pattern(
    client, db_session, auth_headers, monkeypatch
):
    """Modifiers are not mohinga-only."""
    monkeypatch.setattr(
        "routers.orders.dispatch_kitchen_ticket",
        AsyncMock(return_value=None),
    )
    cat = Category(name="Snacks")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name="အုန်းနို့ဆွဲ",
        price=1500,
        category_id=cat.id,
        modifiers_config=[
            {
                "group": "အကြော်",
                "is_required": False,
                "options": [{"name": "ပဲကြော်", "price": 500}],
            }
        ],
        is_available=True,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "takeaway",
            "customer_name": "OtherItem",
            "items": [
                {
                    "menu_item_id": item.id,
                    "quantity": 1,
                    "selected_modifiers": [
                        {"name": "ပဲကြော်", "price": 500, "quantity": 3, "group": "အကြော်"}
                    ],
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    # 1500 + 500*3 = 3000
    assert float(res.json()["total_amount"]) == 3000.0
