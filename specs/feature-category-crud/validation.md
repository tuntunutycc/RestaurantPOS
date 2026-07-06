# Validation: Category Edit & Delete

Use before merging category CRUD changes. Automated items must pass in CI:

```bash
PYTHONPATH=. pytest tests/test_category_crud.py -v
```

**Primary test file:** `tests/test_category_crud.py`  
**API:** `routers/menu.py` — `PUT` / `DELETE` `/api/categories/{category_id}`

---

## Automated — category CRUD (required for merge)

| # | Scenario | Test function | Expected |
|---|----------|---------------|----------|
| 1 | **Successful edit** — authorized admin updates category name | `test_update_category_name` | `PUT` → **200 OK**; response `name` matches |
| 2 | **Prevent deletion (items exist)** — category with active menu item | `test_delete_category_blocked_when_items_exist` | `DELETE` → **400**; `detail` = `Cannot delete category. Please delete all menu items under this category first.` |
| 3 | **Successful deletion (empty category)** — no menu items | `test_delete_category_without_items` | `DELETE` → **200**; category absent from list |
| 4 | **Delete after soft-deleted items only** — no active items, no order history on soft-deleted rows | `test_delete_category_after_soft_deleted_items_only` | `DELETE` → **200**; soft-deleted rows purged |
| 5 | **Delete with soft-deleted items that have order history** — active count is zero | `test_delete_category_allowed_when_only_soft_deleted_items_with_order_history` | `DELETE` → **200**; items moved to `__system_archived__` |

### Cross-feature (menu item soft delete)

Validated together with `specs/feature-menu-items/validation.md` — menu soft delete must run before category delete in real workflows.

---

## Manual — Counter UI (optional sign-off)

- [ ] Menu Management → category row shows **Edit** and **Delete**
- [ ] Edit opens prompt; rename refreshes list
- [ ] Delete with items shows server error message in dialog
- [ ] Delete empty category removes row after confirm

- [ ] Delete category after soft-deleting all its menu items succeeds

---

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-04 | `tests/test_category_crud.py` | **5 passed** |
| 2026-07-04 | `tests/test_category_crud.py` + `tests/test_menu_item_soft_delete.py` | **8 passed** |
| 2026-07-04 | Full `pytest -q` | **80 passed** |
