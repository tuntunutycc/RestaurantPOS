# Implementation Reference: Dual Pricing

## Price helper (`routers/orders.py`)

```python
def _resolve_unit_base_price(menu_item: MenuItem, *, is_takeaway: bool = False) -> float:
    """Effective base before discount/tax."""
    if is_takeaway:
        raw = getattr(menu_item, "takeaway_price", None)
        if raw is not None:
            return float(raw)
    return float(menu_item.price)
```

Discount and tax are applied in `_calculate_order_line_pricing()` (see `specs/feature-menu-item-discount/`).

## Migrations (`main.py`)
- `ALTER TABLE menu_items ADD COLUMN takeaway_price FLOAT`
- `ALTER TABLE order_items ADD COLUMN is_takeaway BOOLEAN NOT NULL DEFAULT 0` (SQLite: INTEGER 0/1)

## Frontend

| File | Change |
|------|--------|
| `counter.html` | `#item-takeaway-price` input |
| `counter.js` | create/update/reset/edit wiring |
| `waiter.js` | `getEffectiveBasePrice(item, isTakeaway)`, cart `is_takeaway`, checkbox in `renderCart()` |

## Tests
`tests/test_menu_dual_pricing.py`
