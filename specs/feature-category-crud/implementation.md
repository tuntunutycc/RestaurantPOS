# Implementation Reference: Category Edit & Delete

**Status:** Done (2026-07-04, updated after soft-delete integration)  
**Branch:** `feat/ui-updates`  
**Related:** `specs/feature-menu-items/` (menu item soft delete enables empty-category flow)

## API (`routers/menu.py`)

| Method | Path | Access | Notes |
|--------|------|--------|-------|
| `PUT` | `/api/categories/{category_id}` | `ADMIN_PANEL_ROLES` | Update `name` and/or `printer_route` (pre-existing) |
| `DELETE` | `/api/categories/{category_id}` | `ADMIN_PANEL_ROLES` | Blocked when active menu items exist |

### Delete rule (enforced)
1. Count **active** items only: `MenuItem.category_id` match AND `is_deleted = false`.
2. If any active → `HTTP 400` with blocked message.
3. Soft-deleted, no `order_items` → hard-purge row.
4. Soft-deleted with order history → `category_id` reassigned to `__system_archived__` (hidden from list API).
5. Delete `Category` row; `IntegrityError` → `400` safety net.

**Constants:** `ARCHIVED_CATEGORY_NAME = "__system_archived__"`, `_get_or_create_archived_category()`.

**Schema note:** Order history uses `OrderItem` snapshots; soft-deleted `MenuItem` rows with orders are moved, not destroyed.

## Frontend (`static/counter.js`, `static/counter.html`)

- `renderCategories()` — **Edit** / **Delete** buttons per category row in `#categories-list`.
- Edit → `#category-edit-modal` form → `PUT` with `{ name }` → `loadMenuData()`.
- Delete → `dialogConfirm` → `DELETE` → `dialogAlert` on failure; on success refresh categories + menu items.
- `loadMenuData()` uses `Promise.allSettled` so a menu-items API failure does not mask category list updates.

## Tests

`tests/test_category_crud.py` (5 tests):
- `test_update_category_name` — rename
- `test_delete_category_without_items` — empty category
- `test_delete_category_blocked_when_items_exist` — active item blocks (`400`)
- `test_delete_category_after_soft_deleted_items_only` — only soft-deleted items, no orders → **200**
- `test_delete_category_allowed_when_only_soft_deleted_items_with_order_history` — soft-deleted + paid order → **200**, item moved to archive category

See `validation.md` for merge checklist.
