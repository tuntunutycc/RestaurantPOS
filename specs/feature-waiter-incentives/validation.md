# Validation: Promoted Items & Waiter Incentives

```bash
PYTHONPATH=. pytest tests/test_waiter_incentives.py tests/test_rbac.py::test_promoted_items_full_flow tests/test_rbac.py::test_phase4b_promoted_ui_contract -v
```

**Primary test file:** `tests/test_waiter_incentives.py`

---

## Automated (required for merge)

| # | Scenario | Test | Expected |
|---|----------|------|----------|
| 1 | Toggle promoted on menu item | `test_toggle_promoted_flips_flag` | `PUT toggle-promoted` → `is_promoted=true` |
| 2 | Create menu item with is_promoted | `test_create_menu_item_with_is_promoted` | `POST` body → persisted flag |
| 3 | Promoted report attributes waiter sales | `test_promoted_report_attributes_waiter` | qty + revenue for `created_by_id` |
| 4 | Non-promoted lines excluded | `test_promoted_report_excludes_non_promoted_items` | No revenue from non-promoted item |
| 5 | Cashier denied promoted report | `test_cashier_cannot_access_promoted_report` | **403** |
| 6 | Account denied promoted report | `test_account_cannot_access_promoted_report` | **403** |
| 7 | Waiter sees self only | `test_waiter_promoted_report_scoped_to_self` | Single row, own `user_id` |

### Regression

| Test | File |
|------|------|
| Full E2E flow | `test_promoted_items_full_flow` |
| UI contract | `test_phase4b_promoted_ui_contract` |

---

## Manual — Counter UI (optional)

- [ ] Admin: Menu item **★ Promoted** badge + Promote button
- [ ] Admin/root: Dashboard → **Waiter Incentives** → date range → chart + table
- [ ] Waiter menu: **★ Promo** on promoted cards

---

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-05 | `tests/test_waiter_incentives.py` | **7 passed** |
| 2026-07-05 | Full suite (`pytest -q`) | **84 passed** (includes promoted-item regressions) |
