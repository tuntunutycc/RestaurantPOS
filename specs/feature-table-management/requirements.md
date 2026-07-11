# Requirements: Table Management Enhancements (Phase 1 - Step 7)

## 1. Purpose
Strengthen table administration while preserving business history integrity.
This feature enables admin-controlled table edit/delete operations with strict deletion safety and historical order preservation.

## 2. Actors and Permissions

### 2.1 Admin / Root (admin panel roles)
- Can update table metadata:
  - rename table (`name_or_number`)
  - reassign table to another zone (`zone_id`)
- Can delete a table, subject to delete safety rules.
- Access: `ADMIN_PANEL_ROLES` = `root`, `admin` (`rbac.py`).

### 2.2 Waiter / Cashier / Account / Other roles
- Must not be able to mutate table resources (create/update/delete).
- Any attempted mutation must return `403 Forbidden`.

## 3. Functional Requirements

### FR-1: Table Edit (Admin-only)
- System must provide API and UI controls for admin to:
  - change table name
  - change table zone
- Validation rules:
  - table must exist
  - target zone must exist
  - table name must be non-empty
  - table name must remain unique

### FR-2: Explicit Table Delete Action (Admin-only)
- System must provide an explicit delete action in table management UI.
- UI must require user confirmation before delete request.

### FR-3: Delete Safety Constraint (Critical)
- Table deletion is allowed only when all orders linked to that table are finalized.
- If any linked order is non-finalized, delete must be rejected with `400 Bad Request` and clear reason text.

### FR-4: Historical Order Preservation
- On allowed table deletion:
  - linked finalized orders must be preserved
  - `orders.table_id` for those rows must be detached (`NULL`) before deleting table row
- Deletion must not remove/alter financial facts in historical orders.

### FR-5: User Feedback and UX
- Admin UI must show clear outcomes:
  - success message for update/delete
  - informative error for blocked delete
  - permission-denied message for unauthorized mutations

### FR-6: Realtime/UI Consistency
- After successful table mutations, affected screens should reflect updated table state through existing refresh/realtime mechanism.

## 4. Business Logic Rules

### BL-1: Finalized vs Non-finalized Orders
- Deletion eligibility depends on order finalization state.
- Any order in a non-finalized state blocks deletion.

### BL-2: Server-side Enforcement
- All deletion safety and RBAC constraints must be enforced in backend APIs (frontend checks are not sufficient).

### BL-3: Integrity over Convenience
- If ambiguity occurs between convenience and preserving business history, preserve history and block destructive action.

## 5. API Behavior Requirements

### 5.1 Update Table
- Method: `PUT`
- Auth: admin role required
- Success: returns updated table payload
- Failures:
  - `404` for missing table/zone
  - `400` for invalid or duplicate table name
  - `403` for non-admin

### 5.2 Delete Table
- Method: `DELETE`
- Auth: admin role required
- Success:
  - detach finalized linked orders (`table_id = NULL`)
  - delete table record
  - return success payload with deleted table id
- Failures:
  - `400` if non-finalized linked orders exist (blocked delete)
  - `404` if table not found
  - `403` for non-admin

## 6. Data Integrity Requirements
- No cascade behavior may erase historical orders because of table deletion.
- Reports and historical order endpoints must remain queryable after table deletion.
- Existing checkout/report totals must remain unaffected by table record removal.

## 7. Non-Functional Requirements
- Error responses for blocked deletes must be human-readable and actionable.
- Behavior must be deterministic across repeated requests.
- Existing table-related endpoints must remain backward compatible for current UI flows.

## 8. Table floor grid UX (see `specs/feature-table-all-view/`)
- Waiter, Cashier, and Table Dashboard floor grids use an **ALL** zone tab (default) and compact display names (strip leading `"Table "` in UI only).
- Admin kanban (zone columns) is unchanged for CRUD.

## 9. Acceptance Criteria
- AC-1: Admin can rename and reassign a table via UI and API.
- AC-2: Admin can delete table only when no non-finalized linked orders exist.
- AC-3: Delete is blocked with `400` and clear reason when active/non-finalized orders exist.
- AC-4: On successful delete, finalized linked orders remain in DB with `table_id = NULL`.
- AC-5: Non-admin table mutations return `403`.
- AC-6: Automated tests cover delete success, delete blocked, and RBAC denial scenarios.
