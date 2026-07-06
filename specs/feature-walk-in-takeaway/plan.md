# Plan: Direct Walk-in Takeaway

## Phase 1 — SDD audit
- Confirm no dummy-table / `is_takeaway_zone` code (none in repo)
- `requirements.md`, `implementation.md`, `validation.md`

## Phase 2 — Backend verify
- `table_id` nullable on `Order` / schemas (existing)
- `created_by_id` on submit (existing)
- Kitchen ticket header: `Takeaway #<id>`

## Phase 3 — Frontend
- `waiter.html` / `waiter.js` — Walk-in Takeaway button + cart defaults
- `counter.js` — Cashier label `Takeaway #<id>`
- `table-dashboard.js` — Kitchen active takeaway panel

## Phase 4 — Tests
- `tests/test_walk_in_takeaway.py`
