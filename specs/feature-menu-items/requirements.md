# Requirements: Menu Item Soft Delete

## Purpose
Allow admin-panel users to remove menu items from active ordering without destroying sales history or order records.

## Schema (existing)
`MenuItem` columns:
- `is_deleted` boolean default `false`
- `deleted_at` datetime nullable
- `is_available` set `false` on soft delete

`OrderItem` stores snapshots: `menu_item_name_at_sale`, `unit_price_at_sale`, `category_name_at_sale`.

## Related: dual pricing
See `specs/feature-menu-pricing/requirements.md` for optional `MenuItem.takeaway_price` and per-line `OrderItem.is_takeaway`.

## FR-1: Soft delete API
- `DELETE /api/menu-items/{id}` sets `is_deleted=true`, `deleted_at=now`, `is_available=false`.
- **No hard delete** of `menu_items` rows when order history exists.

## FR-2: Active order guard (resolved)
Before soft delete, block if the item appears on any **non-finalized** order line:
- Order `status` NOT IN (`paid`, `cancelled`)
- Order line `item_status` != `cancelled`

If blocked → **`400`** with:
> Cannot delete menu item. It is currently part of an active order.

## FR-3: List filtering
- `GET /api/menu-items/` returns only `is_deleted=false` (waiter/cashier/admin ordering UIs).

## FR-4: History & reports
- Order details and sales reports use `OrderItem` snapshots and/or outer-join `MenuItem`; soft-deleted items remain readable in historical data.

## FR-5: Counter UI
- Delete confirms soft removal (not hard delete).
- On `400` active-order error → `window.alert` + dialog with server `detail`.

## FR-6: Relationship to category delete
- Category `DELETE` counts only `is_deleted=false` menu items when checking if a category is empty.
- After all items in a category are soft-deleted, category deletion must be allowed (see `specs/feature-category-crud/requirements.md` FR-2).

## Authorization
- `DELETE /api/menu-items/{id}` — `ADMIN_PANEL_ROLES` (`root`, `admin`).
