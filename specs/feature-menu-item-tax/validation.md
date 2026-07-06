# Validation: Per-Item Tax

```bash
PYTHONPATH=. pytest tests/test_menu_item_tax.py -v
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Item `tax_type=none` | Line subtotal = base only; checkout `tax_amount=0` |
| 2 | Dine-in 5% on price 1000 | `unit_tax=50`; line subtotal 1050×qty |
| 3 | Takeaway fixed 500 on takeaway_price 2000 | `unit_tax=500`; line subtotal 2500×qty |

## Manual
- [ ] Admin: set tax on menu item; save and reload
- [ ] Waiter cart shows base + tax unit price
- [ ] Cashier receipt tax matches backend

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| TBD | `tests/test_menu_item_tax.py` | **3 passed** |
| 2026-07-06 | Full `pytest -q` | **156 passed** |
