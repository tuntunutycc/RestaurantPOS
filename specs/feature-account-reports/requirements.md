# Requirements: Account (Accountant) Role — Read-Only Financial Reports

## Purpose
Define the `account` role for finance staff who need **read-only** access to store sales data, with a **strict 3-month (90-day) lookback** window. Aligns with `specs/feature-rbac/requirements.md` §3.3 and report matrix §8.

## Status
**Mostly as-built on `main` (Phase 4, 2026-07-04).** This folder formalizes the contract and records the **90-day** business rule (implementation currently uses `93` — see `plan.md` alignment step).

---

## FR-A1: Role definition (accountant / finance)

| Item | Contract |
|------|----------|
| Role string | `account` on `User.role` |
| Login | Username + password via `POST /api/auth/login` |
| Default page | `/account` (`ROLE_DEFAULT_PAGE` in `auth.js`) |
| Session policy | Single-device (`SINGLE_DEVICE_ROLES`) |
| Password change | `POST /api/auth/change-password` allowed |

**Must not:**
- Submit orders (`POST /api/orders/submit` → **403**)
- Checkout orders
- Mutate menu, categories, tables, zones, printers
- Create/edit/delete staff (`/api/admin/users` → **403**)
- Access audit logs, admin accounts, waiter incentives, or per-waiter staff breakdown

---

## FR-A2: Permitted reports (store financial view)

The `account` role may view **store-level** sales analytics within the time cap (FR-A3).

| Capability | API | Allowed |
|------------|-----|---------|
| Today's store summary | `GET /api/reports/summary/today` | ✓ |
| Daily sales trend | `GET /api/reports/daily-sales?start_date=&end_date=` | ✓ (≤ 90d) |
| Monthly sales trend | `GET /api/reports/monthly-sales?year=` | ✓ (months within 90d window) |
| Sales by cashier | `GET /api/reports/sales/by-cashier?start_date=&end_date=` | ✓ (≤ 90d) |
| Top selling items | `GET /api/reports/top-items` | ✓ (today only; implicit within cap) |
| Hourly trend | `GET /api/reports/hourly-trend` | ✓ (today only) |
| Category sales | `GET /api/reports/category-sales` | ✓ (within cap on date params) |
| Cancellations | `GET /api/reports/cancellations` | ✓ (within cap) |

**Denied (403):**

| Capability | API |
|------------|-----|
| Sales by waiter / order staff | `GET /api/reports/sales/by-order-staff` |
| Promoted items / incentives | `GET /api/reports/sales/promoted-by-waiter` |
| Monthly store sales (cashier role widget) | N/A — account uses `/account`, not counter admin charts |

**UI surface:** dedicated `/account` page (`account.html`, `account.js`) — not Counter admin dashboard.

---

## FR-A3: Strict 3-month (90-day) time constraint

**Business rule:** `account` may only query data from **today back to exactly 90 calendar days ago** (inclusive). `root` and `admin` have **no** lookback cap.

### Server enforcement (canonical)

Central helper: `services/report_access.py` → `assert_report_date_range(user, start_date, end_date)`.

| Check | Rule | HTTP | Message (example) |
|-------|------|------|-------------------|
| Range span | `(end - start).days + 1 ≤ 90` | **400** | `Account role is limited to 90 days per query` |
| Oldest start | `start_date ≥ today - 89 days` | **400** | `Account role cannot view data older than 90 days` |
| Invalid range | `start_date > end_date` | **400** | `start_date cannot be after end_date` |

Constant: `ACCOUNT_MAX_REPORT_DAYS = 90` in `rbac.py`.

**Monthly sales special case:** `GET /api/reports/monthly-sales` clips the query window to the oldest allowed date rather than returning an empty year when partially in range (existing behavior); reject with **400** only when the entire requested year is older than the cap.

**Timezone:** UTC calendar dates (consistent with existing report routers).

### Roles without cap

| Role | Lookback |
|------|----------|
| `root` | unlimited |
| `admin` | unlimited |
| `account` | **90 days** |
| `cashier` | role-specific scoping (checkout-only summary; no monthly store) — see `specs/feature-cashier-reports/` |
| `waiter` | self-only daily order lines |

---

## FR-A4: Staff provisioning

| Item | Contract |
|------|----------|
| Created by | `root` or `admin` via `POST /api/admin/users` |
| Role value | `account` in `AdminStaffRole` |
| Password | Required on create (min 6 chars); optional on update |
| PIN | Not used (`pin_code = null`) |

---

## FR-A5: Frontend UX (`/account`)

| Item | Contract |
|------|----------|
| Route guard | `requireRole(['account'])` |
| Overview tab | Today's KPIs via `summary/today` |
| History tab | Date-range picker with client validation mirroring FR-A3 |
| Date input `min` | Set to `today - 89 days` on `<input type="date">` |
| Date input `max` | Today |
| Error display | `#account-range-error` for client validation; toast/dialog for API **400** detail |
| Constant | `ACCOUNT_MAX_DAYS = 90` in `account.js` (must match backend) |

---

## Reporting matrix (account column summary)

| Report | account |
|--------|---------|
| Store daily / monthly | yes (≤ 90d) |
| By cashier | yes (≤ 90d) |
| By waiter / order staff | **no** |
| Promoted incentives | **no** |
| Ordering / admin mutations | **no** |

## Related specs
- `specs/feature-rbac/requirements.md` — §3.3, §8, session policy
- `specs/feature-cashier-reports/requirements.md` — cashier vs account report separation
- `specs/mission.md` — account persona
