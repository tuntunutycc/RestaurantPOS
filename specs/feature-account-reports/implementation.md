# Implementation Reference: Account Role & Financial Reports

**Status:** Done on `main` (90-day cap aligned 2026-07-05).  
**Branch:** `main`

## Role & RBAC constants (`rbac.py`)

| Constant | Value (target) | Purpose |
|----------|----------------|---------|
| `ROLE_ACCOUNT` | `"account"` | Role identifier |
| `PASSWORD_ROLES` | `root`, `admin` only | Password login + change-password |
| `PIN_ROLES` | includes `account` | PIN login via `/api/auth/login-pin` |
| `SINGLE_DEVICE_ROLES` | includes `account` | One active session |
| `FULL_REPORT_ROLES` | root, admin, account | Store report access |
| `ADMIN_MANAGEABLE_ROLES` | cashier, waiter, account | Staff CRUD targets |
| `ACCOUNT_MAX_REPORT_DAYS` | **90** (currently `93`) | Lookback cap |

**Models:** No schema change. `User.role` is `String(32)`.

## Auth (`routers/auth.py`)

| Endpoint | account access |
|----------|----------------|
| `POST /api/auth/login` | ✗ |
| `POST /api/auth/login-pin` | ✓ |
| `POST /api/auth/change-password` | ✗ (`403`) |
| `GET /api/auth/me` | ✓ |

## Report access (`services/report_access.py`)

```python
def assert_report_date_range(user, start, end):
    # account only:
    #   span ≤ ACCOUNT_MAX_REPORT_DAYS
    #   start ≥ today - (ACCOUNT_MAX_REPORT_DAYS - 1)
    # → HTTP 400 with explicit detail
```

Used by date-ranged report handlers in `routers/reports.py`.

## Report endpoints (`routers/reports.py`)

| Endpoint | account | Date guard |
|----------|---------|------------|
| `GET /api/reports/summary/today` | ✓ | N/A (today) |
| `GET /api/reports/sales` | ✓ | `assert_report_date_range` |
| `GET /api/reports/daily-sales` | ✓ | `assert_report_date_range` |
| `GET /api/reports/monthly-sales` | ✓ | Account-specific year clip |
| `GET /api/reports/sales/by-cashier` | ✓ | `assert_report_date_range` |
| `GET /api/reports/top-items` | ✓ | Today only |
| `GET /api/reports/hourly-trend` | ✓ | Today only |
| `GET /api/reports/category-sales` | ✓ | Date params + guard |
| `GET /api/reports/cancellations` | ✓ | Date params + guard |
| `GET /api/reports/sales/by-order-staff` | **403** | — |
| `GET /api/reports/sales/promoted-by-waiter` | **403** | — |

`_DASHBOARD_ROLES = [root, admin, account]`  
`_SUMMARY_ROLES` includes account for today's summary.

## Staff provisioning (`routers/users.py`)

- Admin/root create `account` users with **PIN** (password rejected).
- Account cannot call staff CRUD APIs.

## Frontend

| File | Behavior |
|------|----------|
| `main.py` | Serves `GET /account` |
| `static/account.html` | Overview + History tabs, date inputs, charts |
| `static/account.js` | `requireRole(['account'])`, client date validation, fetches report APIs |
| `static/auth.js` | `ROLE_DEFAULT_PAGE.account = '/account'` |
| `static/login.js` | Password login for `root`/`admin` only |
| `static/pin-login.js` | PIN login for `account` → redirect `/account` |

**Not used by account:** `counter.js`, `waiter.js` (guarded by role).

## Tests (existing)

| Test | File |
|------|------|
| Account cannot submit orders | `test_account_cannot_submit_orders` |
| Range > cap → 400 | `test_account_report_range_capped` |
| Monthly sales access | `test_account_monthly_sales_access` |
| Promoted report 403 | `test_account_cannot_access_promoted_report` |
| UI contract `ACCOUNT_MAX_DAYS` | `test_phase4_dashboard_ui_contract` |

See `validation.md` for merge checklist and gaps.
