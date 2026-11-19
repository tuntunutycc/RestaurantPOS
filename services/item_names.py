"""Name shown for a sold order line (specs/feature-snapshot-first-names).

An order line shows the name it was **sold under**. Renaming a menu item later
must not change old bills, history or reports. No imports from models/schemas so
both ``routers.orders`` and ``schemas`` can use it without a circular import.
"""

from __future__ import annotations

DELETED_ITEM_LABEL = "[Deleted Item]"


def order_line_display_name(order_item, deleted_label: str = DELETED_ITEM_LABEL) -> str:
    """Snapshot name first; live menu name only for legacy lines without one."""
    snapshot = (getattr(order_item, "menu_item_name_at_sale", None) or "").strip()
    if snapshot:
        return snapshot
    menu_item = getattr(order_item, "menu_item", None)
    if menu_item is not None and not bool(getattr(menu_item, "is_deleted", False)):
        live = (getattr(menu_item, "name", None) or "").strip()
        if live:
            return live
    return deleted_label
