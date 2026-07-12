# Implementation: Per-Item Tax

## Server (`routers/orders.py`)
- `_calculate_order_line_pricing()`: `discounted_price = base - unit_discount`, then `unit_tax` on **discounted_price**, then `subtotal = (discounted_price + unit_tax + modifiers) × qty`.
- Checkout sets `order.tax_amount` to sum of `unit_tax_at_sale × quantity` for non-cancelled lines.

## Admin UI
- `static/counter.html` / `counter.js`: `#item-tax-type`, `#item-tax-value` on menu create/edit.
- Discount **type/value** admin UI remains legacy (`discount_price` / create forces `discount_type: 'none'`) — see `feature-menu-item-discount` FR-D5.

## Explicitly not implemented
- **No “No Receipt” / tax-exemption toggle** at checkout (no model field, API, or UI). Official-receipt exemption is out of scope until a dedicated feature spec exists.

## Tests
- `tests/test_menu_item_tax.py`, `tests/test_menu_item_discount.py` (tax-after-discount cases)
