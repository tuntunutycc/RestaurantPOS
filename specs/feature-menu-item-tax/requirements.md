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

## FR-T1: Tax base (after discount — CRITICAL)

```
effective_base = takeaway_price when line.is_takeaway and takeaway_price is set
               else price

unit_discount = discount_formula(effective_base, discount_type, discount_value)
discounted_price = effective_base - unit_discount
```

Tax is calculated on **`discounted_price` only** (not modifiers, not pre-discount base). See `specs/feature-menu-item-discount/`.

## FR-T2: Tax formulas (per unit, before modifiers)

| `tax_type` | Formula |
|------------|---------|
| `none` | `unit_tax = 0` |
| `percentage` | `unit_tax = round(discounted_price × (tax_value / 100), 2)` |
| `fixed` | `unit_tax = round(tax_value, 2)` |

```
line_subtotal = round((discounted_price + unit_tax + modifiers_total) × quantity, 2)
```

## FR-T3: Order submit / create
- Server applies FR-T1–T2 per line; persists `unit_price_at_sale`, `unit_discount_at_sale`, `unit_tax_at_sale`, `subtotal`.
- `Order.total_amount` (open orders) = sum of non-cancelled line subtotals (order-level checkout discount applied only at checkout, not on open-order preview).

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

## FR-T6: Waiter / Cashier display (current)

| Surface | Shows |
|---------|--------|
| **Menu grid** | Base price with strikethrough when discount applies (dine-in base) |
| **Cart line** | Per-item `Base \| Disc \| Tax` breakdown + line final total |
| **Cart footer / order sidebar** | 4-line Subtotal / Total Discount / Tax / Grand Total |
| **Modifier modal “Add to Cart”** | Base + modifiers only (tax/discount reflected after add, in cart) |
| **Cashier checkout** | Sum of line taxes; order-level discount separate |

Checkout receipt `tax_amount` matches backend sum of `unit_tax_at_sale × quantity`.

## Authorization
- Menu write — `ADMIN_PANEL_ROLES`
- Orders — `POS_ORDER_ROLES` / `CHECKOUT_ROLES`

## Related
- `specs/feature-menu-pricing/` — dine-in vs takeaway base price
- `specs/tech-stack.md` — checkout money rules (updated)
