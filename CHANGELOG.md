# Changelog

## 2026-07-12 — Pre-E2E system audit (SDD sync)

### Summary
Documentation and frontend health check against current Cashier 3-pane / Waiter two-pane reality. No new product features. Specs updated for modal/pane wording; waiter legacy sidebar DOM fallbacks removed; full pytest green (181).

### Spec
- Synced pane/modal language across walk-in, cancellation, cart-breakdown, payment-method, table-all-view, api-reference, menu-item-tax/discount
- Added `feature-menu-item-tax/implementation.md` and `feature-payment-method-analytics/implementation.md` (explicitly notes **No Receipt / tax exemption is not implemented**)

### Frontend
- `static/waiter.js` — removed orphaned `#waiter-table-details-sidebar` / backdrop fallbacks; modal-only open/close

### Tests
- `pytest`: 181 passed

## 2026-07-12 — Cashier 3-pane billing layout

### Summary
Cashier / Billing is a single-page **Tables | Takeaways | Check Out** grid. Selecting an occupied table or takeaway fills the right pane without a modal; checkout controls and listeners stay intact.

### Spec
- `specs/feature-cashier-three-pane/`
- Updated `specs/feature-counter-ui/requirements.md`

### Frontend
- `static/counter.html` — `#pane-tables`, `#pane-takeaways`, `#pane-checkout`
- `static/counter.js` — selection highlighting; `selectOrder(order, source)`

## 2026-07-12 — Waiter two-pane layout & active-order modal

### Summary
Waiter screen splits into Menu+Cart (left) and Tables/Takeaways (right). Occupied tables and active takeaways open a centered pop-out modal so viewing an order never overrides the new-order cart.

### Spec
- `specs/feature-waiter-two-pane-layout/`
- Updated `specs/feature-waiter-cart-breakdown/` (FR-WB1b)

### Frontend
- `static/waiter.html` — tinted two panes; `#active-order-modal`
- `static/waiter.js` — modal open/close; available tables set cart context only

## 2026-07-11 — Waiter cart footer: Submit below price breakdown

### Summary
Cart sidebar groups price breakdown and Submit Order at the bottom so waiters review totals before confirming.

### Spec
- Updated `specs/feature-waiter-cart-breakdown/requirements.md` (FR-WB1b), `implementation.md`, `validation.md`

### Frontend
- `static/waiter.html` — `#cart-footer` with breakdown then `#submit-order`; table selection moved above footer

## 2026-07-11 — Table grid status labels (Free + compact typography)

### Summary
Floor grid cards show **Free** instead of raw `available` / `AVAILABLE`, with smaller status text so table names stand out.

### Spec
- Updated `specs/feature-table-all-view/requirements.md` (FR-TA5), `implementation.md`, `validation.md`

### Frontend
- `static/table-display.js` — `displayTableStatus()`, typography helpers
- `waiter.js`, `counter.js`, `table-dashboard.js` — consistent status rendering

## 2026-07-11 — Payment method analytics (Cash vs Mobile Money)

### Summary
Checkout requires and persists `payment_method` (`cash` | `mobile_money`). Dashboard Overview shows today/monthly sales split by payment method for reconciliation.

### Spec
- `specs/feature-payment-method-analytics/`
- Updated `specs/database-schema.md`, `specs/api-reference.md`, `specs/feature-counter-ui/requirements.md`

### Backend
- `OrderCheckoutRequest` validates/normalizes payment method
- `GET /api/analytics/sales-breakdown` — today + current month totals by payment method (`routers/analytics.py`)

### Frontend
- `counter.html` / `counter.js` — Cash/Mobile Money toggle buttons at checkout; payment breakdown cards on Dashboard Overview

### Tests
- `tests/test_payment_method_analytics.py` (4 scenarios)

## 2026-07-11 — Cashier takeaway display & order waiter attribution

### Summary
Walk-in takeaway orders no longer show "Deleted Table" / "Unknown" in the Cashier UI. Orders track who opened them via `Order.created_by_id`; API exposes `waiter_name` and Cashier checkout shows **Served by: [Name]**.

### Spec
- Updated `specs/database-schema.md`, `specs/feature-walk-in-takeaway/requirements.md`, `specs/api-reference.md`

### Backend
- `Order.created_by_id` FK + startup migration/backfill from earliest order item
- `waiter_name` / `served_by_name` on `OrderResponseDetail`, `OrderDetailsResponse`, `ActiveTakeawayOrderResponse`
- Set `created_by_id` on new orders in `POST /api/orders/submit` and `POST /api/orders/`

### Frontend
- `static/counter.js` — `cashierOrderDisplayLabel()`, `orderServedByLabel()` for takeaway list + checkout modal

### Tests
- Extended `tests/test_walk_in_takeaway.py` (order + active-takeaways `waiter_name`)

## 2026-07-11 — Table ALL view & compact table names

### Summary
Waiter, Cashier, and Table Dashboard floor grids default to an **ALL** zone tab showing every table in a dense responsive grid. UI strips leading `"Table "` from dine-in labels (e.g. `Table G1` → `G1`); takeaway labels unchanged.

### Spec
- `specs/feature-table-all-view/`
- Updated `specs/feature-table-management/requirements.md`, `specs/api-reference.md`

### Frontend
- `static/table-display.js` — shared `displayTableName()`
- `waiter.js`, `counter.js`, `table-dashboard.js` — ALL tab + grid density + formatted labels

### Tests
- `tests/test_table_all_view.py`

## 2026-07-11 — Menu management RBAC (admin vs cashier availability)

### Summary
Admins retain full menu CRUD. Cashiers may toggle sold-out/in-stock via `PATCH /api/menu-items/{id}/availability` only. Counter Menu Management tab shows availability-only UI for cashiers.

### Spec
- `specs/feature-menu-rbac/`
- Updated `specs/feature-rbac/requirements.md`, `specs/feature-menu-items/requirements.md`, `specs/api-reference.md`

### Backend
- `MENU_AVAILABILITY_ROLES` in `rbac.py`
- `MenuItemAvailabilityUpdate` schema; `PATCH /api/menu-items/{item_id}/availability`

### Frontend
- `counter.html` / `counter.js` — cashier stock toggles; admin-only sections hidden

### Tests
- `tests/test_menu_rbac_availability.py`

## 2026-07-06 — Menu category navigation pills (Counter + Waiter)

### Summary
Category ALL + per-category pills for client-side menu filtering. Counter Menu Management list gains tabs; waiter grid behavior documented (already implemented).

### Spec
- `specs/feature-menu-category-navigation/`

### Frontend
- `counter.html` / `counter.js` — `#menu-category-tabs`, `filterMenu()`, `hidden` row filter
- Waiter: existing `#category-tabs` in `waiter.js` (unchanged)

### Tests
- `tests/test_menu_category_navigation.py`; full suite **166 passed**

## 2026-07-06 — Predefined instruction quick tags

### Summary
Waiters can tap predefined instruction chips in the special-instructions modal; admins manage tags from Menu Management.

### Spec
- `specs/feature-predefined-instructions/`

### Backend
- `PredefinedInstruction` model; CRUD at `/api/predefined-instructions`
- Default Myanmar seed tags on empty table

### Frontend
- `waiter.html` / `waiter.js` — chip buttons append to textarea
- `counter.html` / `counter.js` — admin add/delete tags

### Tests
- `tests/test_predefined_instructions.py`; full suite **165 passed**

## 2026-07-06 — Spec/code baseline audit (SDD sync)

### Summary
Synchronized `specs/` with the current working codebase. Added canonical `database-schema.md` and `api-reference.md`. No new product features.

### Spec updates
- `tech-stack.md`, `mission.md`, `roadmap.md` — pricing, roles, router list, test count (160)
- Feature specs: menu discount/tax, waiter breakdown, walk-in takeaway, RBAC validation (90-day cap)
- New: `feature-menu-item-discount/implementation.md`, `validation.md`; `feature-waiter-cart-breakdown/implementation.md`

### Code cleanup
- Removed unused `_base_price_with_discount()` from `routers/orders.py`

## 2026-07-06 — Per-item menu discount + tax-after-discount pricing

### Summary
Menu items support `discount_type` (`none` / `percentage` / `fixed`) and `discount_value`. Standard POS math: tax is applied on the **discounted** price. Waiter cart shows per-item breakdown (Base | Disc | Tax) and footer includes Total Discount.

### Spec
- `specs/feature-menu-item-discount/` — new requirements
- `specs/feature-menu-pricing/`, `specs/feature-menu-item-tax/`, `specs/feature-waiter-cart-breakdown/` — updated formulas

### Backend
- `MenuItem.discount_type`, `MenuItem.discount_value`; `OrderItem.unit_discount_at_sale`
- `_calculate_order_line_pricing()` — discount then tax; legacy `discount_price` migrated at runtime
- `breakdown_discount_total` on order details / active takeaways; per-item `unit_discount_at_sale` in responses

### Frontend
- `waiter.html` / `waiter.js` — item-level breakdown rows, Total Discount footer row, sidebar item pricing

### Tests
- `tests/test_menu_item_discount.py` — 10% discount + 5% tax on discounted price; grand total formula
- Full suite **160 passed**

## 2026-07-06 — Waiter cart price breakdown (Subtotal / Tax / Grand Total)

### Summary
Waiter cart footer and active-order sidebar show a 3-line price breakdown. Backend `GET /api/orders/{id}/details` returns `breakdown_subtotal`, `breakdown_tax_total`, `breakdown_grand_total`.

### Spec
- `specs/feature-waiter-cart-breakdown/`

### Backend
- `_order_price_breakdown()`; fields on `OrderDetailsResponse` and `ActiveTakeawayOrderResponse`
- `unit_price_at_sale` on `OrderItemDetailsResponse`

### Frontend
- `waiter.html` / `waiter.js` — cart summary + order details sidebar breakdown; live update on takeaway toggle

### Tests
- `tests/test_waiter_cart_breakdown.py` — **1 passed**; full suite **157 passed**

## 2026-07-06 — Per-item tax on menu items

### Summary
Menu items support `tax_type` (`none` / `percentage` / `fixed`) and `tax_value`. Tax is calculated on the active base price (dine-in vs takeaway) at order submit and included in line subtotals. Checkout sums per-line tax for receipt display; legacy 5% global tax replaced.

### Spec
- `specs/feature-menu-item-tax/` — requirements + validation
- `specs/tech-stack.md` — updated checkout tax rules
- `specs/feature-menu-pricing/` — cross-reference

### Backend
- `MenuItem.tax_type`, `MenuItem.tax_value`; `OrderItem.unit_tax_at_sale`
- `_calculate_order_line_pricing()` in `routers/orders.py`
- Checkout uses sum of line taxes (no global 5%)

### Frontend
- `counter.html` / `counter.js` — Tax Type + Tax Value on menu form; checkout tax from lines
- `waiter.js` — `computeUnitTax()` in cart/display pricing

### Tests
- `tests/test_menu_item_tax.py` — **3 passed**; full suite **156 passed**

## 2026-07-06 — Auto-clear empty takeaway orders (last item cancel)

### Summary
When the last active item is cancelled, the order auto-transitions to `cancelled`. Cancelled takeaways are excluded from `active-takeaways` and removed from the UI via `order_cancelled` WebSocket. Waiter cart/sidebar dismisses automatically.

### Spec
- `specs/feature-order-cancellation/` — FR-C4 auto-clear behavior
- `specs/feature-walk-in-takeaway/` — active list removal documented

### Backend
- `_release_table_if_order_fully_cancelled` returns auto-cancel flag; broadcasts `order_cancelled` on full clear
- `GET /api/orders/active-takeaways` excludes `cancelled` orders

### Frontend
- `waiter.js` — `handleRemoteOrderClosed`, always refresh takeaway list; dismiss cart/sidebar
- `counter.js` — only clear checkout on cancelled/paid takeaway updates

### Tests
- `test_last_takeaway_item_cancel_auto_clears_from_active_list` — **passed**; full suite **153 passed**

## 2026-07-06 — Takeaway item-level cancel parity (corrects whole-order UI)

### Summary
Walk-in takeaway now mirrors dine-in for **item-level** cancellation: clicking an active takeaway card opens the order details sidebar with per-item Cancel controls. Removed "Cancel Entire Order" buttons from waiter/cashier UI. Customer name prompt uses modal or native `prompt()` fallback.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W6/W7: view order sidebar + item cancel parity
- `specs/feature-order-cancellation/` — reframed as item-level primary UX

### Frontend
- `waiter.js` — takeaway card → `openOrderDetails()`; `promptForCustomerName()`; removed whole-order cancel UI
- `counter.js` / `counter.html` — removed cashier Cancel Order button

### Tests
- `tests/test_walk_in_takeaway.py::test_cancel_takeaway_order_item_without_table` — **passed**

## 2026-07-06 — Walk-in customer prompt & whole-order cancellation

### Summary
Walk-in Takeaway button now prompts for optional customer name. New `POST /api/orders/{order_id}/cancel` cancels active orders, frees tables, and broadcasts realtime updates. Cancel Order buttons on waiter cart/sidebar and cashier checkout.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W4 customer name prompt
- `specs/feature-order-cancellation/` — cancel flow requirements + validation

### Backend
- `POST /api/orders/{order_id}/cancel` — cancel items + order, release table, WebSocket (`order_updated`, `takeaways_updated`, `table_status_changed`)
- Verified `customer_name` on `OrderCreate` / submit (unchanged)

### Frontend
- `waiter.js` — walk-in name prompt; Cancel Order in cart (append) + order details sidebar
- `counter.js` — Cancel Order on checkout panel

### Tests
- `tests/test_order_cancellation.py` — **3 passed**; full suite **151 passed**

## 2026-07-06 — Walk-in takeaway append mode

### Summary
Active walk-in takeaway orders are clickable on the waiter dashboard. Clicking opens cart **Append Mode** bound to `order_id`. `POST /api/orders/submit` accepts optional `order_id` to add batches without creating a duplicate order.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W6 append parity with occupied tables

### Backend
- `schemas.OrderSubmitRequest.order_id` optional
- `routers/orders.py` — takeaway append lookup (`table_id IS NULL`, open/dining)

### Frontend
- `waiter.js` — `activateTakeawayAppendContext()`, submit sends `order_id`, header "Adding to Takeaway: …"

### Tests
- `tests/test_walk_in_takeaway.py` — +2 scenarios; full suite green

## 2026-07-06 — Direct walk-in takeaway (`table_id = NULL`)

### Summary
Walk-in takeaway orders use no physical table. Waiter attribution via `OrderItem.created_by_id` from JWT session. UI adds **[ + Walk-in Takeaway ]** button; Cashier/kitchen display **🛍️ Takeaway #\<id\>**. Cart items default `is_takeaway=true` with dual pricing.

### Spec
- `specs/feature-walk-in-takeaway/` — requirements, plan, implementation, validation
- Audited: no dummy-table / `is_takeaway_zone` logic in codebase

### Backend
- Verified nullable `table_id` + `created_by_id` on submit; kitchen ticket header `Takeaway #<id>`
- `new_order_batch` WebSocket includes `order_type`

### Frontend
- `waiter.html` / `waiter.js` — walk-in button, cart defaults
- `counter.js` — `formatTakeawayOrderLabel`, cashier takeaway list/checkout headers
- `table-dashboard.html` / `table-dashboard.js` — active walk-in takeaway panel (kitchen board)

### Tests
- `tests/test_walk_in_takeaway.py` — **4 passed**; full suite **146 passed**

## 2026-07-06 — Dual pricing (dine-in vs takeaway per line)

### Summary
Menu items can have an optional `takeaway_price`. Order lines accept `is_takeaway`; server resolves unit price (takeaway price when set, else dine-in base). Waiter cart shows a per-line 🛍️ Takeaway checkbox with live subtotal updates.

### Spec
- `specs/feature-menu-pricing/` — requirements, plan, implementation, validation

### Backend
- `models.py` — `MenuItem.takeaway_price`, `OrderItem.is_takeaway`
- `schemas.py`, `routers/orders.py`, `routers/menu.py`, `main.py` migrations

### Frontend
- `static/counter.html`, `static/counter.js` — optional Takeaway Price on menu form
- `static/waiter.js` — per-line takeaway toggle + dynamic pricing

### Tests
- `tests/test_menu_dual_pricing.py` — **4 passed**; full suite **142 passed**

## 2026-07-06 — Counter primary nav highlighting & category edit modal

### Summary
Dashboard, Cashier/Billing, and Menu Management tabs use enhanced primary styling. Category rename uses a modal instead of `window.prompt`; Edit/Delete were already wired to backend CRUD.

### Spec
- `specs/feature-counter-ui/requirements.md` (new) — FR-N1–FR-N3 primary nav UX
- `specs/feature-category-crud/` — FR-3/FR-4 UI modal + full CRUD matrix

### Frontend
- `static/counter.html` — `.tab-btn-primary` styles; `#category-edit-modal`
- `static/counter.js` — `openCategoryEditModal`, `bindCategoryEditModal`

### Backend
- No API changes (`PUT`/`DELETE` `/api/categories/{id}` already in `routers/menu.py`)

### Tests
- `tests/test_category_crud.py` — **5 passed**; full suite **138 passed**

## 2026-07-06 — Strict password vs PIN login separation

### Summary
Password roles (`root`, `admin`) and PIN roles (`account`, `cashier`, `waiter`) are enforced at login endpoints with explicit **403** responses when the wrong auth method is used.

### Backend
- `routers/auth.py` — `/login` rejects PIN roles; `/login-pin` rejects password roles

### Frontend
- `static/login.js`, `static/pin-login.js` — surface 403 detail messages
- `static/auth.js` — Change Password hidden for PIN roles; export `PIN_ROLES`
- `static/counter.js` — staff form PIN field toggled by role

### Tests
- `tests/test_rbac_security_gaps.py`, `tests/test_rbac.py` — strict login rejection cases
- `tests/test_integrity.py` — fix isolated-run summary assertion
- Full suite: **138 passed** (`PYTHONPATH=. python -m pytest -q`)

## 2026-07-06 — Account role PIN-only authentication (SDD alignment)

### Summary
`account` is now a PIN-based role like `cashier`/`waiter`. Only `root` and `admin` use username + password. Change Password is forbidden for `account`.

### Spec
- `specs/feature-rbac/` — auth matrix, change-password contract, validation checklist
- `specs/feature-account-reports/` — login, provisioning, validation updated

### Backend
- `rbac.py` — `PIN_ROLES` includes `account`; `PASSWORD_ROLES` is `root`/`admin` only
- `routers/auth.py` — change-password `403` for account; login-pin accepts account
- `routers/users.py` — account requires `pin_code`; rejects `password` on staff API

### Frontend
- `static/auth.js`, `static/login.js` — Change Password / password login for `root`/`admin` only
- `static/pin-login.js` — account logs in via PIN → `/account`
- `static/counter.js`, `counter.html` — staff form uses PIN for all roles including account

### Tests
- `tests/test_rbac_security_gaps.py` — account in forbidden change-password cases
- `tests/test_rbac.py` — account PIN provisioning + session tests
- Full suite: **123 passed** (`PYTHONPATH=. python -m pytest -q`)

## 2026-07-05 — Multi-cashier real-time checkout sync

### Summary
When one cashier checks out a table or takeaway order, all other open cashier Counter sessions refresh immediately (table grid, takeaway list, and stale receipt cleared).

### Backend
- `routers/orders.py` — broadcast `order_updated` on checkout alongside `order_completed`

### Frontend
- `static/counter.js` — handle `order_completed`, `takeaways_updated`, and paid `order_updated` via shared `handleRemoteOrderClosed`

### Tests
- Full suite: **121 passed** (`PYTHONPATH=. python -m pytest -q`)

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

## 2026-07-04 — Menu soft delete, category CRUD, and counter UI (`feat/ui-updates` merged)

### Menu item soft delete
- `DELETE /api/menu-items/{id}` sets `is_deleted=true`; blocks when item is on an active unpaid order (`400`).
- Waiter/counter lists use `GET /api/menu-items/` (`is_deleted=false` only).
- Tests: `tests/test_menu_item_soft_delete.py`, `tests/test_sales_integrity.py`

### Category delete fix
- Category delete counts only active menu items (`is_deleted=false`).
- Category with only soft-deleted items can be deleted.
- Tests: `tests/test_category_crud.py`

### Counter UI
- Main navigation active tab state (`setActiveMainTab` in `counter.js`).
- Docs: `specs/feature-menu-items/`, `specs/feature-category-crud/`, `specs/feature-counter-ui/`

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
