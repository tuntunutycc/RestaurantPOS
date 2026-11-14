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

**Counter UI payload (`static/counter.js` `#user-form`):** `{ username, role, pin_code }` — PIN required for `cashier`/`waiter`/`account`; no `password` field.

---

## Categories & menu

| Method | Path | Roles |
|--------|------|-------|
| GET | `/api/categories/` | authenticated |
| POST | `/api/categories/` | `root`, `admin` |
| PUT/DELETE | `/api/categories/{category_id}` | `root`, `admin` |
| GET | `/api/menu-items/` | authenticated |
| POST | `/api/menu-items/` | **`root`, `admin` only** |
| POST | `/api/menu-items/upload` | **`root`, `admin` only** |
| PUT | `/api/menu-items/{item_id}` | **`root`, `admin` only** (full update) |
| PATCH | `/api/menu-items/{item_id}/availability` | **`root`, `admin`, `cashier`** — body `{ "is_available": boolean }` |
| PUT | `/api/menu-items/{item_id}/toggle-promoted` | `root`, `admin` |
| PUT | `/api/menu-items/{item_id}/toggle-availability` | `root`, `admin` (legacy flip; prefer PATCH) |
| DELETE | `/api/menu-items/{item_id}` | **`root`, `admin` only** |

See `specs/feature-menu-rbac/` for cashier availability-only contract.

**MenuItem fields:** `price`, `discount_price` (legacy), `discount_type`, `discount_value`, `takeaway_price`, `tax_type`, `tax_value`, `modifiers_config`, etc.

**Modifiers:** `modifiers_config` = `[{ group, is_required, options: [{ name, price }] }]`. Order lines use `selected_modifiers: [{ name, price, group?, quantity? }]` (`quantity` default 1; money = `sum(price * quantity)`).

**Counter UI create payload (`static/counter.js` `#form-menu-item`):** sends all `MenuItemCreate` fields including admin-edited `modifiers_config` (empty when no groups). Legacy `#item-discount-price` maps to `discount_price`. Edit mode omits `is_available` so sold-out state is preserved.

---

## Zones & tables (`ADMIN_PANEL_ROLES` for mutations)

| Method | Path | Roles | Notes |
|--------|------|-------|-------|
| GET/POST | `/api/zones` | GET: admin; POST: admin | |
| PUT/DELETE | `/api/zones/{zone_id}` | admin | |
| GET/POST | `/api/tables` | GET/POST: admin | **No pagination** — full list |
| PUT/DELETE | `/api/tables/{table_id}` | admin | |
| GET | `/api/tables/status` | authenticated | All zones + nested tables (**no pagination**) |
| GET | `/api/tables/grid` | authenticated | All zones + table status/active order (**no pagination**) |

**Counter UI table create (`static/counter.js` kanban):** `{ name, zone_id, status: "available" }` — `zone_id` integer from zone column.

See `specs/feature-table-all-view/` for ALL-tab floor grid UX.

---

## Kitchen printers (`ADMIN_PANEL_ROLES`)

| Method | Path | Notes |
|--------|------|-------|
| GET/PUT | `/api/admin/kitchen-printers` | Global backend: `file` \| `escpos_network` \| `windows_printer` |
| GET | `/api/admin/windows-printers` | List installed Windows queues (`available`, `printers[]`, `message`) |

## Cashier / terminal printers (dynamic)

| Method | Path | Roles | Notes |
|--------|------|-------|-------|
| GET | `/api/printers` | Admin: all; Checkout: `?role=cashier` | Unified `Printer` rows; includes `windows_printer_name` |
| POST | `/api/printers` | Admin | Create (optional `windows_printer_name`) |
| PUT | `/api/printers/{id}` | Admin | Update |
| DELETE | `/api/printers/{id}` | Admin | Delete |

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
| POST/PUT | `/api/orders/{order_id}/checkout` | `OrderCheckoutResponse` |

**Checkout body (`OrderCheckoutRequest`):**
- `payment_method` — `cash` \| `mobile_money` \| `split` (optional when `cash_amount` / `mobile_money_amount` provided)
- `amount_tendered` — required for legacy single-method; for split, cash given
- optional `cash_amount`, `mobile_money_amount` — tendered/applied per method; sum must be ≥ final total
- optional `discount_type` (`percentage`|`amount`), `discount_value`
- `issue_receipt` — bool, default `true`
- `printer_id` — optional cashier printer id
- `cashier_name` — optional free-text label printed on the receipt (blank → omitted / stored null)

**Checkout response (`OrderCheckoutResponse`):** same fields as `OrderResponseDetail` plus optional `warning` (e.g. printer offline). Payment success is always reflected by HTTP 200 + `status=paid`; print failures do not roll back checkout.

**Admin printers:** `GET/PUT /api/admin/kitchen-printers` manages global print mode only (`file` \| `escpos_network` \| `windows_printer`). `windows_printer` sends **cashier receipts** to a Windows queue; kitchen/bar keep **LAN** when `Printer.host` is set (else file). Named printers use `/api/printers` CRUD with roles `cashier|kitchen|bar|other` and optional `windows_printer_name`. `GET /api/admin/windows-printers` lists installed queues when `pywin32` is available. Category `food`→kitchen, `drinks`→bar (fallback kitchen). Cashier UI persists selection in `localStorage.selectedCashierPrinterId` and display name in `localStorage.currentCashierName`.

---

## Analytics

| Method | Path | Response | Role notes |
|--------|------|----------|------------|
| GET | `/api/analytics/sales-breakdown` | `SalesBreakdownResponse` | root, admin, account (store-wide); cashier (own checkouts). Waiter → **403** |

**`SalesBreakdownResponse`:**
```json
{
  "today": { "cash": 0, "mobile_money": 0, "total": 0 },
  "month": { "cash": 0, "mobile_money": 0, "total": 0 }
}
```

Paid/completed orders only. `total == cash + mobile_money`.

---

## Order contracts (key fields)

### `OrderSubmitRequest`
- `table_id` — **FK to `tables.id`** (not legacy table number)
- `order_type` — `dine_in` \| `takeaway`
- `customer_name` — optional for takeaway
- `order_id` — optional append to existing order
- `items[]` — `{ menu_item_id, quantity, is_takeaway, selected_modifiers, note }`

### `OrderDetailsResponse` / `ActiveTakeawayOrderResponse`
- `order_type`, `table_id`, `customer_name`
- `waiter_name` — resolved from `Order.created_by_id` (order-taking staff)
- `served_by_name` — latest batch `OrderItem.created_by_id` (add-on staff when different)
- `breakdown_subtotal`, `breakdown_discount_total`, `breakdown_tax_total`, `breakdown_grand_total`
- `items[]` → `OrderItemDetailsResponse` with `unit_price_at_sale`, `unit_discount_at_sale`, `unit_tax_at_sale`, `is_takeaway`, per-line `waiter_name`

### `OrderResponseDetail` (list endpoints)
- `waiter_name`, `served_by_name` (same resolution as above)
- Does **not** include order-level `breakdown_*` fields
- `OrderItemDetail` includes `unit_tax_at_sale` only (not full pricing snapshots)

Use **`GET /api/orders/{id}/details`** for waiter active-order modal / cart breakdown.

---

## Kitchen printers (`ADMIN_PANEL_ROLES`)

| Method | Path | Notes |
|--------|------|-------|
| GET/PUT | `/api/admin/kitchen-printers` | Includes `windows_printer` backend |
| GET | `/api/admin/windows-printers` | Installed Windows queues for cashier setup |

---

## Predefined instructions

| Method | Path | Role notes |
|--------|------|------------|
| GET | `/api/predefined-instructions` | `POS_ORDER_ROLES` |
| POST | `/api/predefined-instructions` | `ADMIN_PANEL_ROLES` |
| DELETE | `/api/predefined-instructions/{instruction_id}` | `ADMIN_PANEL_ROLES` |

Menu items include `category_id`; categories at `GET /api/categories/` — used for client-side category pill filtering (`specs/feature-menu-category-navigation/`).

---

## Reports

| Method | Path | Role notes |
|--------|------|------------|
| GET | `/api/reports/summary/today` | Cashier = own checkout total |
| GET | `/api/reports/sales` | root, admin, account; `period=daily\|monthly` + `date`; tax-aware totals |
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
