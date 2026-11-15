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
| 5 | Kitchen per-line slips with mixed `is_takeaway` | Takeaway lines use `{name} (ပါဆယ်)`; dine-in lines do not |
| 6 | Cashier receipt with `is_takeaway` line | Receipt item name includes `(ပါဆယ်)` |

## Manual
- [ ] Counter menu form: optional Takeaway Price saves on create/edit
- [ ] Waiter cart: 🛍️ checkbox updates line subtotal when takeaway price exists
- [ ] Dine-in table + Takeaway tick → kitchen slip shows ပါဆယ် under that item; cashier UI + receipt show marker

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | `tests/test_menu_dual_pricing.py` | **4 passed** |
| 2026-07-06 | Full `pytest -q` | **142 passed** |
| 2026-11-14 | `tests/test_menu_dual_pricing.py` (+ print markers) | **passed** |
