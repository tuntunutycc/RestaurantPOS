# Validation Checklist: Table Management Enhancements (Phase 1 - Step 7)

Use this checklist to verify feature completeness before marking Step 7 as done.

## A. API + RBAC Validation

- [ ] `PUT /api/tables/{table_id}` requires admin role.
- [ ] `DELETE /api/tables/{table_id}` requires admin role.
- [ ] Non-admin mutation attempts (waiter/cashier/other) return `403`.
- [ ] Update returns `404` when table does not exist.
- [ ] Update returns `404` when target zone does not exist.
- [ ] Update returns `400` for invalid/blank table name.
- [ ] Update returns `400` for duplicate table name.

## B. Delete Safety Constraints

- [ ] Delete is blocked (`400`) when table has at least one non-finalized order.
- [ ] Blocked delete response contains clear, user-readable reason.
- [ ] Delete succeeds when linked orders are finalized.
- [ ] On successful delete, linked finalized orders are preserved (not deleted).
- [ ] On successful delete, preserved finalized orders have `table_id = NULL`.

## C. Historical Integrity & Reporting

- [ ] Historical finalized orders remain retrievable after table deletion.
- [ ] Sales/report endpoints remain queryable after table deletion event.
- [ ] No loss of historical financial facts due to table deletion.

## D. Admin UI / UX Validation

- [ ] Table management UI has explicit edit action (rename + zone reassignment).
- [ ] Table management UI has explicit delete action with confirmation.
- [ ] Successful update shows clear success feedback.
- [ ] Successful delete shows clear success feedback.
- [ ] Blocked delete shows informative error feedback.
- [ ] Unauthorized mutation handling shows appropriate permission-denied feedback.
- [ ] Non-admin users do not see table-mutation controls in admin surface.

## E. Realtime / Refresh Behavior

- [ ] After successful table update, table views reflect latest data without stale state.
- [ ] After successful table delete, table grid/views refresh correctly.
- [ ] No broken UI state when deleted table previously appeared in visible lists.

## F. Automated Test Checklist (Required)

- [ ] Test: delete success for table with finalized linked orders.
- [ ] Test: delete blocked for table with active/non-finalized linked orders.
- [ ] Test: non-admin delete attempt denied (`403`).
- [ ] (Recommended) Test: update table rename + zone reassignment success.
- [ ] (Recommended) Test: update validation failures (duplicate name, missing zone).

## G. Definition of Done

- [ ] All required checks in sections A-F pass.
- [ ] Test suite is green.
- [ ] Roadmap Step 7 status can be safely moved to completed with evidence.
