"""Kitchen LAN printing: route resolution, file backend, submit integrity."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from models import Category, MenuItem, Table, Zone
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
        return PrinterConfig(backend="file", output_dir=str(tmp_path), routes={})

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


def test_admin_kitchen_printer_settings_api(client, auth_headers):
    get_res = client.get("/api/admin/kitchen-printers", headers=auth_headers("admin"))
    assert get_res.status_code == 200, get_res.text
    body = get_res.json()
    assert body["backend"] in ("file", "escpos_network")
    assert len(body["routes"]) == 2

    put_res = client.put(
        "/api/admin/kitchen-printers",
        headers=auth_headers("admin"),
        json={
            "backend": "escpos_network",
            "routes": [
                {"route_key": "drinks", "host": "192.168.1.101", "port": 9100},
                {"route_key": "food", "host": "192.168.1.102", "port": 9100},
            ],
        },
    )
    assert put_res.status_code == 200, put_res.text
    updated = put_res.json()
    assert updated["backend"] == "escpos_network"
    drinks = next(r for r in updated["routes"] if r["route_key"] == "drinks")
    food = next(r for r in updated["routes"] if r["route_key"] == "food")
    assert drinks["host"] == "192.168.1.101"
    assert food["host"] == "192.168.1.102"

    waiter_res = client.get("/api/admin/kitchen-printers", headers=auth_headers("waiter"))
    assert waiter_res.status_code == 403
