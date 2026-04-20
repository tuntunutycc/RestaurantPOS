# Feature Plan: Table Management Enhancements (Phase 1 - Step 7)

## Objective
Implement admin-focused table management improvements with strict deletion safety:
- admin can edit table name and zone
- admin can explicitly delete a table from UI
- non-admin users cannot mutate tables
- table deletion is blocked if non-finalized orders exist
- finalized historical orders are preserved by detaching `table_id`

## Scope
- Frontend: admin table-management UX in `static/counter.js` / `static/counter.html`
- Backend: table update/delete API behavior and RBAC in `routers/tables.py`
- Contracts: schema compatibility for table payloads in `schemas.py` (only if needed)
- Tests: backend automated tests for success/block/RBAC paths

## Out of Scope
- No waiter/cashier table-mutation permissions
- No changes to checkout/business tax logic
- No migration to new frontend framework

## Implementation Steps

### 1) Confirm contract and role boundaries
- Verify update and delete endpoints for tables remain admin-only.
- Confirm required request/response shapes for:
  - update table (rename + zone reassignment)
  - delete table success payload
  - delete table blocked payload (400 + clear reason)
- Ensure no endpoint contract drift for existing consumers.

### 2) Backend: table update behavior hardening
- Ensure update endpoint supports:
  - table rename (`name_or_number`)
  - zone reassignment (`zone_id`)
- Validate:
  - table exists
  - target zone exists (when zone changes)
  - new table name is non-empty and unique
- Keep role guard admin-only.

### 3) Backend: table delete safety rule
- Define finalized statuses for delete eligibility.
- On delete request:
  1. query orders linked to table
  2. if any non-finalized order exists -> return `400` with explicit reason
  3. if all linked orders are finalized -> set linked orders `table_id = NULL`
  4. delete table record
- Preserve historical order/report integrity (no historical order loss).

### 4) Backend: realtime/event consistency
- If table grid relies on websocket refresh, ensure table mutation paths trigger expected refresh events so admin/waiter/cashier UIs remain consistent.

### 5) Frontend: admin table-management UX
- Add/keep explicit controls in admin table management panel for:
  - edit table (name + zone)
  - delete table with confirmation dialog
- Show clear feedback messages for:
  - successful update/delete
  - blocked delete (active/non-finalized orders)
  - permission failure (403)
- Ensure UI does not expose table mutation actions to non-admin roles.

### 6) Automated tests (merge gate)
- Add/extend backend tests for:
  - delete success when all linked orders are finalized
  - delete blocked when any linked order is non-finalized
  - non-admin delete denial (`403`)
  - optional: update success and validation failures for name/zone constraints

### 7) Documentation alignment
- Update roadmap/remediation references if step status changes from "in progress" to "completed."
- Keep spec artifacts and test evidence synchronized.

## Delivery Criteria
- Admin can edit and delete tables from UI.
- Deletion safety invariant is enforced server-side.
- Historical finalized orders remain queryable after table deletion.
- RBAC is enforced and verified by automated tests.
