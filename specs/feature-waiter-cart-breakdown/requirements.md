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
Vertical order in `#cart-sidebar` (`waiter.html`):

1. **Cart line items** (`#cart-list`)
2. **Price breakdown** (`#cart-summary`) — Subtotal, Total Discount, Tax, Grand Total
3. **Submit Order** (`#submit-order`) — full-width CTA directly below the breakdown (`#cart-footer`, `flex flex-col gap-4`)
4. **Zone & table selection** (`#table-selection-panel`) — zone tabs, walk-in takeaway, table grid, active takeaways, selected label — at the **bottom** of the sidebar

Rationale: waiters add items from the menu (left), then immediately see totals and submit; table/destination picker stays accessible below without pushing the bill out of view. Submit still requires a valid order context (table or takeaway) via existing JS validation.

## FR-WB2: Active order sidebar
When viewing an occupied table or active takeaway order (`GET /api/orders/{id}/details`), the summary shows the same **4-line** breakdown using **server-calculated** fields:

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
