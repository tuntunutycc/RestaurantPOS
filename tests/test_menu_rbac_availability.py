"""RBAC for menu management: admin-only CRUD vs cashier availability patch."""

import uuid

from models import Category, MenuItem


def _create_menu_item(db_session):
    suffix = uuid.uuid4().hex[:8]
    cat = Category(name=f"RBAC-Cat-{suffix}")
    db_session.add(cat)
    db_session.flush()
    item = MenuItem(
        name=f"RBAC-Item-{suffix}",
        price=12.0,
        category_id=cat.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_cashier_cannot_create_menu_item(client, auth_headers, db_session):
    cat = Category(name=f"RBAC-Create-{uuid.uuid4().hex[:6]}")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)

    res = client.post(
        "/api/menu-items/",
        headers=auth_headers("cashier"),
        json={
            "name": "Blocked Item",
            "price": 9.0,
            "category_id": cat.id,
            "is_available": True,
            "modifiers_config": [],
        },
    )
    assert res.status_code == 403, res.text


def test_cashier_can_patch_menu_availability(client, auth_headers, db_session):
    item = _create_menu_item(db_session)

    res = client.patch(
        f"/api/menu-items/{item.id}/availability",
        headers=auth_headers("cashier"),
        json={"is_available": False},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["is_available"] is False
    assert body["id"] == item.id

    restore = client.patch(
        f"/api/menu-items/{item.id}/availability",
        headers=auth_headers("cashier"),
        json={"is_available": True},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["is_available"] is True


def test_cashier_cannot_full_update_menu_item(client, auth_headers, db_session):
    item = _create_menu_item(db_session)

    res = client.put(
        f"/api/menu-items/{item.id}",
        headers=auth_headers("cashier"),
        json={"price": 99.0},
    )
    assert res.status_code == 403, res.text


def test_admin_can_patch_menu_availability(client, auth_headers, db_session):
    item = _create_menu_item(db_session)

    res = client.patch(
        f"/api/menu-items/{item.id}/availability",
        headers=auth_headers("admin"),
        json={"is_available": False},
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_available"] is False


def test_waiter_cannot_patch_menu_availability(client, auth_headers, db_session):
    item = _create_menu_item(db_session)

    res = client.patch(
        f"/api/menu-items/{item.id}/availability",
        headers=auth_headers("waiter"),
        json={"is_available": False},
    )
    assert res.status_code == 403, res.text
