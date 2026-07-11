# Requirements: Per-Item Menu Discount

## Purpose
Allow admins to configure **item-level discounts** on menu items. Discount is applied to the effective base price **before** tax (standard POS math).

## Data model — `MenuItem`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `discount_type` | `none` \| `percentage` \| `fixed` | `none` | Discount mode |
| `discount_value` | `float` | `0.0` | Percent (e.g. `10`) or fixed amount (e.g. `200`) |

Legacy `discount_price` (sale price) remains in the DB for backward compatibility. When `discount_type` is `none` and `discount_price > 0`, the server treats it as a **fixed** discount of `effective_base - discount_price`.

### `OrderItem` snapshot

| Field | Notes |
|-------|-------|
| `unit_price_at_sale` | Effective **base** unit price at submit (before discount/tax) |
| `unit_discount_at_sale` | Per-unit discount amount at submit |
| `unit_tax_at_sale` | Per-unit tax at submit (on discounted price) |

## FR-D1: Effective base price

```
effective_base = takeaway_price  when line.is_takeaway and takeaway_price is set
               else price
```

## FR-D2: Discount formulas (per unit)

| `discount_type` | Formula |
|-----------------|---------|
| `none` | `unit_discount = 0` |
| `percentage` | `unit_discount = round(effective_base × (discount_value / 100), 2)` |
| `fixed` | `unit_discount = round(min(discount_value, effective_base), 2)` |

```
discounted_price = round(effective_base - unit_discount, 2)
```

## FR-D3: Tax after discount (CRITICAL)

Tax is calculated on **`discounted_price`**, not `effective_base`. See `specs/feature-menu-item-tax/requirements.md`.

```
unit_tax = tax_formula(discounted_price, tax_type, tax_value)
item_final_unit = discounted_price + unit_tax + modifiers_total
line_subtotal = round(item_final_unit × quantity, 2)
```

## FR-D4: Order-level breakdown

| Field | Formula |
|-------|---------|
| `breakdown_subtotal` | Σ `(effective_base + modifiers) × qty` |
| `breakdown_discount_total` | Σ `unit_discount_at_sale × qty` |
| `breakdown_tax_total` | Σ `unit_tax_at_sale × qty` |
| `breakdown_grand_total` | Σ line `subtotal` (= Subtotal − Discount + Tax) |

## FR-D5: Admin menu UI (current vs planned)

| Capability | Status |
|------------|--------|
| API accepts `discount_type`, `discount_value` on create/update | **Implemented** |
| Server pricing + snapshots | **Implemented** |
| Waiter cart breakdown | **Implemented** |
| Counter admin form: Discount Type + Value dropdowns | **Not yet** — uses legacy `#item-discount-price` (`discount_price`) only |

**Counter UI (`static/counter.js`, 2026-07):** create/update sends `discount_type: "none"`, `discount_value: 0`, plus optional `discount_price`. Server legacy rule (FR-D2) still applies at order time when `discount_price` is set.

## Authorization
- Menu write — `ADMIN_PANEL_ROLES`
- Orders — `POS_ORDER_ROLES`

## Related
- `specs/feature-menu-pricing/` — dine-in vs takeaway base
- `specs/feature-menu-item-tax/` — per-item tax on discounted price
- `specs/feature-waiter-cart-breakdown/` — waiter UI breakdown
