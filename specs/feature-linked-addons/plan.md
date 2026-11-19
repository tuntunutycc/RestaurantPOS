# Plan: Linked add-ons (Step 2 of 2)

Precondition: Step 1 (`specs/feature-snapshot-first-names/`) is done, the whole suite is green and the owner has reviewed it.

Order (contract first):
1. **Docs/contract**: `schemas.py` - `ModifierOption.linked_menu_item_id`, `ModifierOption.price_override`, `SelectedModifier.linked_menu_item_id`; keep `_normalize_modifiers_config` tolerant of old rows (missing keys -> `None`). Update `specs/api-reference.md` and `specs/database-schema.md` JSON shapes.
2. **Tests first** (`tests/test_linked_addons.py`): write from `validation.md`; confirm they fail for the right reason.
3. `services/menu_links.py` (new, no router imports):
   - `effective_option_price(db, option)` - the one rule from requirements;
   - `validate_and_normalize_options(db, options, holder_id)` - FR-L1 (target exists, not self, name fill, price overwrite, duplicate check, override needs link);
   - `holders_linking_to(db, target_id)` - non-deleted holders (scan `modifiers_config` in Python; the menu is small and the code stays database-neutral for the later PostgreSQL move);
   - `sync_dependents_price(db, target)` - FR-L3, returns the changed holders; assigns a **new list** to the JSON column so SQLAlchemy sees the change.
4. `routers/menu.py`:
   - create / upload / update call the validator;
   - update: when `price` changes call `sync_dependents_price` before the single commit, then broadcast the item and each changed holder;
   - delete: after the existing checks, `holders_linking_to` -> `400` with the holder list.
5. `routers/orders.py`: extend `_selected_modifiers_payload` / `_normalize_selected_modifier_dict` so the three order paths resolve linked options through the menu item (FR-L4) and write `linked_menu_item_id` into the snapshot only when linked. One shared helper, not three copies.
6. Frontend:
   - `static/counter.js` + `static/counter.html`: option row with the link select, auto-fill name, read-only synced price, custom-price / follow-price actions; carry the new keys through the three editor helpers; show server errors.
   - `static/waiter.js`: on `menu_item_updated`, refresh linked option prices in cart lines.
   - `static/i18n.js`: new labels.
7. Run the whole suite, mutation check, then `specs/feature-priced-modifiers/requirements.md` pointer, `CHANGELOG.md`, tick `validation.md`.

Files to add: `services/menu_links.py`, `tests/test_linked_addons.py`.
Files to modify: `schemas.py`, `routers/menu.py`, `routers/orders.py`, `static/counter.js`, `static/counter.html`, `static/waiter.js`, `static/i18n.js`, `specs/api-reference.md`, `specs/database-schema.md`, `specs/feature-priced-modifiers/requirements.md`, `CHANGELOG.md`.
Files **not** modified: `models.py`, `main.py` (no migration), `routers/reports.py`, `services/printing/*`, `static/order-history.js` (they read snapshots).

Notes
- No SQLite change, so there is nothing to migrate or roll back in the database; rollback is a code revert. Rows saved by the new code only contain two extra optional keys, which the old code ignores.
- Do not run `scripts/clear_sales.py` or touch the real `pos.db` during development; tests use the in-memory database.
- Tests share one database for the whole suite: use unique names per test.
