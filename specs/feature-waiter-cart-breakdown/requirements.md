# Requirements: Waiter Cart Price Breakdown

## Purpose
Waiters must quote the exact bill (base, tax, total) to customers before cashier checkout.

## FR-WB1: Cart footer (unsubmitted lines)
When the cart has items, show a **4-line breakdown** (not a single total):

| Line | Formula |
|------|---------|
| **Subtotal** | Σ `(effective_base + modifier_charges) × qty` per line (pre-discount) |
| **Total Discount** | Σ `unit_discount × qty` per line (shown as negative, e.g. red/green) |
| **Tax** | Σ `unit_tax × qty` per line (tax on discounted price) |
| **Grand Total** | Subtotal − Total Discount + Tax |

Each cart row shows an item-level breakdown when discount or tax applies: `Base | Disc | Tax` and the line final price.

Updates **in real time** when quantity changes or the 🛍️ Takeaway checkbox toggles (base/tax may change).

## FR-WB1b: Cart sidebar layout (cart-first)
Vertical order in the **left pane** cart block (`#cart-sidebar` in `waiter.html`):

1. **Cart line items** (`#cart-list`)
2. **Price breakdown** (`#cart-summary`) — Subtotal, Total Discount, Tax, Grand Total
3. **Submit Order** (`#submit-order`) — full-width CTA directly below the breakdown (`#cart-footer`)

Zone / table / takeaway selection lives in the **right floor pane** (`#waiter-pane-floor`). See `specs/feature-waiter-two-pane-layout/`.

Rationale: waiters add items and review totals next to the menu; table destination is chosen on the floor pane. Occupied-order details open in a modal and do not replace the cart.

## FR-WB2: Active order modal
When viewing an occupied table or active takeaway order (`GET /api/orders/{id}/details`) in `#active-order-modal`, the summary shows the same **4-line** breakdown using **server-calculated** fields:

| Response field | Meaning |
|----------------|---------|
| `breakdown_subtotal` | Sum of `(unit_price_at_sale + modifiers) × quantity` |
| `breakdown_discount_total` | Sum of `unit_discount_at_sale × quantity` |
| `breakdown_tax_total` | Sum of `unit_tax_at_sale × quantity` |
| `breakdown_grand_total` | Sum of non-cancelled line `subtotal` values |

## FR-WB3: Consistency
Cart client math must use the same rules as `routers/orders.py` `_calculate_order_line_pricing()` (see `specs/feature-menu-item-tax/`).

## Related
- `specs/feature-menu-item-tax/` — per-item tax
- `specs/feature-menu-pricing/` — dine-in vs takeaway base
