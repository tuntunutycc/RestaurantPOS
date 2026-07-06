# Validation: Account Role & 90-Day Report Cap

```bash
PYTHONPATH=. pytest tests/test_rbac.py::test_account_cannot_submit_orders \
  tests/test_rbac.py::test_account_report_range_capped \
  tests/test_rbac.py::test_account_monthly_sales_access \
  tests/test_rbac.py::test_phase4_dashboard_ui_contract \
  tests/test_waiter_incentives.py::test_account_cannot_access_promoted_report -v
```

**Target module (after Proceed):** extend `tests/test_account_reports.py` (new) or `tests/test_rbac.py`.

---

## Automated (required for merge)

| # | Scenario | Test (planned) | Expected |
|---|----------|----------------|----------|
| 1 | Account can login with PIN | `auth_headers("account")` / login-pin tests | 200 + JWT |
| 2 | Account cannot submit orders | `test_account_cannot_submit_orders` | **403** |
| 3 | Account cannot access staff breakdown | new: `test_account_cannot_access_by_order_staff` | **403** |
| 4 | Account cannot access promoted report | `test_account_cannot_access_promoted_report` | **403** |
| 5 | Account daily range > 90 days | `test_account_report_range_capped` (update threshold) | **400** |
| 6 | Account start_date older than 90 days | new: `test_account_rejects_start_before_90_days` | **400** + detail message |
| 7 | Account valid 30-day range | new: `test_account_daily_sales_within_window` | **200** |
| 8 | Admin same old range (no cap) | new: `test_admin_unrestricted_report_range` | **200** |
| 9 | Account monthly sales in window | `test_account_monthly_sales_access` | **200** |
| 10 | UI contract: account page + 90-day constant | `test_phase4_account_ui_contract` | static file assertions |

### Regression

| Test | File |
|------|------|
| Account staff CRUD by admin | `test_rbac_hierarchy.py` |
| Account denied `/api/admin/users` | `TestScenario4FloorStaffCannotCreateUsers` |

---

## Manual — `/account` UI

- [ ] Login as account → lands on `/account` (not `/counter`)
- [ ] Overview shows today's KPIs
- [ ] History: date picker `min` blocks dates older than 90 days
- [ ] History: selecting over-90-day span shows client error before fetch
- [ ] Backend **400** on bad range shows readable message
- [ ] No Take Orders link; no admin tabs

---

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-05 | `tests/test_account_reports.py` | **8 passed** |
| 2026-07-05 | Full suite (`pytest -q`) | **92 passed** |
