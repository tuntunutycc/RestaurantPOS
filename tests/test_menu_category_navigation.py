"""Menu category navigation contract: menu items expose category_id for client-side filtering."""

import uuid

from models import Category, MenuItem


def test_menu_items_include_category_id(client, db_session, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    category = Category(name=f"Nav-Cat-{suffix}")
    db_session.add(category)
    db_session.flush()
    menu_item = MenuItem(
        name=f"Nav-Item-{suffix}",
        price=1000.0,
        category_id=category.id,
        is_available=True,
        modifiers_config=[],
    )
    db_session.add(menu_item)
    db_session.commit()

    res = client.get("/api/menu-items/", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    rows = res.json()
    match = next((row for row in rows if row["id"] == menu_item.id), None)
    assert match is not None
    assert match["category_id"] == category.id
