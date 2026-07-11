# API Reference (Current)

All REST routes use prefix `/api` unless noted. Auth: `Authorization: Bearer <JWT>` except public setup routes.

Role constants: `rbac.py`. Request/response shapes: `schemas.py`.

---

## Setup (public)

| Method | Path | Access | Notes |
|--------|------|--------|-------|
| GET | `/api/setup/status` | Public | `{ needs_setup: bool }` |
| POST | `/api/setup/root` | Public when no root | Creates first root; returns token |

---

## Auth

| Method | Path | Roles | Notes |
|--------|------|-------|-------|
| POST | `/api/auth/login` | `root`, `admin` only | Password; cross-role → `403` |
| POST | `/api/auth/login-pin` | `cashier`, `waiter`, `account` | 4-digit PIN; cross-role → `403` |
| GET | `/api/auth/me` | Authenticated | Validates JWT + session `jti` |
| POST | `/api/auth/change-password` | `root`, `admin` | PIN roles → `403` |

Body: login requests accept optional `device_id` for session binding.

---

## Root admin (`root` only)

| Method | Path |
|--------|------|
| GET | `/api/root/admins` |
| POST | `/api/root/admins` |
| PUT | `/api/root/admins/{user_id}` |
| DELETE | `/api/root/admins/{user_id}` |
| POST | `/api/root/admins/{user_id}/reset-password` |
| GET | `/api/root/audit-logs` |

---

## Staff (`ADMIN_PANEL_ROLES`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/admin/users` | Lists staff; includes `pin_code` |
| POST | `/api/admin/users` | `StaffRole` only; `admin`/`root` → `403` |
| PUT | `/api/admin/users/{user_id}` | |
| DELETE | `/api/admin/users/{user_id}` | Soft delete |

---

## Categories & menu (`ADMIN_PANEL_ROLES` for mutations)

| Method | Path |
|--------|------|
| GET/POST | `/api/categories/` |
| PUT/DELETE | `/api/categories/{category_id}` |
| GET/POST | `/api/menu-items/` |
| POST | `/api/menu-items/upload` |
| PUT | `/api/menu-items/{item_id}` |
| PUT | `/api/menu-items/{item_id}/toggle-promoted` |
| PUT | `/api/menu-items/{item_id}/toggle-availability` |
| DELETE | `/api/menu-items/{item_id}` |

**MenuItem fields:** `price`, `discount_price` (legacy), `discount_type`, `discount_value`, `takeaway_price`, `tax_type`, `tax_value`, `modifiers_config`, etc.

---

## Zones & tables (`ADMIN_PANEL_ROLES` for mutations)

| Method | Path |
|--------|------|
| GET/POST | `/api/zones` |
| PUT/DELETE | `/api/zones/{zone_id}` |
| GET/POST | `/api/tables` |
| PUT/DELETE | `/api/tables/{table_id}` |
| GET | `/api/tables/status` |
| GET | `/api/tables/grid` |

---

## Kitchen printers (`ADMIN_PANEL_ROLES`)

| Method | Path |
|--------|------|
| GET/PUT | `/api/admin/kitchen-printers` |

---

## Orders (`POS_ORDER_ROLES` except checkout)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| POST | `/api/orders/` | `OrderCreateResponse` | **Legacy** create/append; no batch/kitchen print |
| GET | `/api/orders/` | `list[OrderResponseDetail]` | Optional `status` filter |
| GET | `/api/orders/active-takeaways` | `list[ActiveTakeawayOrderResponse]` | `order_type=takeaway`, not paid/cancelled |
| GET | `/api/orders/tables` | `list[OrderResponseDetail]` | Checkout-ready tables |
| GET | `/api/orders/active-by-table/{table_id}` | `OrderResponseDetail` | |
| PUT | `/api/orders/{order_id}/status` | `OrderStatusUpdateResponse` | Legacy bulk cancel path |
| POST | `/api/orders/{order_id}/cancel` | `OrderStatusUpdateResponse` | API/test whole-order cancel |
| GET | `/api/orders/{order_id}/details` | `OrderDetailsResponse` | **Full breakdown** + item snapshots |
| PUT | `/api/orders/{order_id}/items/{item_id}/status` | `OrderResponseDetail` | Item status incl. `cancelled` |
| POST | `/api/orders/submit` | `OrderSubmitResponse` | **Primary** submit; batching + kitchen print |

### Checkout (`CHECKOUT_ROLES`: root, admin, cashier)

| Method | Path |
|--------|------|
| POST/PUT | `/api/orders/{order_id}/checkout` |

**Checkout body:** `payment_method`, `amount_tendered`, optional `discount_type` (`percentage`|`amount`), `discount_value`.

---

## Order contracts (key fields)

### `OrderSubmitRequest`
- `table_id` — **FK to `tables.id`** (not legacy table number)
- `order_type` — `dine_in` \| `takeaway`
- `customer_name` — optional for takeaway
- `order_id` — optional append to existing order
- `items[]` — `{ menu_item_id, quantity, is_takeaway, selected_modifiers, note }`

### `OrderDetailsResponse` / `ActiveTakeawayOrderResponse`
- `breakdown_subtotal`, `breakdown_discount_total`, `breakdown_tax_total`, `breakdown_grand_total`
- `items[]` → `OrderItemDetailsResponse` with `unit_price_at_sale`, `unit_discount_at_sale`, `unit_tax_at_sale`, `is_takeaway`

### `OrderResponseDetail` (list endpoints)
- Does **not** include order-level `breakdown_*` fields
- `OrderItemDetail` includes `unit_tax_at_sale` only (not full pricing snapshots)

Use **`GET /api/orders/{id}/details`** for waiter sidebar breakdown.

---

## Reports

| Method | Path | Role notes |
|--------|------|------------|
| GET | `/api/reports/summary/today` | Cashier = own checkout total |
| GET | `/api/reports/top-items` | Dashboard roles |
| GET | `/api/reports/hourly-trend` | |
| GET | `/api/reports/daily-sales` | Account ≤ 90 days |
| GET | `/api/reports/monthly-sales` | Cashier excluded |
| GET | `/api/reports/category-sales` | |
| GET | `/api/reports/cancellations` | |
| GET | `/api/reports/sales/by-cashier` | root, admin, account; not cashier/waiter |
| GET | `/api/reports/sales/by-order-staff` | root, admin (all); waiter (self); account → 403 |
| GET | `/api/reports/sales/promoted-by-waiter` | root, admin; waiter self |

Query params: `start_date`, `end_date` where applicable.

---

## WebSocket

| Endpoint | Events (non-exhaustive) |
|----------|-------------------------|
| `/ws` | `new_order_batch`, `order_updated`, `order_cancelled`, `takeaways_updated`, `table_status_changed`, `table_grid_updated`, `menu_item_added`, `menu_item_updated`, `menu_item_availability_toggled` |

Payloads are feature-specific; see individual feature specs.

---

## Primary vs legacy paths

| Use case | Preferred endpoint | Legacy |
|----------|-------------------|--------|
| Waiter submit | `POST /api/orders/submit` | `POST /api/orders/` |
| Price breakdown UI | `GET /api/orders/{id}/details` | Derive from list responses |
| Item cancel | `PUT .../items/{id}/status` | `POST .../cancel`, `PUT .../status` |
