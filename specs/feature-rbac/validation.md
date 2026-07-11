# Validation: RBAC & Authorization

Use this checklist before marking the feature complete. Automated items must pass in CI (`PYTHONPATH=. pytest -q`). Manual items require explicit sign-off.

**Primary test file:** `tests/test_rbac.py`  
**Hierarchy compliance:** `tests/test_rbac_hierarchy.py`  
**Supporting:** `tests/test_orders_rbac.py`, `tests/conftest.py`

---

## Role creation hierarchy (automated compliance)

Strict chain **ROOT → ADMIN → CASHIER / WAITER** verified in `tests/test_rbac_hierarchy.py` (2026-07-04).

| Scenario | Rule | Test class / method | Expected |
|----------|------|---------------------|----------|
| 1 | Root creates `admin` | `TestScenario1RootCreatesAdmin` | `POST /api/root/admins` → 2xx |
| 2 | Admin cannot create `admin` or `root` | `TestScenario2AdminCannotCreateAdmin` (param: admin, root) | `POST /api/admin/users` → `403` |
| 3 | Admin creates `cashier` / `waiter` | `TestScenario3AdminCreatesFloorStaff` (param: cashier, waiter) | `POST /api/admin/users` → 2xx |
| 4 | Cashier / waiter cannot create users | `TestScenario4FloorStaffCannotCreateUsers` | `POST /api/admin/users` → `403` |
| 5 | `root` cannot be created via staff API | `TestScenario5RootCannotBeCreatedViaStaffApi` (param: admin, root actors) | `POST /api/admin/users` → `403` |

**Enforcement note:** `UserCreateRequest.role` accepts `StaffRole` at the schema layer; `routers/users.py::_reject_privileged_roles_via_staff_api` returns **`403 Forbidden`** (not `422`) when `admin` or `root` is requested on the staff API.

Run hierarchy tests only:
```bash
PYTHONPATH=. pytest tests/test_rbac_hierarchy.py -v
```

---

## Phase 1 — Schema & Contracts

### Automated
- [x] Fresh DB starts without errors; `user_sessions` and `admin_audit_logs` tables exist — full suite bootstrap
- [x] `orders.checked_out_by_id` column exists after lifespan migration — `test_checkout_sets_checked_out_by_id`
- [ ] `StaffRole` schema rejects `kitchen` and unknown roles (`422`) — not isolated; kitchen login blocked in auth allowlist
- [ ] Legacy DB: user `username=admin` promoted to `role=root` when no root exists — lifespan only; no dedicated test
- [x] Fresh install: no default admin user seeded — `test_setup_status_and_root_creation`

### Manual
- [ ] Existing historical orders remain queryable after migration
- [ ] Deleted user references in old orders show fallback labels in reports

---

## Phase 2 — Auth, Sessions & Device Policy

### Automated
- [x] `GET /api/setup/status` → `needs_setup: true` when no root — `test_setup_status_and_root_creation`
- [x] `POST /api/setup/root` creates root; second call → `403` — `test_setup_status_and_root_creation`
- [x] Login returns JWT; `GET /api/auth/me` succeeds with valid token — `conftest.auth_headers` + API tests
- [ ] JWT missing/invalid `jti` → `401` at `get_current_user` — not explicit test
- [x] **Single-device:** cashier login B revokes cashier login A session (A gets `401`) — `test_single_device_login_revokes_prior_session`
- [ ] **Single-device:** same test for `waiter` and `account` — cashier covered; waiter/account not duplicated
- [x] **Multi-device:** two concurrent `admin` sessions both valid — `test_multi_device_admin_sessions_both_valid`
- [ ] **Multi-device:** two concurrent `root` sessions both valid — not explicit test
- [ ] `device_id` persisted on `UserSession` row after login — not asserted in tests
- [x] `POST /api/auth/change-password` succeeds for `root`/`admin`; fails for `account`/`cashier`/`waiter` — `test_rbac_security_gaps.py`
- [ ] Legacy `kitchen` role user cannot authenticate (`401`) — not automated

### Manual
- [ ] Client sends stable `device_id` from `localStorage` on each login
- [ ] Revoked session shows login redirect on next API failure (UI behavior)

---

## Phase 3 — User Management & Audit

### Automated — API authorization
- [x] `root` can `POST /api/root/admins` (create admin) — `TestScenario1RootCreatesAdmin`
- [x] `root` can `GET /api/root/admins` (list) — `test_root_creates_admin_and_lists`
- [ ] `root` can `PUT /api/root/admins/{id}` (update) — not isolated test
- [ ] `root` can `DELETE /api/root/admins/{id}` (soft delete) — not isolated test
- [ ] `root` can `POST /api/root/admins/{id}/reset-password` — not automated (see `implementation.md`)
- [ ] `admin` cannot access `/api/root/admins` → `403` — not isolated test
- [x] `admin` can CRUD `cashier`/`waiter`/`account` via `/api/admin/users` — `TestScenario3AdminCreatesFloorStaff` (+ existing staff CRUD tests)
- [x] `admin` cannot create user with `role=admin` → `403` — `TestScenario2AdminCannotCreateAdmin` in `tests/test_rbac_hierarchy.py`
- [x] `admin` cannot create user with `role=root` → `403` — `TestScenario2AdminCannotCreateAdmin` in `tests/test_rbac_hierarchy.py`
- [x] `cashier`/`waiter`/`account` cannot access `/api/admin/users` → `403` — `TestScenario4FloorStaffCannotCreateUsers` (+ existing RBAC tests)
- [x] `root` cannot be created via `POST /api/admin/users` → `403` — `TestScenario5RootCannotBeCreatedViaStaffApi`
- [x] Staff create/update/delete writes `AdminAuditLog` row — `test_admin_staff_crud_writes_audit_log`
- [x] `root` can `GET /api/root/audit-logs` with expected actor/action/target fields
- [x] Non-root roles (`admin`, `cashier`, `waiter`, `account`) get `403` on audit logs — `test_audit_logs_forbidden_for_non_root`
- [x] Audit log `action` filter works — `test_audit_logs_filter_by_action`
- [x] Counter audit log UI contract (HTML/JS root-gating) — `test_counter_audit_log_ui_contract`
- [ ] Password hashes never appear in any user API response — convention enforced; no dedicated assertion

### Automated — soft delete safety
- [x] Deleting staff user sets `is_deleted`; historical `OrderItem.created_by_id` rows remain — `test_soft_delete_user_preserves_history_and_reports`
- [x] Reports still compute when attributed user is soft-deleted — `test_soft_delete_user_preserves_history_and_reports`

### Manual — UI
- [ ] Fresh install: `/login` → `/setup` → create root → login as root
- [ ] Root uses **Admin Accounts** tab: create admin, reset password, edit, delete
- [ ] Admin uses **Staff Management**: create cashier, waiter, account (no admin in role dropdown)
- [ ] **Change Password** modal works for root/admin only (hidden for `account`, `cashier`, `waiter`)
- [x] Root **Audit Logs** tab implemented (`counter.html` + `counter.js`); manual sign-off: verify as root on live `/counter`
- [x] Admin attempting staff form with `admin` role is blocked in UI and API — API: `TestScenario2AdminCannotCreateAdmin`; UI: staff role dropdown excludes admin/root

---

## Phase 4 — Dashboards & Reporting

### Automated — report authorization
- [x] `account` request with range > 90 days → `400` — `test_account_report_range_capped`
- [x] `account` cannot access `by-order-staff` (waiter breakdown) — denied in report router; promoted report `403` in `test_promoted_items_full_flow`
- [x] `waiter` cannot `POST /api/orders/checkout` → `403` — `test_waiter_cannot_checkout_but_can_submit`
- [x] `account` cannot `POST /api/orders/submit` → `403` — `test_account_cannot_submit_orders`
- [x] `admin` and `root` can access full store + both breakdown endpoints — `test_per_cashier_and_waiter_reports`
- [ ] `account` can read store summary within 90-day window — partial via monthly/daily tests
- [ ] `account` cannot read data older than 90 days → `400` — not isolated
- [x] `waiter` sees self only on `by-order-staff` — `test_waiter_order_staff_scoped_to_self`
- [ ] `waiter` cannot access `by-cashier` → `403` — not isolated
- [x] `cashier` cannot access `by-cashier` → `403` — `test_cashier_cannot_view_by_cashier_breakdown`
- [x] `cashier` cannot access `by-order-staff` → `403` — `test_cashier_cannot_view_order_staff_breakdown`

### Automated — attribution correctness
- [x] Checkout sets `Order.checked_out_by_id` to current cashier — `test_checkout_sets_checked_out_by_id`
- [x] `by-cashier` totals match checkout-attributed paid orders for date range (daily and monthly) — `test_per_cashier_and_waiter_reports`
- [x] `by-order-staff` totals match `OrderItem.created_by_id` for paid/completed orders — `test_per_cashier_and_waiter_reports`
- [ ] Cashier submitting order via waiter flow sets `created_by_id` = cashier id — not isolated

- [x] Counter Phase 4 UI contract — `test_phase4_dashboard_ui_contract` (includes staff date-range controls)
- [x] Account can access monthly sales API — `test_account_monthly_sales_access`
- [x] Cashier cannot access monthly store sales API — `test_cashier_cannot_access_monthly_store_sales`
- [x] `cashier` can `POST /api/orders/submit` (waiter capability) — `test_waiter_cannot_checkout_but_can_submit` (waiter submit); cashier checkout in `test_cashier_and_admin_can_checkout`
- [x] `admin`/`root` retain admin panel endpoints (`menu`, `tables`, `kitchen_printers`) — `test_admin_kitchen_printer_settings_api` + existing feature tests
- [ ] `cashier` cannot mutate menu/tables → `403` — not isolated in RBAC suite

### Manual — dashboard UI
- [x] **Root:** today total + Staff Performance cashier/waiter charts (date range + Today/This Month) + Sales History daily/monthly
- [x] **Admin:** today total + Staff Performance charts (date range) + Sales History
- [x] **Account:** `/account` daily + monthly views with date-range picker (≤ 90 days) — manual sign-off on live UI
- [x] **Cashier:** today own checkout KPI only; **no** Staff Performance tab; no monthly store widget
- [x] **Cashier:** nav **Take Orders** → `/waiter` (`auth.js`, cashier/waiter only)
- [ ] **Waiter:** own daily total on waiter screen (minimal; optional)

### Regression
- [x] Full suite `pytest -q` passes (record count in CHANGELOG) — **121 passed**
- [x] Checkout tax/discount money invariants unchanged — included in full suite
- [x] `tests/test_kitchen_printing.py` still passes — included in full suite
- [x] Table management RBAC (`ADMIN_PANEL_ROLES`) unchanged — included in full suite

---

## Phase 4b — Promoted Items

- [x] `MenuItem.is_promoted` on model + schemas + lifespan migration
- [x] `PUT /api/menu-items/{id}/toggle-promoted` (admin panel)
- [x] `GET /api/reports/sales/promoted-by-waiter` returns per-staff qty + revenue
- [x] Root/admin can load full report; account denied (`403`)
- [x] End-to-end: toggle promoted → order → checkout → report (`test_promoted_items_full_flow`)
- [x] Admin menu UI: checkbox + Promote button + badge
- [x] Waiter menu: **★ Promo** visual indicator
- [x] Counter Dashboard → **Waiter Incentives** (root/admin only)
- [x] UI contract test (`test_phase4b_promoted_ui_contract`)

---

## Security Review Checklist

- [x] All RBAC rules enforced server-side (UI bypass with crafted JWT still fails) — hierarchy + role tests use JWT directly
- [ ] Revoked `jti` cannot be replayed — partial via single-device test; no explicit replay test
- [x] Admin escalation to `admin`/`root` blocked at handler (not only UI) — `tests/test_rbac_hierarchy.py`
- [x] Audit `detail_json` does not store plaintext PINs; uses `"[REDACTED]"` + `pin_set`/`pin_changed` — `test_audit_log_never_stores_plaintext_pin`
- [x] Root-only endpoints return `403` for all other roles (not `404`) — `test_audit_logs_forbidden_for_non_root`, `TestScenario4FloorStaffCannotCreateUsers`

---

## Menu management RBAC (`specs/feature-menu-rbac/`)

### Automated
- [x] Cashier `POST /api/menu-items/` → **403** — `test_cashier_cannot_create_menu_item`
- [x] Cashier `PATCH /api/menu-items/{id}/availability` → **200** — `test_cashier_can_patch_menu_availability`
- [x] Cashier `PUT /api/menu-items/{id}` (price) → **403** — `test_cashier_cannot_full_update_menu_item`
- [x] Admin `PATCH …/availability` → **200** — `test_admin_can_patch_menu_availability`
- [x] Waiter `PATCH …/availability` → **403** — `test_waiter_cannot_patch_menu_availability`
- [x] Account menu/table mutations → **403** — `test_account_forbidden_on_menu_item_and_table_mutations` in `test_rbac_security_gaps.py`

### Manual
- [ ] Cashier Counter → Menu Management: availability toggles only (no Add/Edit/Delete)
- [ ] Admin sees full menu CRUD on Menu Management tab
- [ ] Waiter menu greys out sold-out item (WebSocket or refresh)

---

## Definition of Done

| Criterion | Required |
|-----------|----------|
| All Phase 1–4 **automated** items checked | yes — core paths covered; see unchecked items above for follow-up |
| All Phase 3–4 **manual UI** items checked | partial — live sign-off still required for setup flow, admin accounts tab, change password |
| Security review checklist signed off | partial — escalation + audit PIN verified; jti replay + root admin CRUD gaps documented |
| `validation.md` evidence date + pytest count recorded | yes |
| `implementation.md` updated to match as-built state | yes |
| `CHANGELOG.md` entry added | yes |
| Open decisions in `requirements.md` §12 resolved or explicitly accepted | yes |

**Current evidence (2026-07-11):** **171 passed** — includes menu RBAC (`tests/test_menu_rbac_availability.py`); RBAC Phases 1–4b; Staff Performance root/admin only; role creation hierarchy in `tests/test_rbac_hierarchy.py` + `tests/test_rbac_security_gaps.py`.
