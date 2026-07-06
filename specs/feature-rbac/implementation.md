# Implementation Reference: RBAC Hierarchy

Records the **current** RBAC implementation as of 2026-07-04. Use with `requirements.md` and `validation.md`.

> **Stack note:** This project uses **FastAPI + static JavaScript** (not Next.js). Frontend guards are convenience only; server enforces all rules.

## 1. Role Constants (`rbac.py`)

| Constant | Values |
|----------|--------|
| `ALL_ROLES` | `root`, `admin`, `account`, `cashier`, `waiter` |
| `PASSWORD_ROLES` | `root`, `admin` |
| `PIN_ROLES` | `cashier`, `waiter`, `account` |
| `SINGLE_DEVICE_ROLES` | `account`, `cashier`, `waiter` |
| `MULTI_DEVICE_ROLES` | `root`, `admin` |
| `uses_single_device_sessions()` / `uses_multi_device_sessions()` | Session policy helpers in `rbac.py`; used by `services/sessions.py` |
| `ADMIN_PANEL_ROLES` | `root`, `admin` |
| `POS_ORDER_ROLES` | `root`, `admin`, `cashier`, `waiter` |
| `CHECKOUT_ROLES` | `root`, `admin`, `cashier` |
| `FULL_REPORT_ROLES` | `root`, `admin`, `account` |
| `ADMIN_MANAGEABLE_ROLES` | `cashier`, `waiter`, `account` |
| `ACCOUNT_MAX_REPORT_DAYS` | `90` (align from `93` on next implementation pass) |

Legacy `kitchen` login role is removed from schemas and login allowlists. Existing `kitchen` DB rows cannot authenticate.

## 2. Data Model Additions (`models.py`)

| Entity / column | Purpose |
|-----------------|---------|
| `UserSession` | `jti`, `device_id`, `revoked_at` — JWT session validation |
| `AdminAuditLog` | Admin staff CRUD audit trail (root-readable) |
| `Order.checked_out_by_id` | Per-cashier checkout attribution |
| `MenuItem.is_promoted` | Waiter incentive / promoted-item reporting flag |

## 3. API Surface

### Setup (one-time)
| Method | Path | Access |
|--------|------|--------|
| `GET` | `/api/setup/status` | Public |
| `POST` | `/api/setup/root` | Public only when no root exists |

### Auth
| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/auth/login` | Password roles; accepts `device_id` |
| `POST` | `/api/auth/login-pin` | PIN roles; accepts `device_id` |
| `GET` | `/api/auth/me` | Validates JWT + active session |
| `POST` | `/api/auth/change-password` | `root`, `admin` only — `403` for PIN roles (`account`, `cashier`, `waiter`) |

### Root admin management
| Method | Path | Access |
|--------|------|--------|
| `GET` | `/api/root/admins` | `root` |
| `POST` | `/api/root/admins` | `root` |
| `PUT` | `/api/root/admins/{id}` | `root` |
| `DELETE` | `/api/root/admins/{id}` | `root` |
| `POST` | `/api/root/admins/{id}/reset-password` | `root` |
| `GET` | `/api/root/audit-logs` | `root` — query: `action`, `start_date`, `end_date`, `limit` |

### Staff management (admin panel)
| Method | Path | Access |
|--------|------|--------|
| `GET/POST/PUT/DELETE` | `/api/admin/users` | `ADMIN_PANEL_ROLES`; admin restricted to `ADMIN_MANAGEABLE_ROLES` |

## 3.1 Hierarchy enforcement audit (2026-07-04)

Strict chain: **ROOT → ADMIN → CASHIER / WAITER** (plus `account` under admin for finance).

| Rule | Enforced? | Mechanism |
|------|-----------|-----------|
| Admin cannot create `admin` or `root` | **Yes** | `UserCreateRequest.role` = `StaffRole`; `routers/users.py::_reject_privileged_roles_via_staff_api` → `403` |
| Only root creates `admin` | **Yes** | `POST /api/root/admins` requires `ROLE_ROOT`; body has no `role` field — server sets `role=admin` |
| Admin creates `cashier` / `waiter` | **Yes** | `POST /api/admin/users` with `ADMIN_MANAGEABLE_ROLES`; PIN required for PIN roles |
| Root cannot create `admin` via staff API | **Yes** | `_validate_staff_body` rejects `role=admin` with `400` even for root actor |
| Root cannot create another `root` | **Yes** | No API accepts `role=root` on create; setup/seed only when zero roots exist |

**Tests:** `tests/test_rbac_hierarchy.py` (5 scenarios), `test_admin_cannot_create_admin`, `test_root_creates_admin_and_lists`, `test_setup_status_and_root_creation`.

## 3.2 First root bootstrap

| Method | Path / script | When | Production use |
|--------|---------------|------|----------------|
| **CLI (canonical)** | `scripts/seed_root.py` | No non-deleted `root` in DB | **Recommended** |
| HTTP setup API | `POST /api/setup/root` | No root exists | Dev / pytest only |
| Setup UI | `/setup` | `needs_setup: true` | Dev only — not for production |
| Lifespan migration | `main.py` | No root + legacy `username=admin` | One-time upgrade path |

### `scripts/seed_root.py`

```bash
# Non-interactive (deploy / CI)
PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'

# Interactive (prompts for password)
PYTHONPATH=. python scripts/seed_root.py --username root
```

- Default username: `root` (override with `--username`).
- Password minimum: 6 characters (matches setup API).
- Idempotent: prints existing root and exits 0 if one already exists.
- Uses `auth.hash_password` and `SessionLocal` — same DB as the running app (`pos.db` by default).

### Reports (role-scoped)
| Method | Path | Roles |
|--------|------|-------|
| `GET` | `/api/reports/summary/today` | root, admin, account, cashier (cashier = own checkout only) |
| `GET` | `/api/reports/daily-sales` etc. | Dashboard roles; account ≤ 90 days |
| `GET` | `/api/reports/sales/by-cashier` | root, admin, account (≤90d); cashier, waiter → **403** |
| `GET` | `/api/reports/sales/by-order-staff` | root, admin (all); waiter (self); cashier, account → **403** |
| `GET` | `/api/reports/sales/promoted-by-waiter` | root, admin (all); waiter (self) |
| `PUT` | `/api/menu-items/{id}/toggle-promoted` | `ADMIN_PANEL_ROLES` |

## 4. Session Flow (`services/sessions.py`, `auth.py`)

1. Login creates `UserSession` row with `jti`.
2. JWT payload: `{ sub, role, jti, exp }`.
3. `get_current_user` rejects missing/revoked `jti`.
4. Single-device roles: new login revokes prior sessions.

**Gap:** `POST /api/setup/root` uses hardcoded `device_id="setup-device"` (no client UUID).

## 5. Frontend Pages & Guards

| Path | Roles | Module |
|------|-------|--------|
| `/setup` | Public (needs_setup) | `setup.html`, `setup.js` |
| `/login` | Password roles | `login.js` → redirects to `/setup` if needed |
| `/pin-login` | cashier, waiter | `pin-login.js` |
| `/counter` | cashier, admin, root | `counter.js` |
| `/waiter` | waiter, admin, root, cashier | `waiter.js` |
| `/account` | account | `account.js` |

### Nav (`static/auth.js`)
- **Change Password** button for `root`/`admin` only → `POST /api/auth/change-password` modal. Hidden for PIN roles (`account`, `cashier`, `waiter`).
- **Take Orders** link (`/waiter`) — visible only for `cashier` and `waiter` roles.
- Default pages: `ROLE_DEFAULT_PAGE` map.

### Counter tabs by role
| Tab | root | admin | cashier |
|-----|------|-------|---------|
| Dashboard | ✓ | ✓ | ✓ (scoped) |
| Cashier / Billing | ✓ | ✓ | ✓ |
| Menu | ✓ | ✓ | — |
| Staff Management | ✓ | ✓ | — |
| **Admin Accounts** | ✓ | — | — |
| **Audit Logs** | ✓ | — | — |
| Table Management | ✓ | ✓ | — |

**Main nav active state:** selected tab uses `.tab-btn.active` (see `specs/feature-counter-ui/implementation.md`).

### Account reports (`/account`) — Phase 4 complete

- **Tabs:** Today's Overview | Sales History.
- **Overview:** today KPIs + cashier breakdown (today).
- **History:** date-range filter (≤ 93 days, client + server validation), daily sales chart, monthly sales chart (year selector), cashier breakdown for range.
- **APIs:** `/api/reports/summary/today`, `/api/reports/daily-sales`, `/api/reports/monthly-sales`, `/api/reports/sales/by-cashier`.

### Counter dashboard — Phase 4 complete

`applyDashboardRoleVisibility(role)` gates widgets by role:

| Dashboard area | root | admin | cashier |
|----------------|------|-------|---------|
| Today KPIs (store / own checkout) | store | store | own checkout |
| Hourly + Top Items charts | ✓ | ✓ | hidden |
| Sales History subtab (daily/monthly store) | ✓ | ✓ | hidden |
| Insights subtab | ✓ | ✓ | hidden |
| **Staff Performance** subtab | ✓ | ✓ | hidden |
| **Waiter Incentives** subtab | ✓ | ✓ | hidden |
| Cashier breakdown chart | ✓ | ✓ | hidden |
| Waiter/order-staff breakdown chart | ✓ | ✓ | hidden |

**Staff Performance tab** (`dashboard-tab-staff`):
- Date range: `#staff-filter-start-date` / `#staff-filter-end-date`
- Presets: `#btn-staff-preset-today`, `#btn-staff-preset-month`
- Period label: `#staff-report-period`
- Default range: first day of current month → today
- APIs: `GET /api/reports/sales/by-cashier` and `by-order-staff` with `start_date` + `end_date` (supports single-day and multi-day/month ranges)
- JS: `getStaffReportDateRange()`, `setStaffFilterDateRange()`, `loadStaffBreakdownCharts()` in `counter.js`

### Phase 4b — Promoted items (2026-07-04)

**Schema**
- `MenuItem.is_promoted` boolean (`models.py`, `schemas.py`).
- Startup migration in `main.py` lifespan (SQLite `ALTER TABLE`).

**Manual migration (SQLite dev):**
```bash
sqlite3 pos.db "ALTER TABLE menu_items ADD COLUMN is_promoted BOOLEAN NOT NULL DEFAULT 0;"
```
Restart the app to apply via lifespan if the column is missing.

**Menu admin UI** (`counter.html` / `counter.js`)
- Checkbox on create/edit form (`#item-is-promoted`).
- List badge **★ Promoted** + **Promote/Unpromote** button.
- `PUT /api/menu-items/{id}/toggle-promoted`.

**Waiter/cashier menu** (`waiter.js`)
- **★ Promo** badge + amber border on promoted item cards.

**Incentives report** (root + admin only)
- Counter → Dashboard → **Waiter Incentives** subtab.
- `GET /api/reports/sales/promoted-by-waiter?start_date=&end_date=`
- Bar chart + detail table (staff, qty, revenue).

Root admin UI calls `/api/root/admins` (`counter.js`: `loadRootAdmins`, reset/delete).

### Audit log viewer (Phase 3 — 2026-07-04)

- **Location:** Counter → **Audit Logs** tab (`tab-audit-logs`, `panel-audit-logs`).
- **Visibility:** `applyAdminOnlyTabVisibility` shows tab only when `role === 'root'`; non-root users redirected if panel was open.
- **API:** `GET /api/root/audit-logs?action=&start_date=&end_date=&limit=` — root-only (`403` for other roles).
- **UI:** Table columns — Time, Actor, Action (label), Target, Details (username/role deltas, PIN flags).
- **Filters:** Action dropdown, from/to date, Refresh / Apply Filters.
- **JS:** `loadAuditLogs`, `fetchAuditLogs`, `renderAuditLogs` in `counter.js`.

## 6. Bootstrap / Migration (`main.py` lifespan)

- `ALTER TABLE orders ADD COLUMN checked_out_by_id` (SQLite-safe).
- If no `root` exists and `username=admin` user exists → promote to `role=root` (one-time legacy upgrade).
- **Removed:** auto-seed default admin on every boot.
- **Preferred fresh install:** `scripts/seed_root.py` (see §3.2).

## 7. Intentional Deviations & Known Gaps

Documented for SDD honesty — resolve in a follow-up spec amendment or implementation pass.

| Item | Spec wording | Current behavior | Severity |
|------|--------------|------------------|----------|
| Root staff API | §2.1 governance | Root has `ADMIN_PANEL_ROLES` + `/api/admin/users` for staff | **Resolved:** root superset (2026-07-04) |
| Audit log UI | §7 FR-A3 root viewer | Counter **Audit Logs** tab; filters + table | **Done** (2026-07-04) |
| Account monthly UI | §2.3 daily/monthly reports | `/account` History tab with monthly chart + date range | **Done** (2026-07-04) |
| Cashier → waiter link | §2.4 may use waiter screen | Nav **Take Orders** → `/waiter` (cashier/waiter only) | **Done** (2026-07-04) |
| Admin dashboard staff breakdown | FR-8 / FR-D1 per-cashier/waiter | Staff Performance: date-range charts + Today/This Month presets | **Done** (2026-07-05) |
| Phase 4b promoted items | §4.2 incentives | `is_promoted` + incentives report + waiter badges | **Done** (2026-07-04) |
| Root POS capabilities | Role table silent | Root in `POS_ORDER_ROLES` and `CHECKOUT_ROLES` | **Undocumented** — intentional superuser |

## 8. Test Map

Primary: `tests/test_rbac.py`  
Related: `tests/test_orders_rbac.py`, `tests/conftest.py` (root/admin/account/cashier/waiter seeds)

Latest suite: `PYTHONPATH=. python -m pytest -q` → **121 passed** (2026-07-05)

Primary: `tests/test_rbac.py`  
Hierarchy: `tests/test_rbac_hierarchy.py`

### Not yet automated (see `validation.md`)
- Root reset password API
- Cashier `POST /api/orders/submit` success
- Kitchen role login blocked
- JWT without valid `jti` (explicit test)

## 9. Module Index

| Path | Role |
|------|------|
| `rbac.py` | Role constants |
| `auth.py` | JWT + session-aware `get_current_user` |
| `services/sessions.py` | Session create/revoke |
| `services/audit.py` | Admin audit log writes |
| `services/report_access.py` | Account 90-day cap |

**Related feature SDD:** `specs/feature-account-reports/` — accountant role contract (FR-A1–FR-A5).
| `routers/setup.py` | One-time root HTTP bootstrap (dev/test) |
| `scripts/seed_root.py` | CLI seed for first root (production) |
| `routers/root_users.py` | Root admin CRUD + audit read |
| `routers/users.py` | Staff CRUD + audit on admin actions; `_reject_privileged_roles_via_staff_api` |
| `tests/test_rbac_hierarchy.py` | Automated role creation hierarchy compliance (5 scenarios) |
| `routers/auth.py` | Login + change password |
| `routers/reports.py` | Role-scoped reports |
