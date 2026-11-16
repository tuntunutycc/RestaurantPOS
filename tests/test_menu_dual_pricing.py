import uuid

from models import Category, MenuItem, OrderItem, Table, Zone


def _seed_table(db_session):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)
    return table


def _seed_category_and_item(db_session, *, price: float, takeaway_price=None):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"Item-{suffix}",
        price=price,
        takeaway_price=takeaway_price,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()
    db_session.refresh(menu_item)
    return menu_item


def _submit_line(client, auth_headers, menu_item_id, *, is_takeaway: bool, table_id=None, order_type="dine_in"):
    payload = {
        "order_type": order_type,
        "items": [
            {
                "menu_item_id": menu_item_id,
                "quantity": 1,
                "is_takeaway": is_takeaway,
                "selected_modifiers": [],
            }
        ],
    }
    if table_id is not None:
        payload["table_id"] = table_id
    return client.post("/api/orders/submit", headers=auth_headers("waiter"), json=payload)


def test_create_menu_item_with_takeaway_price(client, db_session, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    res = client.post(
        "/api/menu-items/",
        headers=auth_headers("admin"),
        json={
            "name": f"Bento-{suffix}",
            "price": 5000.0,
            "takeaway_price": 5500.0,
            "category_id": category.id,
            "modifiers_config": [],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["price"] == 5000.0
    assert body["takeaway_price"] == 5500.0

    persisted = db_session.query(MenuItem).filter(MenuItem.id == body["id"]).first()
    assert persisted is not None
    assert persisted.takeaway_price == 5500.0


def test_dine_in_order_uses_regular_price(client, db_session, auth_headers):
    table = _seed_table(db_session)
    menu_item = _seed_category_and_item(db_session, price=1000.0, takeaway_price=1200.0)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=False,
        table_id=table.id,
        order_type="dine_in",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is False
    assert float(line.unit_price_at_sale) == 1000.0
    assert float(line.subtotal) == 1000.0


def test_takeaway_line_uses_takeaway_price(client, db_session, auth_headers):
    menu_item = _seed_category_and_item(db_session, price=1000.0, takeaway_price=1200.0)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=True,
        order_type="takeaway",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is True
    assert float(line.unit_price_at_sale) == 1200.0
    assert float(line.subtotal) == 1200.0


def test_takeaway_line_falls_back_to_regular_price_without_takeaway_price(client, db_session, auth_headers):
    menu_item = _seed_category_and_item(db_session, price=800.0, takeaway_price=None)

    res = _submit_line(
        client,
        auth_headers,
        menu_item.id,
        is_takeaway=True,
        order_type="takeaway",
    )
    assert res.status_code == 200, res.text

    line = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == res.json()["id"])
        .first()
    )
    assert line is not None
    assert line.is_takeaway is True
    assert float(line.unit_price_at_sale) == 800.0
    assert float(line.subtotal) == 800.0


def test_menu_item_create_payload_matches_counter_form(client, auth_headers, db_session):
    """Counter admin form sends tax/discount defaults + legacy discount_price."""
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Cat-{suffix}")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    payload = {
        "name": f"TaxItem-{suffix}",
        "price": 3000.0,
        "discount_price": 2500.0,
        "discount_type": "none",
        "discount_value": 0.0,
        "takeaway_price": None,
        "tax_type": "percentage",
        "tax_value": 5.0,
        "category_id": category.id,
        "description": "Test item",
        "image_url": None,
        "is_available": True,
        "is_promoted": False,
        "modifiers_config": [],
    }
    res = client.post("/api/menu-items/", headers=auth_headers("admin"), json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tax_type"] == "percentage"
    assert body["tax_value"] == 5.0
    assert body["discount_price"] == 2500.0
    assert body["discount_type"] == "none"
    assert body["discount_value"] == 0.0

    persisted = db_session.query(MenuItem).filter(MenuItem.id == body["id"]).first()
    assert persisted is not None
    assert persisted.tax_type == "percentage"
    assert float(persisted.tax_value) == 5.0
    assert persisted.discount_type == "none"


def test_kitchen_batch_marks_takeaway_lines_only():
    from services.printing.ticket import build_batch_ticket_text

    text = build_batch_ticket_text(
        route="food",
        table_number="F1",
        order_id=77,
        created_at="2026-11-14T20:00:00",
        batch_number=2,
        order_type="dine_in",
        items=[
            {
                "item_name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "is_takeaway": False,
                "selected_modifiers": [],
            },
            {
                "item_name": "မုန့်ဟင်းခါး",
                "quantity": 2,
                "is_takeaway": True,
                "note": "အိမ်ယူ",
                "selected_modifiers": [{"name": "ပဲကြော်", "quantity": 1}],
            },
        ],
    )
    assert "Table: F1" in text
    assert "1x မုန့်ဟင်းခါး" in text
    assert "2x မုန့်ဟင်းခါး (ပါဆယ်)" in text
    assert text.count("(ပါဆယ်)") == 1
    assert "+ ပဲကြော်" in text
    assert "အိမ်ယူ" in text
    # Submenu stays under the parent line that already carries (ပါဆယ်).
    takeaway_block = text.split("2x မုန့်ဟင်းခါး (ပါဆယ်)", 1)[1]
    assert takeaway_block.index("+ ပဲကြော်") < takeaway_block.index("အိမ်ယူ")
    assert "1200" not in text


def test_receipt_marks_takeaway_lines():
    from services.printing.receipt import build_receipt_text

    text = build_receipt_text(
        order_id=77,
        served_by="waiter1",
        location_label="F1",
        items=[
            {
                "name": "မုန့်ဟင်းခါး",
                "quantity": 1,
                "subtotal": 1000.0,
                "is_takeaway": False,
                "selected_modifiers": [],
            },
            {
                "name": "မုန့်ဟင်းခါး",
                "quantity": 2,
                "subtotal": 2400.0,
                "is_takeaway": True,
                "selected_modifiers": [{"name": "ပဲကြော်", "quantity": 1, "price": 500}],
            },
        ],
        subtotal=3400.0,
        discount_amount=0.0,
        tax_amount=0.0,
        grand_total=3400.0,
        payment_method="cash",
        amount_tendered=4000.0,
        change_amount=600.0,
        created_at="2026-11-14 20:05",
        cashier_name="cashier1",
    )
    assert "Location: F1" in text
    assert "1x မုန့်ဟင်းခါး\n" in text
    assert "2x မုန့်ဟင်းခါး (ပါဆယ်)" in text
    assert "+ ပဲကြော်" in text
    assert "2400.00" in text
    takeaway_block = text.split("2x မုန့်ဟင်းခါး (ပါဆယ်)", 1)[1]
    assert takeaway_block.index("+ ပဲကြော်") < takeaway_block.index("2400.00")


def test_dine_in_submit_passes_is_takeaway_to_kitchen_dispatch(
    client, db_session, auth_headers, monkeypatch
):
    """Table order with Takeaway tick must send is_takeaway into kitchen print payload."""
    from models import Table, Zone

    menu_item = _seed_category_and_item(db_session, price=1000.0, takeaway_price=1200.0)
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.commit()
    db_session.refresh(table)

    captured = []

    async def _capture(route, ticket, **kwargs):
        captured.append({"route": route, "ticket": ticket, "kwargs": kwargs})

    monkeypatch.setattr("services.printing.print_jobs.dispatch_kitchen_ticket", _capture)

    res = client.post(
        "/api/orders/submit",
        headers=auth_headers("waiter"),
        json={
            "order_type": "dine_in",
            "table_id": table.id,
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 1,
                    "is_takeaway": False,
                    "selected_modifiers": [],
                },
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                    "is_takeaway": True,
                    "selected_modifiers": [],
                },
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert len(captured) == 2  # one kitchen slip per line
    flags = sorted(bool(t["ticket"].get("is_takeaway")) for t in captured)
    assert flags == [False, True]
    dine = next(t["ticket"] for t in captured if not t["ticket"].get("is_takeaway"))
    take = next(t["ticket"] for t in captured if t["ticket"].get("is_takeaway"))
    assert dine["quantity"] == 1
    assert take["quantity"] == 2
