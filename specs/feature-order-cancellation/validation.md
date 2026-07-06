# Validation: Order Cancellation (Item-Level)

```bash
PYTHONPATH=. pytest tests/test_checkout_cancellation.py tests/test_walk_in_takeaway.py -v -k cancel
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Cancel dine-in item via `PUT .../items/{id}/status` | Line `cancelled`; table freed when last item |
| 3 | Cancel takeaway item (`table_id` null) | **200**; line `cancelled`; order auto-cleared from active list |
| 3 | Checkout excludes cancelled lines from total | Net total correct |

## Manual
- [ ] Occupied table → cancel pending item in sidebar
- [ ] Active takeaway card → same sidebar → cancel pending item
- [ ] No "Cancel Entire Order" button on waiter or cashier

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | Takeaway item cancel test | See `test_cancel_takeaway_order_item_without_table` |
| 2026-07-06 | Full `pytest -q` | **152 passed** |
