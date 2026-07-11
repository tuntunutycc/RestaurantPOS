# Validation: Table ALL View & Display Names

```bash
PYTHONPATH=. pytest tests/test_table_all_view.py -v
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | `GET /api/tables/grid` with 2 zones, 5+ tables total | All tables returned across zones |
| 2 | `GET /api/tables/status` | All zones with nested tables, no truncation |

## Manual

- [ ] Waiter: **ALL** tab default; 35+ tables visible in dense grid; labels show `G1` not `Table G1`
- [ ] Available tables show **Free** (not `AVAILABLE`); status line uses compact `text-[10px]` typography
- [ ] Cashier: same ALL default on floor grid
- [ ] Table Dashboard (admin): ALL tab + compact names
- [ ] Takeaway pills/labels unchanged (`🛍️ Takeaway #…`)
- [ ] Checkout header shows compact table id (e.g. `Checkout - G1`)

## Evidence

| Date | Result |
|------|--------|
| 2026-07-11 | `tests/test_table_all_view.py` — **2 passed**; full suite **173 passed** |
