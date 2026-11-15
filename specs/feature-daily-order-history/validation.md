# Validation: Daily Order History

```bash
PYTHONPATH=. pytest tests/test_daily_order_history.py -v
```

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Paid order on day D listed | Appears with total + items |
| 2 | Open/unpaid order | Not listed |
| 3 | Waiter role | 403 |
| 4 | Export xlsx | 200, spreadsheet content-type, Order ID present |
| 5 | Takeaway line in detail | `is_takeaway` true + modifiers in payload |

## Manual
- [ ] `/order-history` date picker defaults to today
- [ ] View Details modal shows modifiers + ပါဆယ် badge
- [ ] Export downloads `.xlsx` that opens in Excel

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-11-15 | `tests/test_daily_order_history.py` | **4 passed** |
