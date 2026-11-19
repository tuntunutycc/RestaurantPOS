"""Admin-editable receipt text (shop name, address, phone, thank-you, footer note).

Spec: specs/feature-receipt-text
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from models import Category, MenuItem, Order, PrintJob, ReceiptSettings, Table, Zone
from services.printing.receipt import build_receipt_text
from services.printing.service import build_printer_test_ticket_text, dispatch_cashier_receipt

URL = "/api/admin/receipt-settings"
BLANK = {"shop_name": "", "address": "", "phone": "", "thank_you": "", "footer_note": ""}

# The receipt as printed before this feature existed (SHOP_NAME unset).
GOLDEN_DEFAULT = (
    "=================================\n  My Restaurant\n=================================\n"
    "Voucher: 20261119-0001\nLocation: T3\nServed by: waiter1\nCashier: cashier1\n"
    "Time: 2026-11-19 12:00\n---------------------------------\n2x Mohinga\n    + Egg  500.00\n"
    "    *** Note: no chilli ***\n    4000.00\n1x Tea (ပါဆယ်)\n    1500.00\n"
    "---------------------------------\nSubtotal:     5500.00\nDiscount:    -0.00\n"
    "Tax:          0.00\nGrand Total:  5500.00\nPayment:      Cash\nTendered:     6000.00\n"
    "Change Due:   500.00\n---------------------------------\nThank you!\n[ --- CUT RECEIPT --- ]\n"
)


def _receipt_kwargs() -> dict:
    return dict(
        order_id=7, served_by="waiter1", cashier_name="cashier1", location_label="T3",
        items=[
            {"name": "Mohinga", "quantity": 2, "subtotal": 4000.0,
             "selected_modifiers": [{"name": "Egg", "price": 500, "quantity": 1}], "note": "no chilli"},
            {"name": "Tea", "quantity": 1, "subtotal": 1500.0, "is_takeaway": True},
        ],
        subtotal=5500.0, discount_amount=0.0, tax_amount=0.0, grand_total=5500.0,
        payment_method="cash", amount_tendered=6000.0, change_amount=500.0,
        created_at="2026-11-19 12:00", voucher_no="20261119-0001",
    )


@pytest.fixture()
def clean_settings(db_session, monkeypatch):
    """Blank settings before and after (the database is shared between tests)."""
    monkeypatch.delenv("SHOP_NAME", raising=False)

    def wipe():
        db_session.query(ReceiptSettings).delete()
        db_session.commit()

    wipe()
    yield wipe
    wipe()


def _put(client, auth_headers, role="admin", **fields):
    return client.put(URL, headers=auth_headers(role), json=fields)


def _lines(text: str) -> list[str]:
    return text.split("\n")


# —— FR-R5: nothing set -> exactly today's receipt ——


def test_default_receipt_is_byte_identical(client, db_session, auth_headers, clean_settings):
    assert build_receipt_text(**_receipt_kwargs()) == GOLDEN_DEFAULT


def test_dispatch_with_blank_settings_prints_the_old_receipt(db_session, clean_settings, monkeypatch):
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    assert sent == [GOLDEN_DEFAULT]


def test_env_shop_name_is_still_the_fallback(db_session, clean_settings, monkeypatch):
    monkeypatch.setenv("SHOP_NAME", "From Env")
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    assert _lines(sent[0])[1] == "  From Env"


# —— FR-R2: contract, validation, roles ——


def test_get_returns_blank_strings_when_never_set(client, auth_headers, clean_settings):
    res = client.get(URL, headers=auth_headers("admin"))
    assert res.status_code == 200, res.text
    assert res.json() == BLANK


def test_put_then_get_round_trips_myanmar_text(client, auth_headers, clean_settings):
    body = {
        "shop_name": "ရွှေမုန့်ဟင်းခါး",
        "address": "အမှတ် ၁၂၊ ဗိုလ်ချုပ်လမ်း\nရန်ကုန်",
        "phone": "09-123456789",
        "thank_you": "ကျေးဇူးတင်ပါတယ်",
        "footer_note": "WiFi: shwe1234",
    }
    res = _put(client, auth_headers, **body)
    assert res.status_code == 200, res.text
    assert res.json() == body
    assert client.get(URL, headers=auth_headers("root")).json() == body


def test_omitted_field_keeps_stored_value(client, auth_headers, clean_settings):
    _put(client, auth_headers, shop_name="Shop A", phone="111")
    res = _put(client, auth_headers, phone="222")
    assert res.status_code == 200
    assert res.json()["shop_name"] == "Shop A" and res.json()["phone"] == "222"


def test_limits_32_characters_and_3_lines(client, auth_headers, clean_settings):
    ok = _put(client, auth_headers, shop_name="a" * 32, address="b" * 32 + "\n" + "c" * 32 + "\nd")
    assert ok.status_code == 200, ok.text
    for field, value in (
        ("shop_name", "a" * 33),
        ("phone", "1" * 33),
        ("thank_you", "t" * 33),
        ("address", "x\ny\nz\nw"),
        ("footer_note", "x\ny\nz\nw"),
        ("address", "ok\n" + "y" * 33),
        ("shop_name", "two\nlines"),
        ("phone", "two\nlines"),
        ("thank_you", "two\nlines"),
    ):
        res = _put(client, auth_headers, **{field: value})
        assert res.status_code == 422, (field, value, res.text)


def test_myanmar_characters_are_counted_as_characters_not_bytes(client, auth_headers, clean_settings):
    value = "က" * 32  # 96 bytes in UTF-8
    assert _put(client, auth_headers, thank_you=value).status_code == 200
    assert _put(client, auth_headers, thank_you=value + "က").status_code == 422


def test_control_characters_and_blank_lines_are_cleaned(client, auth_headers, clean_settings):
    res = _put(
        client, auth_headers,
        shop_name="  My\x00 Shop\x07 ",
        address="\n  line one \r\n\n\t line two\x1b \n\n",
        thank_you="\tThanks\x7f!",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["shop_name"] == "My Shop"
    assert body["address"] == "line one\nline two"
    assert body["thank_you"] == "Thanks!"


def test_roles(client, auth_headers, clean_settings):
    for role in ("admin", "root"):
        assert client.get(URL, headers=auth_headers(role)).status_code == 200
        assert _put(client, auth_headers, role, phone="1").status_code == 200
    for role in ("cashier", "waiter"):
        assert client.get(URL, headers=auth_headers(role)).status_code == 403
        assert _put(client, auth_headers, role, phone="1").status_code == 403
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"phone": "1"}).status_code == 401


# —— FR-R3: layout ——


def test_layout_header_and_footer(client, db_session, auth_headers, clean_settings, monkeypatch):
    _put(
        client, auth_headers,
        shop_name="Shwe Shop", address="No 1, Main Rd\nYangon", phone="09-111",
        thank_you="Thanks, come again", footer_note="WiFi: abc\nFollow us",
    )
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    lines = _lines(sent[0])
    rule = "=" * 33
    assert lines[:7] == [rule, "  Shwe Shop", "No 1, Main Rd", "Yangon", "09-111", rule, "Voucher: 20261119-0001"]
    assert lines[-6:] == [
        "---------------------------------", "Thanks, come again", "WiFi: abc", "Follow us",
        "[ --- CUT RECEIPT --- ]", "",
    ]
    assert "Thank you!" not in sent[0]


def test_blank_fields_leave_no_empty_line(client, db_session, auth_headers, clean_settings, monkeypatch):
    _put(client, auth_headers, shop_name="Only Name")
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    lines = _lines(sent[0])
    assert lines[:4] == ["=" * 33, "  Only Name", "=" * 33, "Voucher: 20261119-0001"]
    assert lines[-4:] == ["---------------------------------", "Thank you!", "[ --- CUT RECEIPT --- ]", ""]


def test_money_and_item_lines_are_identical_with_custom_text(client, db_session, auth_headers, clean_settings, monkeypatch):
    _put(client, auth_headers, shop_name="X", address="A", phone="P", thank_you="T", footer_note="F")
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    body_custom = sent[0].split("Voucher:", 1)[1].split("Subtotal:", 1)[0]
    body_default = GOLDEN_DEFAULT.split("Voucher:", 1)[1].split("Subtotal:", 1)[0]
    assert body_custom == body_default
    money_custom = sent[0].split("Subtotal:", 1)[1].split("---", 1)[0]
    money_default = GOLDEN_DEFAULT.split("Subtotal:", 1)[1].split("---", 1)[0]
    assert money_custom == money_default


# —— later checkouts and re-prints use the current text ——


def _seed_open_order(db_session):
    suffix = uuid.uuid4().hex[:6]
    zone = Zone(name=f"RT-Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"RT-T-{suffix}", zone_id=zone.id, status="available")
    category = Category(name=f"RT-C-{suffix}")
    db_session.add_all([table, category])
    db_session.flush()
    item = MenuItem(name=f"RT-I-{suffix}", price=1000.0, category_id=category.id, is_available=True, modifiers_config=[])
    db_session.add(item)
    db_session.commit()
    return table, item


def test_checkout_receipt_and_reprint_use_the_current_text(client, db_session, auth_headers, clean_settings, monkeypatch):
    table, item = _seed_open_order(db_session)
    created = client.post(
        "/api/orders/",
        headers=auth_headers("waiter"),
        json={"table_id": table.id, "order_type": "dine_in",
              "items": [{"menu_item_id": item.id, "quantity": 1, "selected_modifiers": []}]},
    )
    assert created.status_code in (200, 201), created.text
    order_id = created.json()["id"]
    paid = client.put(
        f"/api/orders/{order_id}/checkout",
        headers=auth_headers("cashier"),
        json={"payment_method": "cash", "amount_tendered": 100000.0, "issue_receipt": True},
    )
    assert paid.status_code == 200, paid.text
    db_session.expire_all()
    job = db_session.query(PrintJob).filter(PrintJob.order_id == order_id, PrintJob.kind == "receipt").first()
    assert job is not None

    # The owner edits the texts after the sale; a re-print shows the new ones.
    _put(client, auth_headers, shop_name="Renamed Shop", thank_you="See you!")
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**job.payload, db=db_session))
    assert "  Renamed Shop" in sent[0] and "See you!" in sent[0]
    assert "Thank you!" not in sent[0]


# —— FR-R3 / D5: test-print slip ——


def test_test_print_slip_uses_the_configured_shop_name(client, db_session, auth_headers, clean_settings):
    _put(client, auth_headers, shop_name="Test Shop")
    text = build_printer_test_ticket_text(printer_name="P1", role="cashier", db=db_session)
    assert "  Test Shop" in text and "Printer: P1" in text
    clean_settings()
    assert "  My Restaurant" in build_printer_test_ticket_text(printer_name="P1", role="cashier", db=db_session)


# —— loading must never break printing ——


def test_unreadable_settings_fall_back_to_the_old_receipt(db_session, clean_settings, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("db is down")

    monkeypatch.setattr("services.printing.settings._read_receipt_row", boom)
    sent = _capture(monkeypatch)
    asyncio.run(dispatch_cashier_receipt(**_receipt_kwargs(), db=db_session))
    assert sent == [GOLDEN_DEFAULT]


def _capture(monkeypatch) -> list[str]:
    sent: list[str] = []

    async def capture(*, route, ticket_text, **_kwargs):
        sent.append(ticket_text)

    monkeypatch.setattr("services.printing.service._dispatch_payload", capture)
    return sent
