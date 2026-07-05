# Plan: Account Role & 90-Day Report Cap

## Current state (as-built audit)

| Area | Status | Gap vs FR-A3 |
|------|--------|----------------|
| `User.role = account` | ✅ Exists | — |
| `rbac.py` `ROLE_ACCOUNT`, `PASSWORD_ROLES`, `FULL_REPORT_ROLES` | ✅ | `ACCOUNT_MAX_REPORT_DAYS = 93` → align to **90** |
| `services/report_access.py` | ✅ Central date guard | Update constant + messages |
| `routers/reports.py` | ✅ Account in `_DASHBOARD_ROLES`; monthly clip logic | Align constant; verify all date endpoints call `assert_report_date_range` |
| `routers/auth.py` | ✅ Password login for account | — |
| `routers/users.py` | ✅ Admin can create account staff | — |
| `static/account.html` + `account.js` | ✅ Dedicated finance UI | `ACCOUNT_MAX_DAYS = 93` → **90**; add `min`/`max` on date inputs |
| `tests/test_rbac.py` | ✅ Partial (`test_account_report_range_capped`, `test_account_monthly_sales_access`) | Extend isolated oldest-date + admin-unrestricted tests |

**No new DB column required.** Role is a string on `users.role`; time policy is enforced in report access layer.

---

## Implementation phases (pending approval)

### Phase 1 — SDD & constant alignment
1. Set `ACCOUNT_MAX_REPORT_DAYS = 90` in `rbac.py`.
2. Sync `static/account.js` `ACCOUNT_MAX_DAYS = 90`.
3. Update `tests/test_rbac.py` UI contract assertion if string literal changes.

### Phase 2 — Backend enforcement audit
1. Confirm every account-accessible report endpoint invokes `assert_report_date_range` when `start_date`/`end_date` are present:
   - `daily-sales`, `by-cashier`, `category-sales`, `cancellations` (if date params exist)
2. Verify `monthly-sales` account branch uses the same constant.
3. Confirm denied endpoints return **403** for account:
   - `by-order-staff`, `promoted-by-waiter`, order submit
4. Standardize error messages to FR-A3 wording.

### Phase 3 — Frontend `/account`
1. Set `min` / `max` on `#account-start-date` and `#account-end-date` at init.
2. On API **400**, surface `detail` string in `#account-range-error` or toast.
3. No changes to Counter or waiter screens (account never lands there).

### Phase 4 — Tests & validation
1. Add/extend pytest per `validation.md`.
2. Run full suite; update `CHANGELOG.md` on pass.

---

## Out of scope
- PostgreSQL-specific migrations
- Account access to Counter dashboard or waiter incentives UI
- Changing `root`/`admin` unlimited lookback

## Dependencies
- `specs/feature-rbac/` — role hierarchy and staff CRUD
- `services/report_access.py` — single source for date policy
