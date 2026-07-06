# Requirements: Direct Walk-in Takeaway

## Purpose
Allow waiters to start a **walk-in takeaway** order with **no physical table** (`table_id = NULL`). Staff attribution uses the authenticated session at submit time.

## Explicit non-goals (removed / never used)
- **No dummy table** (e.g. "Table 10") for takeaways
- **No `is_takeaway_zone`** or virtual table queue entity
- Takeaway orders are identified by `Order.order_type = 'takeaway'` and `Order.table_id IS NULL`

## Data model

| Field | Rule |
|-------|------|
| `Order.table_id` | `NULL` for walk-in takeaway |
| `Order.order_type` | `'takeaway'` |
| `Order.customer_name` | Optional; default display "Walk-in" |
| `OrderItem.created_by_id` | **Required at submit** — JWT `current_user.id` (waiter incentive attribution) |
| `OrderItem.is_takeaway` | Default `true` for items added in walk-in takeaway cart |

## FR-W1: Create walk-in takeaway
- `POST /api/orders/submit` and `POST /api/orders/` accept `order_type=takeaway` with `table_id` omitted or `null`.
- **No table** is marked occupied.
- Each line sets `created_by_id` from the authenticated user.

## FR-W2: Dine-in still requires table
- `order_type=dine_in` without `table_id` → **400** `table_id is required for dine_in orders`

## FR-W3: Display labels
Kitchen, Cashier, and waiter active lists show:
> **🛍️ Takeaway #\<Order_ID\>**

When `table_id` is null and `order_type=takeaway`.

## FR-W4: Waiter UI
- Prominent **`[ + Walk-in Takeaway ]`** control near the table grid.
- **MUST prompt** for optional `customer_name` (modal or `prompt`) before opening cart; default display **Walk-in** if empty.
- Opens cart context with **no table** selected.
- Cart lines default `is_takeaway=true` (dual pricing per `specs/feature-menu-pricing/`).

## FR-W5: Incentive / staff reports
- `GET /api/reports/sales/promoted-by-waiter` and `GET /api/reports/sales/by-order-staff` include lines from `table_id IS NULL` takeaway orders when `OrderItem.created_by_id` matches.

## FR-W6: Active takeaway parity with occupied tables
Active walk-in takeaway orders (`table_id IS NULL`, `order_type=takeaway`, status `open`/`dining`) behave like **occupied dine-in tables** for waiters:

| Action | Behavior |
|--------|----------|
| Click active takeaway card | Open **order details sidebar** (same as occupied table): list submitted items, totals, per-item actions |
| **Add More Items** (sidebar) | Enter **Append Mode** bound to existing `order_id` |
| Submit new items | `POST /api/orders/submit` with `order_id` → append batch (`batch_number` increments), **no new order** |
| Cancel unserved line | `PUT /api/orders/{order_id}/items/{item_id}/status` with `cancelled` — **same endpoint and UI as dine-in** |
| Kitchen | `new_order_batch` WebSocket + add-on ticket for new batch only |
| Cashier | Single unified receipt (`GET /api/orders/{order_id}/details` totals all lines) |

When the last non-cancelled item is cancelled, order `status` becomes `cancelled` and the takeaway card disappears from active lists (`order_cancelled`, `takeaways_updated`).

**Append contract:** `OrderSubmitRequest.order_id` (optional). When set for `order_type=takeaway`:
- Target order must exist, `table_id IS NULL`, status in `open`/`dining`
- **404** if not found or not appendable
- `table_id` on request is **not** required

Cart header in append mode (waiter UI): **"Adding to Takeaway: \<customer\>"**

## FR-W7: Item-level cancellation (takeaway)
Walk-in takeaway orders **must** support item-by-item cancellation for unserved items, mirroring dine-in table order details:
- Cancel control visible in order details sidebar for non-`cancelled` lines (pending/cooking/served — same rules as dine-in).
- No separate "Cancel Entire Order" button on waiter or cashier UI; staff cancel lines individually.

## FR-W8: Cart price breakdown
Waiter cart and active-order sidebar show **Subtotal**, **Tax**, and **Grand Total** (see `specs/feature-waiter-cart-breakdown/`).

## Authorization
- Submit — `POS_ORDER_ROLES` (`waiter`, `cashier`, `admin`, `root`)

## Related
- `specs/feature-menu-pricing/` — `takeaway_price` + `is_takeaway` line pricing
- `specs/feature-waiter-incentives/` — `created_by_id` attribution
- Item-level cancel: `PUT /api/orders/{order_id}/items/{item_id}/status` with `cancelled` (see FR-W7)
