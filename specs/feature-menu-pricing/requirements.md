# Requirements: Dual Pricing (Dine-in vs Takeaway)

## Purpose
Support optional **takeaway-specific pricing** on menu items (e.g. packaging costs) while preserving deterministic server-side totals.

## Data model

### `MenuItem`
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `price` | `float` | yes | Standard dine-in base price |
| `discount_price` | `float \| null` | no | **Legacy** sale price; migrated to `discount_type`/`discount_value` at runtime when unset |
| `discount_type` | `none` \| `percentage` \| `fixed` | `none` | Per-item discount mode (see `specs/feature-menu-item-discount/`) |
| `discount_value` | `float` | `0.0` | Discount percent or fixed amount |
| `takeaway_price` | `float \| null` | no | Optional takeaway-only base price |

### `OrderItem`
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `is_takeaway` | `bool` | `false` | Per-line flag set at order time |

Snapshots: `unit_price_at_sale` stores the resolved base unit price (before modifiers × qty).

## FR-P1: Price resolution (server authoritative)

For each order line at create/submit time:

```
if line.is_takeaway and menu_item.takeaway_price is not None:
    effective_base = menu_item.takeaway_price
else:
    effective_base = menu_item.price
```

Then apply discount → tax → modifiers (see `specs/feature-menu-item-discount/` and `specs/feature-menu-item-tax/`).

**Fallback:** When `takeaway_price` is `null`, takeaway lines use `menu_item.price` as effective base.

## FR-P2: Menu CRUD
- `POST /api/menu-items/` and `PUT /api/menu-items/{id}` accept optional `takeaway_price`.
- `GET /api/menu-items/` returns `takeaway_price` for waiter/cashier UIs.

## FR-P3: Order endpoints
- `OrderItemCreate` accepts `is_takeaway: bool = false`.
- `POST /api/orders/`, `POST /api/orders/submit` apply FR-P1 per line and persist `OrderItem.is_takeaway`.
- `POST/PUT /api/orders/{id}/checkout` sums stored line `subtotal` values (no repricing at checkout).

## FR-P4: Waiter cart UI
- Each cart line has a **🛍️ Takeaway** checkbox.
- Toggling updates displayed unit/subtotal using `takeaway_price` when defined (FR-P1 fallback otherwise).
- Submit sends `is_takeaway` per line.

## FR-P5: Admin menu UI (`counter.html` / `counter.js`)
- Add/Edit menu item form includes optional **Takeaway Price** input.
- Add/Edit includes **Tax Type** and **Tax Value** (see `specs/feature-menu-item-tax/`).

## Authorization
- Menu write — `ADMIN_PANEL_ROLES`
- Order submit — `POS_ORDER_ROLES`

## Related
- `specs/feature-menu-items/` — soft delete, snapshots
- Order `order_type` (`dine_in` / `takeaway`) — session-level; `is_takeaway` is **line-level** pricing
- Walk-in takeaway (`table_id = NULL`) — `specs/feature-walk-in-takeaway/`
