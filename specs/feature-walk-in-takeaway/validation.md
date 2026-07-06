# Validation: Walk-in Takeaway

```bash
PYTHONPATH=. pytest tests/test_walk_in_takeaway.py -v
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Submit takeaway with `table_id=null` | **200**; `order.table_id` null; `created_by_id` = waiter |
| 2 | Promoted report includes null-table order | Waiter row has sales qty |
| 3 | Dine-in without `table_id` | **400** |
| 4 | `GET /api/orders/{id}/details` for null-table takeaway | **200**; `table_id` null |
| 5 | Append via `POST /api/orders/submit` + `order_id` | **200**; `is_new_order=false`; batch 2 |
| 6 | Cancel item on `table_id=null` takeaway | **200**; line `cancelled`; total recalculated |
| 7 | Cancel last takeaway item → auto-clear | Order `cancelled`; absent from `active-takeaways` |

## Manual
- [ ] `[ + Walk-in Takeaway ]` prompts for optional customer name, then opens cart without table
- [ ] Click active takeaway card → order details sidebar (items list, same as occupied table)
- [ ] Cancel unserved item from takeaway sidebar → item cancelled; list refreshes
- [ ] **Add More Items** → append mode → submit add-on → single receipt at cashier

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-06 | `tests/test_walk_in_takeaway.py` | **7 passed** |
| 2026-07-06 | Full `pytest -q` | **156 passed** |
