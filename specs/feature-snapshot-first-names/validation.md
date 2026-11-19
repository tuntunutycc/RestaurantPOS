# Validation: Snapshot-first item names (Step 1 of 2)

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` -> **627 passed** (2026-11-19; 17 in `tests/test_snapshot_first_names.py`). Before the fix 7 of the new tests failed for the expected reason (the live name was shown after a rename).

## Automated - `tests/test_snapshot_first_names.py`
Use unique item names per test (the in-memory DB is shared across the suite).

- [x] FR-N1: order an item, **rename** it, then check the old name is still shown by: `GET /orders/{id}/details`, order list, active-by-table (`GET /orders/tables` is not asserted: it answers `500` when an open takeaway and an open table order coexist - a separate, pre-existing problem, see CHANGELOG), the Order History day detail, the checkout response (paid order), and the receipt payload.
- [x] FR-N1: open bill, rename, add the item again (new batch): the first line shows the old name, the new line the new name.
- [x] FR-N1: prices and totals of the same bill are unchanged by the rename (guards against fixing names by accident through money).
- [x] FR-N1: reports (top items, category sales, cancellations) after a rename still use the old name for old sales (regression, already true).
- [x] FR-N1: soft-deleted item -> snapshot name; no snapshot and item deleted -> `[Deleted Item]`.
- [x] FR-N1: legacy line with `menu_item_name_at_sale = NULL` or `"   "` and a live item -> live name (fallback).
- [x] FR-N2: backfill fills `NULL` / blank name and category snapshots from the live row; leaves non-empty values alone; leaves `__system_archived__` category as `NULL`; leaves `unit_price_at_sale` alone; second run changes nothing.
- [x] FR-N2: a row whose menu item was hard-deleted is untouched and the backfill does not raise.
- [x] FR-N3: new lines from `create_order` (new order), `create_order` (add to order) and `submit_order` all store the name and category snapshot.
- [x] Roles unchanged: waiter / cashier / admin responses keep the same shape (contract test on the three read endpoints).
- [x] Whole suite: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` is green (baseline before this step: 610 passed).
- [x] Mutation check: 8 deliberate breakages (ignore snapshot, no trim, deleted item live name, overwrite names, archive bucket used, blank category not filled, lifespan call removed, error not swallowed) - all caught; files restored.
- [x] Start-up: the lifespan runs the backfill (`test_server_start_runs_the_backfill`).

## Review checklist
- Security / roles: no new endpoint or permission.
- Money: no totals touched; rename tests assert money is identical.
- Edge cases: open bill with mixed names, blank snapshot, deleted item, legacy `NULL`, archived category, running the backfill twice, failed backfill at start-up.
- Not verified: real printers, a real browser (no frontend change in this step).
