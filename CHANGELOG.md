# Changelog

## 2026-07-05 — Cashier denied Staff Performance (SDD alignment)

### Summary
Cashiers may view **own checkout total today** only. Staff Performance APIs and Counter UI (`by-cashier`, `by-order-staff`, dashboard subtab) are **root/admin only**.

### Backend
- `routers/reports.py` — removed `cashier` from `_STAFF_REPORT_ROLES` and `_ORDER_STAFF_ROLES`
- `services/report_access.py` — `can_view_staff_breakdown` / `can_view_all_waiter_sales` → root/admin only

### Frontend
- `static/counter.js` — hide Staff Performance section and charts for cashier

### Spec / Tests
- `specs/feature-cashier-reports/` + `specs/feature-rbac/` — requirements, implementation, validation synced
- `tests/test_cashier_reports.py` — `test_cashier_cannot_view_*` (**403**)
- Full suite: **121 passed** (`pytest -q`)

## 2026-07-05 — Cashier reports & waiter incentives SDD + tests

### Summary
Formalized SDD for cashier ordering inheritance, scoped daily sales, staff breakdown, and promoted-item incentives. Added dedicated pytest modules; backend already complete on `main`.

### Spec
- `specs/feature-cashier-reports/` — requirements, plan, implementation, validation
- `specs/feature-waiter-incentives/` — requirements, plan, implementation, validation

### Tests
- `tests/test_cashier_reports.py` (5)
- `tests/test_waiter_incentives.py` (7)
- Full suite: **84 passed** (`pytest -q`, 2026-07-05)

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **84 passed**

## 2026-07-05 — Staff Performance date-range reporting (root QA gap)

### Summary
Counter Dashboard → Staff Performance now supports **daily and monthly** per-cashier and per-waiter breakdowns via a date-range picker (not single-day only).

### Frontend
- `static/counter.html` — `staff-filter-start-date` / `staff-filter-end-date`; presets **Today** and **This Month**
- `static/counter.js` — `getStaffReportDateRange()`, default month-to-date; charts call `by-cashier` / `by-order-staff` with `start_date` + `end_date`

### Spec / Tests
- `specs/feature-rbac/` — requirements (FR-D1), implementation, validation, plan, roadmap synced
- `test_per_cashier_and_waiter_reports` — monthly `by-cashier` range assertion
- `test_phase4_dashboard_ui_contract` — staff date-range UI contract

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 - feat(rbac): complete feature delivery (Phases 1–4b)

### Summary
Full RBAC & authorization feature shipped: five-role hierarchy, session/device policy, hierarchical user management, audit logs, role-scoped dashboards, promoted-item waiter incentives, CLI root bootstrap, and automated hierarchy compliance tests.

### Backend
- `rbac.py`, `services/sessions.py`, `services/audit.py`, `services/report_access.py`
- `routers/setup.py`, `routers/root_users.py`; staff API `_reject_privileged_roles_via_staff_api` (403 on admin/root via staff endpoints)
- `scripts/seed_root.py` — production-safe first-root bootstrap
- Models: `UserSession`, `AdminAuditLog`, `Order.checked_out_by_id`, `MenuItem.is_promoted`
- Role-scoped reports, account 93-day cap, checkout/waiter attribution

### Frontend (static JS — not Next.js)
- `/setup`, `/account`, `/counter` (Admin Accounts, Staff Management, Audit Logs, Dashboard, Waiter Incentives)
- `device.js`, role-aware nav (`auth.js`), promo badges (`waiter.js`)

### Spec / Tests
- `specs/feature-rbac/` — requirements, plan, implementation, validation (synced 2026-07-04)
- `tests/test_rbac.py`, `tests/test_rbac_hierarchy.py`, `tests/test_orders_rbac.py`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 - feat/rbac-hierarchy-compliance

### Summary
Automated strict role-creation hierarchy tests; handler-level 403 enforcement for privileged roles on staff API.

### Backend
- `schemas.py`: `UserCreateRequest.role` uses `StaffRole` for handler-level checks
- `routers/users.py`: `_reject_privileged_roles_via_staff_api`

### Tests
- `tests/test_rbac_hierarchy.py` — 5 scenarios (root→admin, admin blocks, floor staff CRUD, floor staff denied, root via staff API blocked)

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 - feat/rbac-root-seed-cli

### Summary
Production-safe CLI to create the first `root` user when none exists.

### Backend
- `scripts/seed_root.py` — idempotent; default username `root`; password min 6 chars

### Tests
- `tests/test_rbac.py::test_seed_root_script_creates_first_root`

## 2026-07-04 - feat/rbac-phase4b-promoted-items

### Summary
Phase 4b: `MenuItem.is_promoted`, promoted-by-waiter reporting, Waiter Incentives dashboard (root/admin), promo badges on waiter menu.

### Backend
- `models.py`: `MenuItem.is_promoted`.
- `schemas.py`: `PromotedStaffSalesResponse`; `is_promoted` on menu schemas.
- `main.py`: lifespan `ALTER TABLE menu_items ADD is_promoted`.
- `routers/menu.py`: `toggle-promoted`; create respects `is_promoted`.
- `routers/reports.py`: `GET /api/reports/sales/promoted-by-waiter`.

### Frontend (static JS)
- `counter.html/js`: promoted checkbox, Promote button, Waiter Incentives tab.
- `waiter.js`: ★ Promo badge on menu cards.

### Tests
- `test_promoted_items_full_flow`, `test_phase4b_promoted_ui_contract`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed** (final suite count)

## 2026-07-04 - feat/rbac-complete

### Summary
**RBAC & Reporting feature delivered:** five-role hierarchy (Phases 1–4b), session policy, user management, role-scoped dashboards, audit logs, and promoted-item waiter incentives.

## 2026-07-04 - feat/rbac-phase4-dashboards

### Summary
Phase 4 UI (excl. 4b): account monthly/date-range reports, role-scoped counter dashboard staff charts, Take Orders nav for cashier/waiter.

### Backend
- `routers/reports.py`: account `monthly-sales` clips to 93-day window instead of rejecting current year.

### Frontend
- `static/account.html`, `account.js` — History tab, 93-day range, daily/monthly charts, cashier breakdown.
- `static/counter.html`, `counter.js` — Staff Performance subtab, `applyDashboardRoleVisibility`, cashier dashboard access.
- `static/auth.js` — **Take Orders** nav link (`/waiter`) for cashier/waiter only.

### Tests
- `test_phase4_dashboard_ui_contract`
- `test_account_monthly_sales_access`
- `test_cashier_cannot_access_monthly_store_sales`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **60 passed**

## 2026-07-04 - feat/rbac-audit-log-viewer

### Summary
Phase 3 UI: root-only Audit Logs tab on Counter screen, connected to `/api/root/audit-logs` with action/date filters.

### Backend
- `routers/root_users.py`: optional `action`, `start_date`, `end_date` query params on audit log list.

### Frontend
- `static/counter.html`: Audit Logs tab + filter bar + table.
- `static/counter.js`: `loadAuditLogs`, root-only tab visibility, forbidden handling.

### Tests
- `test_audit_logs_forbidden_for_non_root`
- `test_audit_logs_filter_by_action`
- `test_audit_logs_invalid_date_range`
- `test_counter_audit_log_ui_contract`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **57 passed**

## 2026-07-04 - rbac/open-decisions-resolved

### Summary
Resolved three RBAC open decisions per product owner approval: root admin-panel superset, cashier daily-only reports, audit PIN redaction.

### Spec
- `specs/feature-rbac/requirements.md` §12 → **Resolved Decisions** table; §3.1, §3.4, §7 FR-A2 updated.

### Backend
- `services/audit.py`: PIN snapshots use `"[REDACTED]"`; `pin_set` / `pin_changed` in `detail_json`.
- `routers/users.py`: pass `pin_set` on create, `pin_changed` on update.

### Tests
- `tests/test_rbac.py::test_audit_log_never_stores_plaintext_pin`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **53 passed**

## 2026-07-04 - docs/sdd-audit-sync

### Summary
SDD alignment audit: synchronized feature `implementation.md` / `validation.md` files with current codebase state; recorded gaps and technical debt honestly.

### Documentation Updates
- **Created** `specs/feature-rbac/implementation.md` (module map, API inventory, known gaps).
- **Updated** `specs/feature-rbac/validation.md` — corrected test claims; added UI implemented vs pending.
- **Updated** `specs/feature-kitchen-printing/validation.md` — 52 passed; RBAC `root+admin`; manual vs automated annotations.
- **Updated** `specs/feature-kitchen-printing/implementation.md` — RBAC wording, takeaway dispatch, test count.
- **Updated** `specs/feature-table-management/validation.md` — checked automated items; documented finalized status + root RBAC.
- **Updated** `specs/roadmap.md` — Phase 0 RBAC baseline, Step 7/8/10 status, current test count.

### Audit Findings (no code changes)
- RBAC: audit log UI, account monthly UI, cashier→waiter nav link still open.
- Table mgmt: PUT validation tests + `table_grid_updated` WebSocket in counter open.
- Kitchen printing: takeaway ticket header untested; escpos missing-host path untested.
- Root has `ADMIN_PANEL_ROLES` superset (staff API) — spec ambiguity documented in `implementation.md`.

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **52 passed** (2026-07-04).

## 2026-07-03 - feat/rbac-hierarchy

### Summary
Expanded role-based access control to five roles (`root`, `admin`, `account`, `cashier`, `waiter`), added server-side session/device policy, one-time root setup, admin audit logs, and role-scoped reporting with per-cashier/per-staff breakdowns. Removed legacy `kitchen` login role.

### Backend
- New modules: `rbac.py`, `services/sessions.py`, `services/audit.py`, `services/report_access.py`.
- New routers: `routers/setup.py` (one-time root), `routers/root_users.py` (admin CRUD + audit logs).
- Models: `UserSession`, `AdminAuditLog`, `Order.checked_out_by_id`.
- JWT now includes `jti`; single-device enforcement for `account`, `cashier`, `waiter`.
- Reports: role-scoped access, account 93-day cap, `/api/reports/sales/by-cashier`, `/api/reports/sales/by-order-staff`.
- Startup: promote legacy `admin` user to `root` when no root exists; removed auto-seed default admin.

### Frontend
- `/setup` one-time root setup page.
- `/account` read-only reports page.
- `device.js` for persistent `device_id` on login.
- Cashier may use `/waiter` screen; root treated as admin panel in counter UI.

### Spec / Docs
- Added `specs/feature-rbac/` (requirements, plan, validation).

### Test Coverage Added
- `tests/test_rbac.py` — hierarchy, sessions, setup, reports, checkout attribution.
- Updated `conftest.py`, `test_orders_rbac.py`, `test_deletion_integrity.py`.
- Validation run: `PYTHONPATH=. venv/bin/python -m pytest -q` → `52 passed`.

## 2026-06-24 - feat/kitchen-print-font-fallback

### Summary
Improved image-rendered kitchen ticket output by adding Latin/digit/punctuation fallback font support for mixed Myanmar and English ticket text.

### Backend / Assets
- Added bundled Latin fallback font support using `assets/fonts/NotoSans-Regular.ttf`.
- Added upstream OFL license at `assets/fonts/OFL-NotoSans.txt`.
- Updated image renderer to choose Myanmar font for Myanmar Unicode ranges and Latin fallback font for English labels, numbers, and punctuation.

### Spec / Docs
- Updated kitchen printing requirements, plan, validation, implementation reference, tech stack, and font README for multi-font fallback behavior.

### Test Coverage Added
- Font fallback routing coverage for mixed Myanmar/English/digit/punctuation ticket text.
- Bundled font loadability coverage for Myanmar and Latin font assets.
- Validation run: `PYTHONPATH=. venv/bin/python -m pytest -q` → `44 passed`.

## 2026-06-23 - docs/kitchen-print-font-bundle

### Summary
Bundled Noto Sans Myanmar for kitchen ticket image rendering so deployments can print Myanmar text without requiring `.env` font path configuration.

### Backend / Assets
- Added `assets/fonts/NotoSansMyanmar-Regular.ttf`.
- Added upstream OFL license at `assets/fonts/OFL-NotoSansMyanmar.txt`.
- Extended image renderer font discovery to prefer bundled fonts in `assets/fonts/` and `static/fonts/`, then system fonts, then Pillow fallback.
- Kept `KITCHEN_PRINT_FONT_PATH` as an optional deployment override.

### Spec / Docs
- Updated kitchen printing requirements, plan, validation, and implementation reference with bundled font behavior and troubleshooting notes.
- Updated `specs/tech-stack.md` and `.env.example` to clarify that bundled font auto-discovery is the default path.

### Test Coverage Added
- Bundled Myanmar font auto-discovery regression coverage in `tests/test_kitchen_printing.py`.
- Validation run: `PYTHONPATH=. pytest -q` → `41 passed`.

## 2026-06-23 - feat/kitchen-image-printing

### Summary
Extended kitchen LAN printing with server-side image render mode for Myanmar text compatibility on Xprinter/ESC/POS printers that cannot render Myanmar Unicode text directly.

### Backend Changes
- Added Pillow dependency for ticket image rendering.
- Added `render_mode` and `paper_width_px` to `kitchen_printer_settings`.
- Extended printer settings API:
  - `render_mode`: `text` | `image`
  - `paper_width_px`: `384` | `576`
- Added image renderer and ESC/POS raster payload builder.
- File backend now supports PNG preview output in image mode.
- Network backend can send raster image ESC/POS payloads in image mode.
- Existing text mode remains the default compatibility path.

### Frontend Changes
- Counter → Menu → Kitchen Printer Settings now includes:
  - render mode selector
  - paper width selector for 58mm/80mm printers

### Spec / Docs
- Updated `specs/feature-kitchen-printing/requirements.md`, `plan.md`, and `validation.md`.
- Updated `specs/roadmap.md`, `specs/tech-stack.md`, and `.env.example`.

### Test Coverage Added
- Image mode file backend writes PNG output.
- ESC/POS raster payload builder returns non-empty raster bytes.
- Settings API validates render mode and paper width.
- Validation run: `PYTHONPATH=. pytest -q` → `39 passed`.

## 2026-06-02 - feat/kitchen-lan-printing

### Summary
Implemented Step 9 kitchen LAN printing with admin category-level printer routing
(`drinks` | `food`, default `food`), configurable ESC/POS network backend for
Xprinter printers, and file backend for development without physical hardware.

### Backend Changes
- Added `Category.printer_route` column and startup migration in `main.py`.
- Extended category schemas/API:
  - `CategoryCreate`, `CategoryUpdate`, `CategoryResponse` include `printer_route`
  - `PUT /api/categories/{category_id}` for admin route updates
- Added `services/printing/` module:
  - route resolver with unknown/null → `food` fallback
  - ticket builder (single-item tickets, Myanmar text, takeaway header)
  - `file` and `escpos_network` backends
- Replaced `mock_send_to_printer` in `routers/orders.py` with `dispatch_kitchen_ticket`.
- Print dispatch remains non-blocking on order submit (`return_exceptions=True`).

### Frontend Changes
- Counter menu admin:
  - category create form includes printer route selector
  - category list shows route badge + inline route update (Save)

### Configuration
- Added `.env.example` printer settings (optional env fallback):
  - `PRINTER_BACKEND`, `PRINTER_DRINKS_HOST/PORT`, `PRINTER_FOOD_HOST/PORT`
  - optional `KITCHEN_PRINT_OUTPUT_DIR`
- **Admin UI (preferred):** Counter → Menu → Kitchen Printer Settings
  - print mode (`file` / `escpos_network`)
  - Drinks + Food counter LAN IP/port saved in database

### Backend (UI settings)
- Added `kitchen_printer_settings` + `printer_route_endpoints` tables.
- Added `GET/PUT /api/admin/kitchen-printers` (admin only).
- Print service loads backend + LAN endpoints from DB, with env fallback if host missing.

### Spec / Docs
- Added `specs/feature-kitchen-printing/` (requirements, plan, validation)
- Updated `specs/roadmap.md` Step 9 and kitchen dispatch baseline notes
- Updated `specs/tech-stack.md` orders router description

### Test Coverage Added
- `tests/test_kitchen_printing.py`:
  - route resolver defaults/unknown fallback
  - category API `printer_route` contract + 422 invalid literal
  - drinks/food file routing on mixed submit
  - unknown DB route fallback to food file
  - submit success when print dispatch raises

## 2026-04-20 - feat/table-management

### Summary
Implemented Phase 1 / Step 7 table-management enhancements on branch `feat/table-management` with finalized-order deletion safety (`paid` and `cancelled` only), historical-order detachment, realtime refresh consistency, and expanded automated coverage.

### Backend Changes
- Updated `routers/tables.py` table/zone delete safety checks to use:
  - finalized statuses: `paid`, `cancelled`
  - block condition: any linked order not in finalized set
- Refined blocked-delete API messages to clearly explain eligibility:
  - table delete now states only paid/cancelled orders permit deletion.
- Kept historical integrity behavior:
  - on successful delete, linked finalized orders are preserved and detached via `table_id = NULL`.
- Marked Step 7 status as completed in `specs/roadmap.md`.

### Frontend Changes
- No frontend code changes were required in this branch.
- Existing admin table-management UX in `static/counter.js` already provided:
  - table edit controls (rename + zone reassignment)
  - explicit table delete action with confirmation
  - user feedback paths for success and error responses

### Realtime / Refresh Changes
- Ensured table-grid refresh broadcast consistency in `routers/tables.py`:
  - `update_table` now triggers table-grid refresh after successful update.
  - `delete_table` now triggers table-grid refresh after successful delete.
  - `delete_zone` now triggers table-grid refresh after successful delete.

### Test Coverage Added/Updated
- Updated `tests/test_tables_management.py` expectations for new non-finalized delete semantics.
- Added test coverage for:
  - blocked delete when status is `completed` (treated as non-finalized/unpaid),
  - successful delete when status is `cancelled`,
  - historical detachment (`table_id = NULL`) retention for finalized rows.
- Validation runs:
  - targeted suite passed (`tests/test_tables_management.py` + `tests/test_integrity.py`)
  - full suite passed (`30 passed`).
