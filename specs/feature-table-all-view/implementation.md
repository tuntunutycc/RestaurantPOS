# Implementation: Table ALL View & Display Names

## Shared helper
- `static/table-display.js` — `stripTableNamePrefix()`, `displayTableName()`

## Frontend
| Surface | ALL tab default | Grid classes | Display names |
|---------|-----------------|--------------|---------------|
| Waiter | `waiter.js` `#zone-tabs` | `grid-cols-3 md:grid-cols-5 lg:grid-cols-8` | `tableLabel()` |
| Cashier | `counter.js` `#cashier-zone-tabs` | same | `cashierTableName()` |
| Table Dashboard | `table-dashboard.js` | same | `tableDisplayLabel()` |

Admin kanban (`counter.js` Table Management) shows formatted names in list; edit inputs use raw `name_or_number`.

## Backend
No code changes — `GET /api/tables/grid` and `/api/tables/status` already return all zones/tables.

## Tests
- `tests/test_table_all_view.py`
