# Implementation Reference: Per-Item Menu Discount

Records **current** implementation (2026-07-06). See `requirements.md`.

## Backend (`routers/orders.py`)

| Function | Purpose |
|----------|---------|
| `_resolve_unit_base_price()` | `takeaway_price` or `price` (no embedded discount in base) |
| `_menu_item_discount_config()` | Reads `discount_type`/`discount_value`; migrates legacy `discount_price` |
| `_calculate_unit_discount_amount()` | Percentage or fixed discount |
| `_calculate_order_line_pricing()` | Returns `(base, unit_discount, unit_tax, line_subtotal)` |
| `_order_price_breakdown()` | Order-level `breakdown_*` totals |

## Models

- `MenuItem.discount_type`, `discount_value`
- `OrderItem.unit_discount_at_sale`

## API

- Menu CRUD exposes discount fields (`schemas.MenuItemCreate/Update/Response`)
- `OrderDetailsResponse.breakdown_discount_total`
- `OrderItemDetailsResponse.unit_discount_at_sale`

## Frontend

| Module | Behavior |
|--------|----------|
| `waiter.js` | `computeUnitDiscount()`, cart line breakdown, footer Total Discount |
| `counter.js` | Legacy `discount_price` input only (gap vs FR-D5) |

## Tests

- `tests/test_menu_item_discount.py` — 10% discount + 5% tax on discounted price

## Legacy

- `discount_price` on admin form maps to server-side fixed discount migration
