# Plan: Safe menu price changes

Order (contract first):
1. `schemas.py`: `MenuMoney` / `ModifierMoney` types, name cleaning, percentage ≤ 100, explicit-null refusal in `MenuItemUpdate`, `SelectedModifier.price` / `ModifierOption.price` finite and bounded.
2. `routers/menu.py`: category must exist (create / update / upload), percentage check on the values **after** a partial update, upload-form checks.
3. `routers/orders.py`: percentage item discount capped at the price; a line that is negative, not finite or above the limit is refused with `400` before anything is saved.
4. Tests (`tests/test_menu_price_safety.py`), `api-reference.md`, `CHANGELOG.md`.

Notes
- No database change, no migration.
- Existing databases keep working: nothing is rewritten; bad values already stored are met by the order-time check (`400` with the item name) instead of a `500`.
