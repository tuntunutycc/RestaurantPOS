# Roadmap

This roadmap is structured for Spec-Driven Development (SDD): every step is tied to verifiable outputs (contracts, tests, and acceptance criteria).

## Phase 0: Completed Features (Baseline)
This baseline captures features that are currently implemented and functional in the existing codebase, grouped by module and role.

### Authentication & Role Access (admin / waiter / cashier)
- JWT-based authentication is implemented with both username/password and PIN login flows:
  - `POST /api/auth/login`
  - `POST /api/auth/login-pin`
- Token validation and role-aware frontend guards are implemented for protected screens.
- Backend RBAC is enforced via role guards on protected endpoints (orders, reports, tables/zones, users).
- Roles are operationally enforced for core flows:
  - waiter can submit/update orders but cannot checkout,
  - cashier/admin can checkout,
  - unauthorized role access returns `403`.

### Admin: Staff User Management
- Admin users can list/create/update/delete staff users via `/api/admin/users`.
- User deletion is implemented as soft delete (`is_deleted`, `deleted_at`) rather than hard delete.
- Safety constraints are implemented:
  - cannot delete own account,
  - cannot delete the last remaining admin.
- Admin user management UI exists in the counter/admin screen.

### Admin: Menu & Category Management
- Category create/list endpoints are implemented.
- Menu item create/list/update/delete endpoints are implemented.
- Menu item availability toggle (`is_available`) is implemented.
- Menu item soft delete is implemented (`is_deleted`, `deleted_at`) to preserve historical order linkage.
- Modifier configuration support is implemented (`modifiers_config`) and used in order pricing.
- Menu item image upload/serving is implemented (upload endpoint + static image serving).
- Admin menu-management UI exists in the counter/admin screen.

### Admin: Zone/Table Management
- Zones and tables CRUD endpoints are implemented.
- Admin-only table management UI exists, including edit (rename/zone reassignment) and delete actions.
- Deletion safety constraints are implemented:
  - block delete when active/non-finalized orders exist,
  - detach historical finalized orders (`table_id = NULL`) when deleting table/zone-linked records.
- Table status/grid endpoints are implemented for waiter/cashier/admin views.

### Waiter: Order Taking & Item Lifecycle
- Waiter dine-in and takeaway ordering flows are implemented in the waiter UI.
- Table-centric order behavior is implemented:
  - create a new open/dining order,
  - append add-on items to existing open/dining order.
- Submit/add-on batching is implemented using `batch_number`.
- Per-line order details are implemented:
  - quantity,
  - selected modifiers,
  - note/special instructions,
  - waiter attribution (`created_by_id`).
- Item status updates are implemented (`pending`, `cooking`, `served`, `cancelled`) through API + UI actions.
- Cancelled-line handling is implemented so cancelled items are excluded from payable totals.

### Cashier: Checkout & Receipt
- Cashier table/takeaway active-order selection flows are implemented.
- Checkout endpoint is implemented (`POST/PUT /api/orders/{order_id}/checkout`) with:
  - payment method capture,
  - optional discount (`percentage` or `amount`),
  - amount tendered validation,
  - change calculation,
  - payment finalization (`status = paid`).
- Money calculation invariants are implemented:
  - deterministic rounding to 2 decimals,
  - tax computed after discount (5% on net taxable amount),
  - negative-safe clamping for taxable/tax/total.
- Cashier receipt rendering and print-friendly receipt output are implemented in UI.

### Reporting & Analytics
- Reports endpoints are implemented for:
  - today summary,
  - top items,
  - hourly trend,
  - daily sales,
  - monthly sales,
  - category sales,
  - cancellations analytics.
- Dashboard charts/tabs are implemented in the counter/admin screen.
- Historical-null-safe reporting behavior is implemented using fallback labels and snapshot columns where needed.

### Realtime & Eventing (WebSocket)
- `/ws` realtime endpoint and connection manager are implemented.
- Broadcast events are implemented for operational refresh workflows, including:
  - `new_order_batch`,
  - `order_updated`,
  - `order_completed`,
  - `takeaways_updated`,
  - `table_status_changed`,
  - `table_grid_updated`,
  - menu item update/delete/availability events.
- Frontend listeners are implemented in waiter/counter/table-dashboard screens for live refresh.

### Kitchen Ticket Dispatch (Mock Printing)
- Kitchen dispatch is implemented as mock printer output writers (file-based) routed by item category/printer mapping.
- Tickets are written to local `*_output.txt` files to simulate printer output.

### Data Integrity & Null-Safety Baseline
- Soft-delete lifecycle is implemented for `users` and `menu_items`.
- Order and reporting payloads include deleted-reference-safe fallback behavior (e.g., deleted user/item labels).
- Detached/deleted table links are handled without breaking order/report flows.

### Test Coverage Baseline
- Automated backend test harness is implemented with `pytest` and isolated test DB setup.
- Test coverage includes core invariant and contract behavior:
  - auth and role checks,
  - order contracts and RBAC,
  - cancellation/checkout money correctness,
  - rounding and tax invariants,
  - deletion-integrity behavior for historical data,
  - table deletion safety constraints.

## Completed (Current Implementation Observed in Codebase)
The current codebase already implements the core end-to-end POS workflows and realtime behavior required for a functional restaurant POS:
- Authentication endpoints exist:
  - `POST /api/auth/login`
  - `POST /api/auth/login-pin`
- Core admin/waiter/cashier UI exists as static HTML + JavaScript (served by FastAPI):
  - waiter screen: dine-in/takeaway order taking + submitting batches
  - counter screen: cashier checkout + reports dashboard
  - table dashboard: item status controls and table/order detail sidebar
- Backend POS domain endpoints exist:
  - menu management (`/api/categories/`, `/api/menu-items/`)
  - zones/tables management (`/api/zones`, `/api/tables`)
  - order lifecycle (`/api/orders/submit`, `/api/orders/active-takeaways`, `/api/orders/active-by-table/{id}`, `/api/orders/{order_id}/details`, `/api/orders/{order_id}/items/{item_id}/status`)
  - checkout (`/api/orders/{order_id}/checkout`)
  - reports analytics (`/api/reports/*`)
- WebSocket realtime exists:
  - kitchen/KDS-style batch delivery (`new_order_batch`)
  - table/cashier refresh (`order_updated`, `table_status_changed`, `table_grid_updated`)
  - takeaways refresh (`takeaways_updated`)
  - menu item realtime updates
- Printing is implemented as a mock ticket writer:
  - writes to local `*_output.txt` files per resolved printer name

### Remediation Status (Completed)
All planned remediation steps are now implemented and test-backed:
- Step 0: Test harness established
  - `pytest` + API test setup with isolated test DB and role-based auth helpers
- Step 1: Cancellation vs checkout consistency fixed
  - checkout excludes cancelled line items from payable subtotal
  - cashier receipt rendering hides cancelled items
- Step 2: API contract hardening complete
  - critical order endpoints now use explicit `response_model`
- Step 3: Comprehensive RBAC enforcement complete in `routers/orders.py`
  - create/append/view endpoints: `admin`, `cashier`, `waiter`
  - checkout endpoints: `admin`, `cashier` only
  - unauthorized access returns `403`
- Step 4: `order.status` literal validation complete
  - strict allowed status literals with normalization
  - invalid literals rejected with `422`
- Step 5: Rounding determinism completed
  - money values rounded to 2 decimals before save/response in key order flows
  - invariant tests cover decimal-sensitive scenarios (e.g., `3.33 × 3 = 9.99`) and stable checkout change calculations
- Step 6: Sales tax on net amount (completed)
  - Introduce fixed 5% tax at checkout using Option B (tax on net amount after discount).
  - Formula:
    - `taxable_amount = max(subtotal - discount_amount, 0.0)`
    - `tax_amount = _round_money(taxable_amount * 0.05)`
    - `grand_total = _round_money(taxable_amount + tax_amount)`
  - Contract/UI impact:
    - include `tax_amount` in checkout/order response contracts
    - show `Tax (5%)` in checkout modal, receipt view, and printable receipt
  - Test impact:
    - add invariant tests for rounding determinism and negative-safe tax/grand-total clamping
- Step 7: Table management enhancements (in progress)
  - Add admin table edit UX (rename + zone reassignment).
  - Keep admin-only table update/delete endpoints enforced by backend RBAC.
  - Harden delete safety: block deleting tables with non-finalized orders and return a clear `400` reason.
  - Preserve sales history safely by detaching finalized historical orders (`table_id = NULL`) when table deletion succeeds.
  - Add test coverage for successful delete, blocked delete with active order, and non-admin RBAC denial.
- Step 8: System integrity audit for deletion safety (planned)
  - Audit all FK relationships in `models.py` and remove destructive delete behavior for critical history.
  - Harden user deletion so historical transactional rows survive (null-safe references + fallback labels).
  - Harden menu item deletion with soft-delete-first policy for items with order history.
  - Enforce backend/frontend null-safety when related rows are deleted or detached.
  - Add invariant tests proving reports remain stable after user/menu-item deletion events.

Validation evidence:
- Automated backend suite is green with invariant/contract/RBAC/cancellation tests.
- Current result after Step 6: `20 passed` in `pytest`.

## Phase 1 (0–30 days): Fully Functional POS MVP
### Goal
Deliver end-to-end daily restaurant POS functionality for `admin`, `waiter`, and `cashier`.

### Must-win outcomes (verifiable)
- Login works for username/password and PIN.
- Staff roles correctly gate sensitive actions (admin vs waiter vs cashier).
- Admin can manage:
  - categories
  - menu items (including `is_available`, modifiers config, and images)
  - zones and tables
  - staff users
- Waiter can:
  - create dine-in orders for tables
  - add-on items to an existing open/dining order for a table
  - create takeaway orders
  - submit items so kitchen/KDS receives new batches
  - update item status (served/cooking/cancelled)
- Cashier can:
  - view one canonical order per table
  - checkout with payment method, optional discount, tendered and change validation
- Reports return stable analytics summaries for the current day and historical trends.

### Implementable steps
1. Contract hardening for critical order flows (completed)
   - Add missing `response_model` types for the key order endpoints.
   - Ensure request/response schemas are aligned to the specs and are stable for the frontend.
2. Correctness alignment: cancellation and checkout totals (completed)
   - Ensure totals computed during:
     - item cancellation/state changes
     - checkout
     are consistent and exclude cancelled items using the same server-side rule.
3. Backend RBAC enforcement for order APIs (completed)
   - Add `require_roles(...)` to order endpoints so role boundaries are enforced server-side (not only by frontend gating).
4. Automated test harness + merge-gate tests (completed)
   - Add `pytest` + backend tests.
   - Add tests for:
     - role access (admin/waiter/cashier)
     - order submit and checkout invariants
     - cancellation effects on totals
     - invalid status inputs
5. Financial rounding determinism improvements (completed)
   - Make rounding/2-decimal rules explicit and consistent across order submit/append, item updates, and checkout.
6. Sales tax on net amount (completed)
   - Add fixed 5% tax calculated after discount during checkout.
   - Clamp taxable base to avoid negative tax and negative grand total.
   - Extend contracts and UI/receipt rendering to expose `tax_amount` consistently.
   - Add automated invariants for tax rounding and large-discount edge cases.
7. Table management enhancements (completed)
   - Add admin-side table edit controls (rename + zone reassignment) and explicit delete actions in table management UI.
   - Keep table mutations strictly admin-only.
   - Block table deletion when non-finalized orders exist; allow deletion only after orders are finalized.
   - Detach finalized historical orders from deleted tables to preserve sales history.
   - Add test coverage for delete success, delete blocked by active order, and non-admin delete denial.
8. System integrity + stability audit for data deletion (next)
   - **FK strategy hardening**
     - Prohibit critical-history cascades (especially order-history references).
     - Use nullable references + `SET NULL` semantics where entity deletion is allowed.
   - **Soft delete rollout**
     - Add soft-delete lifecycle for `users` and `menu_items` (`is_deleted`, `deleted_at`, optional `deleted_by_id`).
     - Keep hard delete only for entities with no historical references.
   - **Null safety**
     - Backend schemas/serializers/reports must return fallback values for missing related entities.
     - Frontend screens must render `[Deleted User]` / `[Deleted Item]` without crashes.
   - **Invariant tests**
     - Add tests that delete/soft-delete users and menu items, then verify daily sales and analytics endpoints still return valid data.

## Phase 2 (31–90 days): Stable POS System
### Goal
Reduce production incidents and make the system predictable for staff under busy conditions.

### Must-win outcomes (verifiable)
- Order correctness improves (lower `order error rate`).
- Staff adoption improves (reduce training time through consistent UX).
- Checkout time is within acceptable bounds under typical load.

### Implementable steps
1. Strengthen domain rules with tests
   - Add regression tests for edge cases:
     - invalid quantities
     - invalid statuses
     - discount edge cases (0, negative, huge values)
     - duplicate/rapid submits (define expected behavior)
2. Improve money correctness strategy
   - Define a contract-level rule for rounding (2 decimals).
   - Plan refactor from `float` toward `Decimal`/`Numeric` while keeping API contracts stable.
3. Backend error handling standardization
   - Create a consistent error response format.
   - Update frontend to handle these errors predictably.
4. Documentation completeness for SDD
   - Every feature spec must include:
     - acceptance criteria (Given/When/Then)
     - API contract updates (schemas + response_model)
     - automated tests scope
     - review checklist completion
5. WebSocket reliability and payload stability
   - Ensure event names and payload fields remain backwards compatible or are versioned.

## Phase 3 (3–12 months): Extendable Platform
### Goal
Add new features safely without breaking existing workflows.

### Implementable steps
1. Data platform hardening (PostgreSQL)
   - Create a PostgreSQL migration plan.
   - Adopt migration tooling (e.g., Alembic) once moving beyond SQLite constraints.
2. Frontend evolution (optional)
   - Keep current JS UI in the short term (as you requested).
   - Later stage: migrate to Next.js or another structured frontend only after contracts and tests are stable.
3. Feature extension framework
   - Establish “new feature templates”:
     - feature spec template
     - contract change checklist
     - tests template
     - UX review checklist
4. Expand domain model (as requested)
   - Add features only through spec + tests workflow, for example:
     - tax, item categories by printer mapping customization
     - shift/session tracking
     - refunds or partial refunds
     - inventory/purchasing (if needed)

## Roadmap Governance (SDD)
- Every merge requires: spec + contract updates + review checklist + automated tests.
- Final decision authority: `developer` role (per our constitution draft).

