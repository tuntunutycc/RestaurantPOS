# Requirements: Table Grid ALL View & Display Names

## Purpose
Improve table floor visibility for restaurants with many tables (35+). All POS roles that show a table grid must support an **ALL** zone tab (default) and compact table labels without a redundant `"Table "` prefix.

## FR-TA1: ALL view (default)
Waiter, Cashier, and Admin table dashboards must show a horizontal **ALL** pill as the **first** tab and **selected by default** on load.

| Selection | Grid content |
|-----------|----------------|
| **ALL** | Every table from every zone in one responsive grid |
| Zone pill | Only tables in that zone |
| Takeaway (where applicable) | Unchanged — separate view, not mixed into dine-in grid |

**Surfaces:**
- Waiter — `#zone-tabs` + `#table-cards` (`waiter.js`)
- Cashier — `#cashier-zone-tabs` + `#cashier-tables-grid` (`counter.js`)
- Table Dashboard (admin/waiter) — `#zone-tabs` + `#tables-grid` (`table-dashboard.js`)

Admin **Table Management** kanban remains zone-column layout (operational CRUD); ALL view applies to **floor grid** UIs only.

## FR-TA2: Responsive grid density
Table floor grids use Tailwind responsive columns so 35+ tables fit on screen, e.g.:

`grid grid-cols-3 md:grid-cols-5 lg:grid-cols-8 gap-2`

Exact breakpoints may vary by surface but must increase columns on larger viewports.

## FR-TA3: Display name formatting (UI only)
Before rendering a **dine-in table** label in grids, cart headers, active orders, checkout modals, and receipts:

```javascript
displayTableName(raw) // strips leading "Table " case-insensitive
// "Table G1" → "G1", "table 35" → "35", "G1" → "G1"
```

- **Do not** mutate stored `name_or_number` in the database.
- **Do not** apply prefix stripping to takeaway labels (`🛍️ Takeaway`, `Takeaway #123`, walk-in customer names).
- Admin edit inputs may show the raw stored value for editing; list/card **display** uses formatted name.

## FR-TA4: Data loading (no pagination)
Frontend ALL view loads the full table set from existing APIs:

| Endpoint | Roles | Notes |
|----------|-------|-------|
| `GET /api/tables/status` | authenticated | Waiter — zones with nested tables |
| `GET /api/tables/grid` | authenticated | Cashier, Table Dashboard — zones with status + active order |
| `GET /api/tables` | admin panel | Flat list for admin CRUD; no pagination |

Server must return **all** zones/tables in one response (no page/limit params). Typical restaurant scale (≤100 tables) is acceptable in memory.

## Related
- `specs/feature-table-management/` — admin CRUD & delete safety
- `specs/feature-menu-category-navigation/` — ALL pill pattern reference
