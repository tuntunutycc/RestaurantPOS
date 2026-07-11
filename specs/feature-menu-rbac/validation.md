# Validation: Menu Management RBAC

```bash
PYTHONPATH=. pytest tests/test_menu_rbac_availability.py tests/test_rbac_security_gaps.py -v
PYTHONPATH=. pytest -q
```

## Automated (required)

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Cashier `POST /api/menu-items/` | **403** |
| 2 | Cashier `PATCH /api/menu-items/{id}/availability` with `{ "is_available": false }` | **200**; item updated |
| 3 | Cashier `PUT /api/menu-items/{id}` (price change) | **403** |
| 4 | Admin `PATCH …/availability` | **200** |
| 5 | Waiter `PATCH …/availability` | **403** |

## Manual

- [ ] Cashier Counter → Menu Management: no Add/Edit/Delete; toggle switches work
- [ ] Admin sees full menu CRUD
- [ ] Waiter menu greys out item after cashier marks sold out (WebSocket or refresh)

## Evidence

| Date | Result |
|------|--------|
| 2026-07-11 | `tests/test_menu_rbac_availability.py` — **5 passed**; full suite **171 passed** |
