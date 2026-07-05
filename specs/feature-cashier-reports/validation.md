# Validation: Cashier Reports & Ordering Inheritance

```bash
PYTHONPATH=. pytest tests/test_cashier_reports.py tests/test_orders_rbac.py tests/test_rbac.py::test_per_cashier_and_waiter_reports tests/test_rbac.py::test_checkout_sets_checked_out_by_id -v
```

**Primary test file:** `tests/test_cashier_reports.py`

---

## Automated (required for merge)

| # | Scenario | Test | Expected |
|---|----------|------|----------|
| 1 | Cashier can submit orders (waiter inheritance) | `test_cashier_can_submit_orders` | `POST /api/orders/submit` → **200**; `created_by_id` = cashier |
| 2 | Cashier cannot checkout | `test_cashier_submit_waiter_checkout_split` or orders RBAC | Waiter **403** on checkout; cashier **200** |
| 3 | Cashier today summary = own checkouts only | `test_cashier_summary_scoped_to_own_checkout` | Only orders with `checked_out_by_id` = this cashier |
| 4 | Cashier sees all staff on by-order-staff | `test_cashier_can_view_order_staff_breakdown` | **200**; waiter row present |
| 5 | Waiter sees self only on by-order-staff | `test_waiter_order_staff_scoped_to_self` | Only own `user_id` in rows |
| 6 | Cashier by-cashier scoped to self | `test_cashier_by_cashier_scoped_to_self` | Other cashier absent |
| 7 | Cashier denied monthly store sales | `test_cashier_cannot_access_monthly_store_sales` | **403** |

### Regression (existing)

| Test | File |
|------|------|
| Per-cashier / per-waiter date range | `test_per_cashier_and_waiter_reports` |
| Checkout attribution | `test_checkout_sets_checked_out_by_id` |

---

## Manual — Counter UI (optional)

- [ ] Cashier: **Take Orders** → `/waiter` works
- [ ] Cashier: Dashboard KPI shows **My Checkout Sales (Today)**
- [ ] Cashier: Staff Performance → waiter chart loads (date range)
- [ ] Cashier: no monthly store sales widget

---

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-05 | `tests/test_cashier_reports.py` | **5 passed** |
| 2026-07-05 | Full suite (`pytest -q`) | **84 passed** (includes cashier report regressions) |
