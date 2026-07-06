# Requirements: Waiter Cart Price Breakdown

## Purpose
Waiters must quote the exact bill (base, tax, total) to customers before cashier checkout.

## FR-WB1: Cart footer (unsubmitted lines)
When the cart has items, show a **3-line breakdown** (not a single total):

| Line | Formula |
|------|---------|
| **Subtotal** | Σ `(unit_base + modifier_charges) × qty` per line (pre-tax) |
| **Tax** | Σ `unit_tax × qty` per line (`tax_type` / `tax_value` on active base) |
| **Grand Total** | Subtotal + Tax |

Updates **in real time** when quantity changes or the 🛍️ Takeaway checkbox toggles (base/tax may change).

## FR-WB2: Active order sidebar
When viewing an occupied table or active takeaway order (`GET /api/orders/{id}/details`), the summary shows the same 3-line breakdown using **server-calculated** fields:

| Response field | Meaning |
|----------------|---------|
| `breakdown_subtotal` | Pre-tax total (line subtotals minus line tax) |
| `breakdown_tax_total` | Sum of `unit_tax_at_sale × quantity` |
| `breakdown_grand_total` | Sum of non-cancelled line `subtotal` values |

## FR-WB3: Consistency
Cart client math must use the same rules as `routers/orders.py` `_calculate_order_line_pricing()` (see `specs/feature-menu-item-tax/`).

## Related
- `specs/feature-menu-item-tax/` — per-item tax
- `specs/feature-menu-pricing/` — dine-in vs takeaway base
