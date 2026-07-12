# Validation: Waiter Cart Price Breakdown

```bash
PYTHONPATH=. pytest tests/test_waiter_cart_breakdown.py -v
PYTHONPATH=. pytest -q
```

## Manual
- [ ] Cart shows Subtotal / Tax / Grand Total; toggling takeaway updates tax
- [ ] Cart line `+` / `-` adjusts qty; `-` to 0 removes line; notes/modifiers retained; footer totals update
- [ ] Active-order modal still has **no** qty `+`/`-` (cancel item only)
- [ ] **Submit Order** appears directly under Grand Total; floor pane is separate
- [ ] Active-order modal shows same breakdown from API fields

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | `tests/test_waiter_cart_breakdown.py` | **1 passed** |
| 2026-07-06 | Full `pytest -q` | **157 passed** |
