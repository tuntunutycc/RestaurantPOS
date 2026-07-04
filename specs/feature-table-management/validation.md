# Validation Checklist: Table Management Enhancements (Phase 1 - Step 7)

Validation evidence (2026-07-04):
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **52 passed**
- Primary test file: `tests/test_tables_management.py`
- Related: `tests/test_integrity.py` (report stability after table delete)

**RBAC note:** Backend and UI use `ADMIN_PANEL_ROLES` (`root`, `admin`), not admin-only. Account/cashier/waiter cannot mutate tables.

**Finalized order definition (implementation):** `paid` and `cancelled` are finalized; `open`, `dining`, `completed`, and other statuses block table delete.

## A. API + RBAC Validation

- [x] `PUT /api/tables/{table_id}` requires admin panel role (`root` or `admin`) — implemented, **not dedicated RBAC test**
- [x] `DELETE /api/tables/{table_id}` requires admin panel role — `test_admin_can_delete_empty_table` uses admin
- [x] Non-admin delete returns `403` — `test_non_admin_cannot_delete_table` (waiter only)
- [ ] Non-admin PUT returns `403` — **not tested** (waiter/cashier/account matrix incomplete)
- [ ] Update returns `404` when table does not exist — implemented, **untested**
- [ ] Update returns `404` when target zone does not exist — implemented, **untested**
- [ ] Update returns `400` for invalid/blank table name — implemented, **untested**
- [ ] Update returns `400` for duplicate table name — implemented, **untested**

## B. Delete Safety Constraints

- [x] Delete blocked (`400`) when table has non-finalized order — `test_table_with_active_order_cannot_be_deleted`
- [x] `completed` status also blocks delete — `test_table_with_completed_order_is_blocked_as_non_finalized`
- [x] Blocked delete response contains clear reason — asserted in tests
- [x] Delete succeeds when linked orders are finalized (`paid`) — `test_delete_detaches_finalized_orders_history`
- [x] Delete succeeds when linked orders are `cancelled` — `test_cancelled_order_allows_table_delete_and_detach`
- [x] Finalized orders preserved (not deleted) — asserted
- [x] Preserved orders have `table_id = NULL` — asserted

## C. Historical Integrity & Reporting

- [x] Historical orders retrievable after delete — order row preserved; UI shows `[Deleted Table]` label
- [x] Sales/report endpoints queryable after delete — `test_integrity.py::test_table_delete_preserves_order_history_and_sales_summary`
- [x] No loss of financial facts — same test asserts totals

## D. Admin UI / UX Validation (manual)

- [x] Edit action (rename + zone) — implemented in `counter.js` (code review)
- [x] Delete with confirmation — `dialogConfirm` before DELETE
- [x] Success toasts on update/delete — `window.toast.success`
- [x] Blocked delete error feedback — API `detail` surfaced
- [ ] Unauthorized mutation feedback — **manual only**
- [x] Non-panel roles do not see Table Management tab — `applyAdminOnlyTabVisibility`

## E. Realtime / Refresh Behavior

- [x] Local refresh after update/delete — `loadTableManagementData()` called
- [ ] `table_grid_updated` WebSocket handled in `counter.js` — **gap**: handler listens for `table_status_changed` only; remote multi-device sync may be stale
- [ ] No broken UI after delete — **manual verification**

## F. Automated Test Checklist

- [x] Delete success with finalized linked orders
- [x] Delete blocked with active/non-finalized orders
- [x] Non-admin delete denied (`403`) — waiter only
- [ ] Update rename + zone reassignment success — **recommended, not implemented**
- [ ] Update validation failures — **recommended, not implemented**
- [ ] Root smoke test for PUT/DELETE — **optional**

## G. Definition of Done

- [x] Delete safety + core RBAC + reporting integrity (automated)
- [ ] Full Section A PUT validation tests
- [ ] Manual UI sign-off (Section D)
- [ ] Realtime `table_grid_updated` in counter (Section E)
- [ ] Roadmap Step 7 → **completed** only after above gaps closed or accepted as debt
