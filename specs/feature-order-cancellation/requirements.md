# Requirements: Order Cancellation (Item-Level)

## Purpose
Staff cancel **individual unserved or mistaken line items** on active orders. This is the primary cancellation UX for both **dine-in** and **walk-in takeaway** orders.

Whole-order cancellation is achieved by cancelling every line item (or when the last active line is cancelled, the server finalizes `order.status = cancelled`).

## API (item-level — primary)

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| `PUT` | `/api/orders/{order_id}/items/{item_id}/status` | `POS_ORDER_ROLES` | Set `item_status` (`pending`, `cooking`, `served`, `cancelled`) |

### Server behavior on `cancelled`
1. Set line `item_status = cancelled`
2. Recalculate `order.total_amount` (excludes cancelled lines) unless order is `paid`
3. **Auto-clear:** If **zero non-cancelled items remain** → set `order.status = cancelled`
4. If `table_id` is set → set table `status = available` (dine-in)
5. If `table_id` is **null** (takeaway) → order drops from `GET /api/orders/active-takeaways`
6. WebSocket: `order_cancelled`, `order_updated`, `table_grid_updated` / `table_status_changed` (dine-in), `takeaways_updated` (takeaway)

## FR-C4: Auto-clear when last active item is cancelled
When the waiter cancels items one-by-one and the **last active line** is cancelled:
- Root order transitions to `status = cancelled`
- **Dine-in:** linked table becomes `available`; table grid refreshes
- **Takeaway:** order is removed from active takeaway lists immediately (API + WebSocket)
- Waiter active-order modal / cart bound to that order closes without page refresh

## FR-C1: Dine-in parity
Occupied table → **active-order modal** → per-item **Cancel Item** for non-cancelled lines.

## FR-C2: Walk-in takeaway parity
Active takeaway card → **active-order modal** (same component as dine-in) → per-item **Cancel Item** with identical confirmation and API call.

## FR-C3: No whole-order cancel button (UI)
Waiter and Cashier UIs do **not** expose a separate "Cancel Entire Order" control. Staff use item-level cancel only.

## Optional API (not primary UX)

| Method | Path | Note |
|--------|------|------|
| `POST` | `/api/orders/{order_id}/cancel` | Bulk-cancel all lines; retained for API/tests, not surfaced in waiter/cashier UI |

## Related
- `specs/feature-walk-in-takeaway/` — FR-W6, FR-W7 takeaway item cancel
- `PUT /api/orders/{order_id}/status` with `cancelled` (legacy)
