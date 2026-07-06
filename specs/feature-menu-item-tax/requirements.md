# Requirements: Per-Item Tax

## Purpose
Allow admins to configure **item-level tax** on menu items. Tax is included in line subtotals at order time and summed at checkout (replaces the legacy fixed 5% order-level tax).

## Data model — `MenuItem`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `tax_type` | `none` \| `percentage` \| `fixed` | `none` | Tax mode |
| `tax_value` | `float` | `0.0` | Percent (e.g. `5`) or fixed amount (e.g. `500`) |

### `OrderItem` snapshot

| Field | Notes |
|-------|-------|
| `unit_tax_at_sale` | Per-unit tax at submit time (audit + receipt) |

Line `subtotal` stores **(base + unit_tax + modifiers) × quantity** (rounded per line).

## FR-T1: Active price for tax base

```
base = takeaway_price when line.is_takeaway and takeaway_price is set
     else discount_price when discount_price > 0
     else price
```

Tax is calculated on **`base` only** (not modifiers).

## FR-T2: Tax formulas (per unit, before modifiers)

| `tax_type` | Formula |
|------------|---------|
| `none` | `unit_tax = 0` |
| `percentage` | `unit_tax = round(base × (tax_value / 100), 2)` |
| `fixed` | `unit_tax = round(tax_value, 2)` |

```
line_subtotal = round((base + unit_tax + modifiers_total) × quantity, 2)
```

## FR-T3: Order submit / create
- Server applies FR-T1–T2 per line; persists `unit_price_at_sale`, `unit_tax_at_sale`, `subtotal`.
- `Order.total_amount` (open orders) = sum of non-cancelled line subtotals minus any order-level discount preview (unchanged discount helper).

## FR-T4: Checkout
```
subtotal = sum(non-cancelled line subtotals)   # tax-inclusive
tax_amount = sum(unit_tax_at_sale × quantity)  # receipt breakdown
discount_amount = order-level discount on subtotal
grand_total = round(max(subtotal - discount_amount, 0), 2)
```
No additional global 5% tax.

## FR-T5: Admin menu UI
- Tax Type dropdown: None / Percentage % / Fixed Amount
- Tax Value input (hidden/disabled when None)

## FR-T6: Waiter / Cashier display
- Cart and menu show **effective unit price** = base + unit_tax (+ modifiers when applicable).
- Checkout receipt `tax_amount` matches backend.

## Authorization
- Menu write — `ADMIN_PANEL_ROLES`
- Orders — `POS_ORDER_ROLES` / `CHECKOUT_ROLES`

## Related
- `specs/feature-menu-pricing/` — dine-in vs takeaway base price
- `specs/tech-stack.md` — checkout money rules (updated)
