# Implementation Reference: Menu Item Soft Delete

**Status:** Done (2026-07-04)  
**Branch:** `feat/ui-updates`  
**Related:** `specs/feature-category-crud/` — category delete ignores soft-deleted items in active-count check

## API (`routers/menu.py`)

| Method | Path | Behavior |
|--------|------|----------|
| `DELETE` | `/api/menu-items/{item_id}` | Soft delete; blocked if on active order |
| `GET` | `/api/menu-items/` | Excludes `is_deleted=true` |

### Active order check
`_menu_item_in_active_order(db, menu_item_id)`:
- Join `order_items` → `orders`
- Block when `orders.status` NOT IN (`paid`, `cancelled`)
- Ignore lines with `item_status = cancelled`

### Soft delete fields set
- `is_deleted = True`
- `deleted_at = utcnow()`
- `is_available = False`
- WebSocket: `menu_item_deleted` `{ id }`

## Frontend

| Surface | File | Notes |
|---------|------|-------|
| Admin menu list | `counter.js` | `deleteMenuItem()` → `parseApiDetail()`; `window.alert` on `400`; soft-delete confirm copy |
| Waiter menu | `waiter.js` | `fetchMenuItems()` → `GET /api/menu-items/` (server filters `is_deleted=false`) |
| Reports / history | `routers/reports.py`, `routers/orders.py` | `OrderItem` snapshots; soft-deleted items still readable |

## Tests

- `tests/test_menu_item_soft_delete.py` — active order block + success path
- `tests/test_deletion_integrity.py::test_soft_delete_menu_item_preserves_history_and_reports`
