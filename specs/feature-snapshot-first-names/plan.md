# Plan: Snapshot-first item names (Step 1 of 2)

Order (contract first, one commit/phase, **no linked add-on code in it**):

1. **Tests first** (`tests/test_snapshot_first_names.py`): write the rename tests from `validation.md`; run them and confirm the "Wrong" surfaces fail before the fix (proves the gap is real).
2. `routers/orders.py`: make `_display_menu_item_name` snapshot-first (FR-N1). It already feeds `_build_order_item_details_response` and the daily history line.
3. `schemas.py`: `OrderResponseDetail.build_from_order` uses the same rule. Prefer one small shared function used by both (a plain function in `schemas.py` or a tiny module under `services/`; decide when implementing, avoiding a circular import).
4. `main.py`: idempotent backfill (FR-N2) after the existing `order_items` column migrations.
5. Run the **whole** suite. Fix tests that assumed live-first names (expected: a few tests that rename an item then read an old order). Each such change is listed in `CHANGELOG.md`.
6. Docs: `specs/api-reference.md`, `specs/database-schema.md`, `CHANGELOG.md`, tick `validation.md`.

Files: `routers/orders.py`, `schemas.py`, `main.py`, `tests/test_snapshot_first_names.py`, existing tests only if they fail for the reason above, `specs/api-reference.md`, `specs/database-schema.md`, `CHANGELOG.md`.

Gate to Step 2: full suite green, mutation check done (see validation), the user reviews the result.

Notes
- No new column, no new endpoint, no frontend change (the screens only display what the API returns).
- Rollback is a code revert; the backfill only filled empty values, so nothing needs undoing.
