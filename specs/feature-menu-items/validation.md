# Validation: Menu Item Soft Delete

```bash
PYTHONPATH=. pytest tests/test_menu_item_soft_delete.py tests/test_deletion_integrity.py::test_soft_delete_menu_item_preserves_history_and_reports -v
```

## Automated (required for merge)

| # | Scenario | Test | Expected |
|---|----------|------|----------|
| 1 | Soft delete when no active orders | `test_soft_delete_menu_item_without_active_orders` | `DELETE` → **200**; `is_deleted=true`; hidden from `GET /api/menu-items/` |
| 2 | Block delete on active order | `test_soft_delete_blocked_when_on_active_order` | `DELETE` → **400**; exact active-order message |
| 3 | Allow delete after order paid | `test_soft_delete_allowed_after_order_paid` | `DELETE` → **200**; item soft-deleted |
| 4 | History preserved | `test_soft_delete_menu_item_preserves_history_and_reports` | Order snapshots + reports still work |
| 5 | Enables category delete | `test_delete_category_after_soft_deleted_items_only` (category CRUD) | Category deletable when only soft-deleted items remain |

## Cross-feature validation

```bash
PYTHONPATH=. pytest tests/test_menu_item_soft_delete.py tests/test_category_crud.py -v
```

## Manual (optional)

- [ ] Waiter menu no longer shows deleted item
- [ ] Counter delete shows alert when item on open table order
- [ ] Past order details still show item name

## Evidence

| Date | Result |
|------|--------|
| 2026-07-04 | `test_menu_item_soft_delete.py` + `test_category_crud.py` | **8 passed** |
