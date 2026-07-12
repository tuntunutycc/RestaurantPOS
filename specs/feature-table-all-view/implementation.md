# Implementation: Table ALL View & Display Names

## Shared helper
- `static/table-display.js` — `stripTableNamePrefix()`, `displayTableName()`, `displayTableStatus()` (`available` → **Free**), typography class constants

## Frontend
| Surface | ALL tab default | Grid classes | Display names | Status label |
|---------|-----------------|--------------|---------------|--------------|
| Waiter | `waiter.js` `#zone-tabs` | `grid-cols-3 md:grid-cols-5 lg:grid-cols-8` | `tableLabel()` | Free / Occupied, `text-[10px]` on dark card |
| Cashier (inside 3-pane `#pane-tables`) | `counter.js` `#cashier-zone-tabs` | `grid-cols-3 sm:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4` (narrower column) | `cashierTableName()` | Free / Occupied on light card |
| Table Dashboard | `table-dashboard.js` | `grid-cols-3 md:grid-cols-5 lg:grid-cols-8` | `tableDisplayLabel()` | same typography on light card |

Admin kanban (`counter.js` Table Management) shows formatted names in list; edit inputs use raw `name_or_number`.

## Backend
No code changes — `GET /api/tables/grid` and `/api/tables/status` already return all zones/tables.

## Tests
- `tests/test_table_all_view.py`
