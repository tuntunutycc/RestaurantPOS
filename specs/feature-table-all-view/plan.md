# Plan: Table ALL View & Display Names

## Phase 1 — Spec
- Add `specs/feature-table-all-view/`
- Update `specs/feature-table-management/requirements.md` (display + grid UX cross-ref)
- Update `specs/api-reference.md` (no pagination on table list endpoints)

## Phase 2 — Backend
- Verify `GET /api/tables`, `/api/tables/grid`, `/api/tables/status` return full lists
- Add pytest: multi-zone grid returns all tables

## Phase 3 — Frontend
- Add `static/table-display.js` — `displayTableName()`, `stripTableNamePrefix()`
- Waiter / Counter / Table Dashboard: ALL tab default, responsive grid, formatted labels
- Include script in relevant HTML files

## Phase 4 — Validation
```bash
PYTHONPATH=. pytest tests/test_table_all_view.py -v
PYTHONPATH=. pytest -q
```
