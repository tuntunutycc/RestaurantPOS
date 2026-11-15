# Requirements: Daily Order History + Excel Export

## Purpose
Admin and Cashier need a **day-scoped list of paid orders** with line-item detail (modifiers + takeaway) and a one-click **Excel (.xlsx) export** for reconciliation / bookkeeping.

## Scope
- New static page: `/order-history` (aliases: `/admin/sales-history`, `/cashier/history`)
- API list + Excel download for one calendar day
- Roles: `root`, `admin`, `cashier`

## Non-goals
- Aggregated charts (existing Sales Reports)
- Editing / refunding historical orders
- Waiter access

## Data rules
- **Statuses:** `paid`, `completed` only
- **Day filter:** `Order.created_at` in `[date 00:00:00, next day)` using server/UTC calendar date (same convention as `GET /api/reports/sales`)
- **Default UI date:** today (UTC date, matching existing reports)
- Line detail uses stored snapshots + `selected_modifiers` + `is_takeaway`; cancelled lines excluded from detail/export

## API

### `GET /api/orders/daily-history?date=YYYY-MM-DD`
Response: list of summary rows + nested items for modal.

### `GET /api/orders/daily-history/export?date=YYYY-MM-DD`
Returns `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` file  
`Content-Disposition: attachment; filename="order-history-YYYY-MM-DD.xlsx"`.

Excel columns (one row per active order line):
| Column | Content |
|--------|---------|
| Order ID | `orders.id` |
| Time | `created_at` formatted |
| Item Details | name + modifiers + `(ပါဆယ်)` when `is_takeaway` |
| Qty | line quantity |
| Total Price | line `subtotal` |

## UI
- Date picker + Load
- Table: Order ID, Time, Total Amount, View Details
- Modal: line items, modifiers, takeaway badge, line subtotals
- Export to Excel button (uses export endpoint with Bearer token)

## Related
- `specs/feature-sales-period-reports/` — day aggregates
- `specs/feature-menu-pricing/` — `is_takeaway`
- `specs/feature-priced-modifiers/` — modifiers
