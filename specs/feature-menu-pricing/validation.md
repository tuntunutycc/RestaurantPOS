# Validation: Dual Pricing

```bash
PYTHONPATH=. pytest tests/test_menu_dual_pricing.py -v
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Create menu item with `takeaway_price` | **200**; field persisted |
| 2 | Submit dine-in line (`is_takeaway=false`) | `unit_price_at_sale` = dine-in base |
| 3 | Submit takeaway line with `takeaway_price` set | `unit_price_at_sale` = takeaway price |
| 4 | Submit takeaway line without `takeaway_price` | `unit_price_at_sale` = dine-in base (fallback) |

## Manual
- [ ] Counter menu form: optional Takeaway Price saves on create/edit
- [ ] Waiter cart: 🛍️ checkbox updates line subtotal when takeaway price exists

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | `tests/test_menu_dual_pricing.py` | **4 passed** |
| 2026-07-06 | Full `pytest -q` | **142 passed** |
