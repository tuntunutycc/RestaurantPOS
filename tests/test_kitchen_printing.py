"""Kitchen LAN printing: route resolution, file backend, submit integrity."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image, ImageFont

from models import Category, MenuItem, Table, Zone
from services.printing.ticket import build_escpos_raster_payload
from services.printing.routes import resolve_printer_route


def _seed_table_and_items(db_session, *, drinks_route=None, food_route=None):
    suffix = uuid.uuid4().hex[:8]
    zone = Zone(name=f"P-Zone-{suffix}")
    db_session.add(zone)
    db_session.flush()

    table = Table(name=f"P-Table-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()

    drinks_category = Category(name=f"P-Drinks-{suffix}", printer_route=drinks_route)
    food_category = Category(name=f"P-Food-{suffix}", printer_route=food_route)
    db_session.add_all([drinks_category, food_category])
    db_session.flush()

    drinks_item = MenuItem(
        name=f"လက်ဖက်ရည်-{suffix}",
        price=1500.0,
        category_id=drinks_category.id,
        is_available=True,
        modifiers_config=[],
    )
    food_item = MenuItem(
        name=f"မုန့်ဟင်းခါး-{suffix}",
        price=3500.0,
        category_id=food_category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add_all([drinks_item, food_item])
    db_session.commit()
    db_session.refresh(table)
    db_session.refresh(drinks_item)
    db_session.refresh(food_item)
    return table, drinks_item, food_item


def _submit_items(client, headers, table_id, items):
    return client.post(
        "/api/orders/submit",
        headers=headers,
        json={
            "table_id": table_id,
            "order_type": "dine_in",
            "items": items,
        },
    )


def test_resolve_printer_route_defaults_and_unknown():
    assert resolve_printer_route(None) == "food"
    assert resolve_printer_route("") == "food"
    assert resolve_printer_route("drinks") == "drinks"
    assert resolve_printer_route("food") == "food"
    assert resolve_printer_route("bar") == "food"


def test_category_api_includes_printer_route(client, auth_headers):
    create_res = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": "Tea Bar", "printer_route": "drinks"},
    )
    assert create_res.status_code == 200, create_res.text
    body = create_res.json()
    assert body["printer_route"] == "drinks"

    update_res = client.put(
        f"/api/categories/{body['id']}",
        headers=auth_headers("admin"),
        json={"printer_route": "food"},
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["printer_route"] == "food"


def test_category_invalid_printer_route_returns_422(client, auth_headers):
    res = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": "Invalid Route Cat", "printer_route": "bar"},
    )
    assert res.status_code == 422


def _patch_file_printer_output(monkeypatch, tmp_path):
    from services.printing.config import PrinterConfig

    def _fake_load_printer_config(db=None):
        return PrinterConfig(
            backend="file",
            render_mode="text",
            paper_width_px=576,
            output_dir=str(tmp_path),
            routes={},
        )

    monkeypatch.setattr(
        "services.printing.service.load_printer_config",
        _fake_load_printer_config,
    )


def test_submit_routes_drinks_and_food_file_outputs(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    _patch_file_printer_output(monkeypatch, tmp_path)

    table, drinks_item, food_item = _seed_table_and_items(
        db_session,
        drinks_route="drinks",
        food_route=None,
    )

    res = _submit_items(
        client,
        auth_headers("waiter"),
        table.id,
        [
            {"menu_item_id": drinks_item.id, "quantity": 1, "selected_modifiers": []},
            {"menu_item_id": food_item.id, "quantity": 2, "selected_modifiers": []},
        ],
    )
    assert res.status_code == 200, res.text

    drinks_output = (tmp_path / "drinks_printer_output.txt").read_text(encoding="utf-8")
    food_output = (tmp_path / "food_printer_output.txt").read_text(encoding="utf-8")

    assert drinks_item.name in drinks_output
    assert "Route: drinks" in drinks_output
    assert food_item.name in food_output
    assert "Route: food" in food_output
    assert "2x" in food_output


def test_submit_unknown_category_route_falls_back_to_food_file(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    _patch_file_printer_output(monkeypatch, tmp_path)

    table, drinks_item, _food_item = _seed_table_and_items(db_session, drinks_route="drinks")
    drinks_category = db_session.get(Category, drinks_item.category_id)
    drinks_category.printer_route = "legacy_station"
    db_session.commit()

    res = _submit_items(
        client,
        auth_headers("waiter"),
        table.id,
        [{"menu_item_id": drinks_item.id, "quantity": 1, "selected_modifiers": []}],
    )
    assert res.status_code == 200, res.text

    food_output = (tmp_path / "food_printer_output.txt").read_text(encoding="utf-8")
    assert drinks_item.name in food_output
    assert "Route: food" in food_output


def test_submit_succeeds_when_print_dispatch_raises(
    client, db_session, auth_headers
):
    table, drinks_item, _ = _seed_table_and_items(
        db_session,
        drinks_route="drinks",
    )

    with patch(
        "routers.orders.dispatch_kitchen_ticket",
        new=AsyncMock(side_effect=RuntimeError("printer offline")),
    ):
        res = _submit_items(
            client,
            auth_headers("waiter"),
            table.id,
            [{"menu_item_id": drinks_item.id, "quantity": 1, "selected_modifiers": []}],
        )

    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] > 0


def test_file_backend_image_mode_writes_png(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    from services.printing.config import PrinterConfig

    def _fake_load_printer_config(db=None):
        return PrinterConfig(
            backend="file",
            render_mode="image",
            paper_width_px=384,
            output_dir=str(tmp_path),
            routes={},
        )

    monkeypatch.setattr(
        "services.printing.service.load_printer_config",
        _fake_load_printer_config,
    )

    table, drinks_item, _ = _seed_table_and_items(db_session, drinks_route="drinks")
    res = _submit_items(
        client,
        auth_headers("waiter"),
        table.id,
        [{"menu_item_id": drinks_item.id, "quantity": 1, "selected_modifiers": []}],
    )
    assert res.status_code == 200, res.text

    output_path = tmp_path / "drinks_printer_output.png"
    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.size[0] == 384
        assert image.size[1] > 0


def test_image_renderer_discovers_bundled_myanmar_font(tmp_path, monkeypatch):
    import services.printing.image_renderer as renderer

    font_dir = tmp_path / "assets" / "fonts"
    font_dir.mkdir(parents=True)
    font_path = font_dir / "CustomMyanmar-Regular.ttf"
    font_path.write_bytes(b"placeholder")

    fallback_font = ImageFont.load_default()
    loaded_paths = []

    def _fake_truetype(path, size):
        loaded_paths.append(path)
        return fallback_font

    monkeypatch.setattr(renderer, "BUNDLED_FONT_DIRS", (font_dir,))
    monkeypatch.setattr(renderer, "SYSTEM_MYANMAR_FONT_PATHS", ())
    monkeypatch.setattr(renderer.ImageFont, "truetype", _fake_truetype)

    font = renderer._load_font(None)

    assert font is fallback_font
    assert loaded_paths == [str(font_path)]


def test_image_renderer_routes_latin_text_to_fallback_font():
    import services.printing.image_renderer as renderer

    myanmar_font = object()
    latin_font = object()

    assert renderer._font_for_char("က", myanmar_font, latin_font) is myanmar_font
    assert renderer._font_for_char("A", myanmar_font, latin_font) is latin_font
    assert renderer._font_for_char("1", myanmar_font, latin_font) is latin_font
    assert renderer._font_for_char("-", myanmar_font, latin_font) is latin_font


def test_image_renderer_mixed_script_output_is_non_empty():
    from services.printing.image_renderer import render_ticket_image

    image = render_ticket_image(
        "=== KITCHEN ITEM TICKET ===\n"
        "Table: 2\n"
        "2x လက်ဖက်ရည် - No sugar\n"
        "*** Note: အချိုလျှော့ ***",
        paper_width_px=384,
    )

    assert image.size[0] == 384
    assert image.histogram()[0] > 0


def test_bundled_print_fonts_are_loadable():
    bundled_fonts = [
        "assets/fonts/NotoSansMyanmar-Regular.ttf",
        "assets/fonts/NotoSans-Regular.ttf",
    ]

    for font_path in bundled_fonts:
        font = ImageFont.truetype(font_path, size=28)
        assert font.getname()[0]


def test_submit_succeeds_when_image_renderer_raises(
    client, db_session, auth_headers, tmp_path, monkeypatch
):
    from services.printing.config import PrinterConfig

    def _fake_load_printer_config(db=None):
        return PrinterConfig(
            backend="file",
            render_mode="image",
            paper_width_px=384,
            output_dir=str(tmp_path),
            routes={},
        )

    monkeypatch.setattr(
        "services.printing.service.load_printer_config",
        _fake_load_printer_config,
    )

    def _raise_render_error(*args, **kwargs):
        raise RuntimeError("font renderer failed")

    monkeypatch.setattr(
        "services.printing.service.render_ticket_image",
        _raise_render_error,
    )

    table, drinks_item, _ = _seed_table_and_items(db_session, drinks_route="drinks")
    res = _submit_items(
        client,
        auth_headers("waiter"),
        table.id,
        [{"menu_item_id": drinks_item.id, "quantity": 1, "selected_modifiers": []}],
    )

    assert res.status_code == 200, res.text
    assert res.json()["total_amount"] > 0


def test_escpos_raster_payload_non_empty():
    image = Image.new("1", (384, 32), 255)
    payload = build_escpos_raster_payload(image)
    assert payload.startswith(b"\x1b\x40\x1d\x76\x30\x00")
    assert payload.endswith(b"\n\n\x1d\x56\x00")
    assert len(payload) > 100


def test_admin_kitchen_printer_settings_api(client, auth_headers):
    get_res = client.get("/api/admin/kitchen-printers", headers=auth_headers("admin"))
    assert get_res.status_code == 200, get_res.text
    body = get_res.json()
    assert body["backend"] in ("file", "escpos_network")
    assert len(body["routes"]) == 3

    put_res = client.put(
        "/api/admin/kitchen-printers",
        headers=auth_headers("admin"),
        json={
            "backend": "escpos_network",
            "render_mode": "image",
            "paper_width_px": 384,
            "routes": [
                {"route_key": "drinks", "host": "192.168.1.101", "port": 9100},
                {"route_key": "food", "host": "192.168.1.102", "port": 9100},
                {"route_key": "cashier", "host": "192.168.1.103", "port": 9100},
            ],
        },
    )
    assert put_res.status_code == 200, put_res.text
    updated = put_res.json()
    assert updated["backend"] == "escpos_network"
    assert updated["render_mode"] == "image"
    assert updated["paper_width_px"] == 384
    drinks = next(r for r in updated["routes"] if r["route_key"] == "drinks")
    food = next(r for r in updated["routes"] if r["route_key"] == "food")
    cashier = next(r for r in updated["routes"] if r["route_key"] == "cashier")
    assert drinks["host"] == "192.168.1.101"
    assert food["host"] == "192.168.1.102"
    assert cashier["host"] == "192.168.1.103"

    waiter_res = client.get("/api/admin/kitchen-printers", headers=auth_headers("waiter"))
    assert waiter_res.status_code == 403
