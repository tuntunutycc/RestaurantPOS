"""Category edit/delete API tests."""

import uuid

from models import Category, MenuItem

CATEGORY_DELETE_BLOCKED_MSG = (
    "Cannot delete category. Please delete all menu items under this category first."
)


def test_update_category_name(client, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    create = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": f"Cat-{suffix}", "printer_route": "food"},
    )
    assert create.status_code == 200, create.text
    category_id = create.json()["id"]

    update = client.put(
        f"/api/categories/{category_id}",
        headers=auth_headers("admin"),
        json={"name": f"Renamed-{suffix}"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == f"Renamed-{suffix}"


def test_delete_category_without_items(client, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    create = client.post(
        "/api/categories/",
        headers=auth_headers("admin"),
        json={"name": f"Empty-{suffix}"},
    )
    assert create.status_code == 200, create.text
    category_id = create.json()["id"]

    delete = client.delete(
        f"/api/categories/{category_id}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 200, delete.text
    assert delete.json() == {"deleted": True, "category_id": category_id}

    listed = client.get("/api/categories/", headers=auth_headers("admin"))
    assert listed.status_code == 200
    assert not any(c["id"] == category_id for c in listed.json())


def test_delete_category_blocked_when_items_exist(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Blocked-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"Item-{suffix}",
        price=5.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()

    delete = client.delete(
        f"/api/categories/{category.id}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 400, delete.text
    assert delete.json()["detail"] == CATEGORY_DELETE_BLOCKED_MSG


def test_delete_category_after_soft_deleted_items_only(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"SoftOnly-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    item = MenuItem(
        name=f"Gone-{suffix}",
        price=3.0,
        category_id=category.id,
        is_available=True,
        is_deleted=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.commit()

    delete = client.delete(
        f"/api/categories/{category.id}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 200, delete.text
    assert delete.json()["deleted"] is True


def test_delete_category_allowed_when_only_soft_deleted_items_with_order_history(
    client, auth_headers, db_session
):
    from models import Order, OrderItem, Table, Zone
    from routers.menu import ARCHIVED_CATEGORY_NAME

    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"History-{suffix}", printer_route="food")
    db_session.add(category)
    db_session.flush()
    zone = Zone(name=f"Z-{suffix}")
    db_session.add(zone)
    db_session.flush()
    table = Table(name=f"T-{suffix}", zone_id=zone.id, status="available")
    db_session.add(table)
    db_session.flush()
    item = MenuItem(
        name=f"Hist-{suffix}",
        price=8.0,
        category_id=category.id,
        is_available=False,
        is_deleted=True,
        modifiers_config=[],
    )
    db_session.add(item)
    db_session.flush()
    order = Order(table_id=table.id, order_type="dine_in", status="paid", total_amount=8.0)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            quantity=1,
            subtotal=8.0,
            batch_number=1,
            batch_status="pending",
            item_status="served",
            selected_modifiers=[],
        )
    )
    db_session.commit()
    category_id = category.id
    item_id = item.id

    delete = client.delete(
        f"/api/categories/{category_id}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 200, delete.text

    db_session.expire_all()
    archived = db_session.query(Category).filter(Category.name == ARCHIVED_CATEGORY_NAME).first()
    assert archived is not None
    moved = db_session.query(MenuItem).filter(MenuItem.id == item_id).first()
    assert moved is not None
    assert moved.category_id == archived.id

    listed = client.get("/api/categories/", headers=auth_headers("admin"))
    assert not any(c["id"] == category_id for c in listed.json())
