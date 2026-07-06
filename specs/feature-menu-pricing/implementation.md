# Implementation Reference: Dual Pricing

## Price helper (`routers/orders.py`)

```python
def _resolve_unit_base_price(menu_item: MenuItem, *, is_takeaway: bool = False) -> float:
    if is_takeaway:
        raw = getattr(menu_item, "takeaway_price", None)
        if raw is not None:
            return float(raw)
    return _base_price_with_discount(menu_item)
```

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
