# Implementation Reference: Waiter Cart Breakdown

Current implementation (2026-07-06).

## API contract

Primary source: `GET /api/orders/{order_id}/details` → `OrderDetailsResponse`:

- `breakdown_subtotal`, `breakdown_discount_total`, `breakdown_tax_total`, `breakdown_grand_total`
- Per item: `unit_price_at_sale`, `unit_discount_at_sale`, `unit_tax_at_sale`

`GET /api/orders/active-takeaways` returns same breakdown on each order.

List endpoints (`OrderResponseDetail`) do **not** include order-level breakdown fields.

## Frontend (`static/waiter.js`)

| Function | Purpose |
|----------|---------|
| `computeLinePricingBreakdown()` | Client-side line math (mirrors server) |
| `computeCartPriceBreakdown()` | Cart footer aggregates |
| `computeOrderItemsBreakdown()` | Prefers server fields; fallback from line snapshots |
| `renderPriceBreakdownHtml()` | 4-line summary HTML |
| `renderItemBreakdownHtml()` | Per-row `Base \| Disc \| Tax` |
| `renderCart()` | Cart rows with breakdown, final price, and qty `+`/`-` |
| `updateCartQuantity(lineKey, delta)` | Core qty mutate; delete line when qty ≤ 0; calls `renderCart()` |
| `increaseCartItemQty(index)` / `decreaseCartItemQty(index)` | Index into current cart entry order; wraps `updateCartQuantity` |

Cart state: `Map` of lineKey → `{ menu_item, selected_modifiers, special_instructions, unit_price, is_takeaway, quantity }`. Notes are part of the line key and are retained on qty change.

Active-order modal rendering must not wire these qty controls.

## HTML (`static/waiter.html`)

Cart summary: `#cart-subtotal`, `#cart-discount-row`, `#cart-discount-total`, `#cart-tax-total`, `#cart-grand-total`.

Footer layout (`#cart-footer`): price breakdown then `#submit-order`. Floor UI (`#table-selection-panel`) is in `#waiter-pane-floor` (see two-pane layout).

## Tests

- `tests/test_waiter_cart_breakdown.py`
