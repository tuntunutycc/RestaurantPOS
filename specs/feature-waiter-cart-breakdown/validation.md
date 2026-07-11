# Validation: Waiter Cart Price Breakdown

```bash
PYTHONPATH=. pytest tests/test_waiter_cart_breakdown.py -v
PYTHONPATH=. pytest -q
```

## Manual
- [ ] Cart shows Subtotal / Tax / Grand Total; toggling takeaway updates tax
- [ ] **Submit Order** appears directly under Grand Total; zone/table grid is **below** submit
- [ ] Order details sidebar shows same breakdown from API fields

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | `tests/test_waiter_cart_breakdown.py` | **1 passed** |
| 2026-07-06 | Full `pytest -q` | **157 passed** |
