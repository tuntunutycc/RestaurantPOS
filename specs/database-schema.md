# Database Schema (Current)

Canonical ORM definition: `models.py`. Runtime column additions for SQLite dev: `main.py` lifespan migrations.

**Engine:** SQLite (dev/default). PostgreSQL planned for production.

---

## Entity relationship overview

```
Zone 1──* Table 1──* Order 1──* OrderItem *──1 MenuItem
                              ├──* PrintJob (*──0..1 OrderItem)
                              │
                              └── checked_out_by → User
OrderItem.created_by → User
Category 1──* MenuItem
User 1──* UserSession
User (actor/target) → AdminAuditLog
KitchenPrinterSettings (singleton id=1)
Printer (id PK) — dynamic named printers by role
PrinterRouteEndpoint (legacy route_key PK, optional fallback)
```

---

## `categories`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `name` | String(255) | Indexed |
| `printer_route` | String(32) nullable | `drinks` \| `food` \| null → food default at print |

---

## `menu_items`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | Integer PK | | |
| `name` | String(255) | | Indexed |
| `price` | Float | | Dine-in catalog base |
| `discount_price` | Float nullable | null | **Legacy** sale price; migrated at pricing time when `discount_type=none` |
| `discount_type` | String(32) | `none` | `none` \| `percentage` \| `fixed` |
| `discount_value` | Float | `0.0` | |
| `takeaway_price` | Float nullable | null | Optional takeaway base |
| `tax_type` | String(32) | `none` | `none` \| `percentage` \| `fixed` |
| `tax_value` | Float | `0.0` | |
| `description` | String(1024) nullable | | |
| `image_url` | String(512) nullable | | Retained for API/DB compatibility; Admin/Waiter UI no longer uploads or displays menu photos |
| `is_available` | Boolean | true | Indexed; soft delete sets `false` |
| `is_promoted` | Boolean | false | Waiter incentive reporting |
| `is_deleted` | Boolean | false | Soft delete |
| `deleted_at` | DateTime nullable | | |
| `modifiers_config` | JSON | `[]` | Modifier groups/options. An option is `{name, price}` plus optional `linked_menu_item_id` / `price_override` (keys absent when not linked; no column or migration - `specs/feature-linked-addons`) |
| `category_id` | FK → categories | | Required |

---

## `zones`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `name` | String(100) | Unique |

---

## `tables`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `name_or_number` | String(50) | Unique; ORM attr `name` (synonym `name_or_number`) |
| `zone_id` | FK → zones | |
| `status` | Enum | `available` \| `occupied` |

---

## `orders`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | Integer PK | | |
| `table_id` | FK → tables nullable | null | **NULL** = walk-in takeaway |
| `table_number` | Integer nullable | | **Legacy**; `table_id` is canonical |
| `order_type` | String(32) | `dine_in` | `dine_in` \| `takeaway` |
| `customer_name` | String(255) nullable | | Takeaway display name |
| `status` | String(50) | `pending` | `open`, `dining`, `paid`, `cancelled`, etc. |
| `total_amount` | Float | 0.0 | Sum of active line subtotals (open); finalized at checkout |
| `created_at` | DateTime | utcnow | |
| `payment_method` | String(32) nullable | | `cash` \| `kpay` \| `mmqr` \| `split` at checkout (`mobile_money` only on orders from before KPay/MMQR) |
| `cash_amount` | Float nullable | | Applied cash portion of bill |
| `kpay_amount` | Float nullable | | Part of the bill paid by KPay. Added at startup to existing databases |
| `mmqr_amount` | Float nullable | | Part of the bill paid by MMQR. Added at startup to existing databases |
| `mobile_money_amount` | Float nullable | | All mobile money = `kpay_amount + mmqr_amount`. Invariant: `cash_amount + kpay_amount + mmqr_amount == total_amount` |
| `amount_tendered` | Float nullable | | Cash physically given |
| `change_amount` | Float nullable | | |
| `tax_amount` | Float nullable | 0.0 | Receipt tax breakdown (sum of line taxes) |
| `discount_type` | String(32) nullable | | Order-level checkout discount: `percentage` \| `amount` |
| `discount_value` | Float nullable | 0.0 | |
| `checked_out_by_id` | FK → users nullable | | Cashier attribution (login user) |
| `cashier_name` | string nullable | | Free-text cashier label for receipt/terminal |
| `voucher_date` | String(8) nullable | | `YYYYMMDD` (Myanmar date of checkout). Set at checkout; NULL for unpaid / pre-feature orders. Added at startup |
| `voucher_seq` | Integer nullable | | 1, 2, 3 … within `voucher_date`. **Unique index `ux_orders_voucher (voucher_date, voucher_seq)`**. API exposes `voucher_no` = `YYYYMMDD-NNNN` (derived, not stored). See `specs/feature-voucher-number` |
| `created_by_id` | FK → users nullable | | **Order-taking staff** (waiter/cashier who opened the order). Set on first `POST /api/orders/submit` or `POST /api/orders/`. Immutable after create. API exposes as `waiter_name`. |

**Attribution split:** `Order.created_by_id` = who **opened** the order; `OrderItem.created_by_id` = who submitted each batch; `Order.checked_out_by_id` = authenticated cashier at checkout; `Order.cashier_name` = optional display name on the physical receipt.

---

## `order_items`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | Integer PK | | |
| `order_id` | FK → orders | | |
| `menu_item_id` | FK → menu_items | | |
| `quantity` | Integer | | CHECK > 0 |
| `subtotal` | Float | | Line total (discounted + tax + modifiers) × qty |
| `batch_number` | Integer | 1 | Kitchen ticket batch |
| `batch_status` | String(32) | `pending` | **Legacy**; always written; KDS uses `item_status` |
| `status` (DB) / `item_status` (ORM) | String(32) | `pending` | `pending` \| `cooking` \| `served` \| `cancelled` |
| `selected_modifiers` | JSON | `[]` | `[{name, price, group, quantity}]` sale-time snapshot; `linked_menu_item_id` is added only for an add-on that was a linked option at sale time |
| `note` | String(1024) nullable | | |
| `special_instructions` | String(1024) nullable | | Alias of note in API |
| `menu_item_name_at_sale` | String(255) nullable | | Snapshot; shown instead of the live name. Empty values of legacy rows are filled once from the live name at start-up |
| `unit_price_at_sale` | Float nullable | | Effective base at submit |
| `unit_discount_at_sale` | Float nullable | | Per-unit discount snapshot |
| `unit_tax_at_sale` | Float nullable | | Per-unit tax on discounted price |
| `category_name_at_sale` | String(255) nullable | | Snapshot; legacy empty values are filled at start-up (never with the `__system_archived__` bucket) |
| `is_takeaway` | Boolean | false | Per-line pricing flag |
| `created_by_id` | FK → users nullable | | Waiter/cashier attribution |

---

## `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `username` | String(255) | Unique |
| `password_hash` | String(255) | Never exposed in API |
| `role` | String(32) | `root` \| `admin` \| `account` \| `cashier` \| `waiter` |
| `pin_code` | String(4) nullable | Unique; returned in admin CRUD only |
| `is_deleted` | Boolean | Soft delete |
| `deleted_at` | DateTime nullable | |

---

## `user_sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `user_id` | FK → users | |
| `jti` | String(64) | Unique; JWT claim |
| `device_id` | String(128) | Single-device enforcement |
| `created_at` | DateTime | |
| `revoked_at` | DateTime nullable | |

---

## `admin_audit_logs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `actor_user_id` | FK → users | |
| `action` | String(64) | |
| `target_user_id` | FK → users nullable | |
| `detail_json` | JSON nullable | PIN values redacted |
| `created_at` | DateTime | |

---

## `kitchen_printer_settings`

Singleton row `id=1`: `backend` (`file` \| `escpos_network` \| `windows_printer`), `render_mode`, `paper_width_px`, `kitchen_slip_mode` (`per_item` default \| `combined`; String(16) NOT NULL, added at startup on existing databases), `kitchen_slip_copies` (Integer NOT NULL default 1; 1–3 copies of each combined slip, any other stored value behaves as 1; added at startup on existing databases).

---

## `receipt_settings`

Singleton row `id=1` (created by the first `PUT /api/admin/receipt-settings`; no row = all blank): `shop_name`, `address`, `phone`, `thank_you`, `footer_note`, all String NOT NULL default `''`. `address` and `footer_note` hold up to 3 lines separated by `\n`; every line at most 32 characters. Blank = built-in default (shop name -> `SHOP_NAME` env -> `My Restaurant`; thank-you -> `Thank you!`; the rest prints nothing). New table only; existing tables unchanged. See `specs/feature-receipt-text/`.

---

## `printer_route_endpoints`

Legacy PK `route_key` (`drinks` | `food` | `cashier`) — optional host fallback. Prefer unified `printers` table.

---

## `printers`

Dynamic named printers (Admin CRUD). LAN uses `host`/`port`; Windows cashier receipts use `windows_printer_name` when backend is `windows_printer`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Checkout `printer_id` for cashier role |
| `name` | String(64) | Label e.g. "Cashier 2" |
| `host` | String(255) nullable | LAN IP |
| `port` | Integer | Default 9100 |
| `windows_printer_name` | String(256) nullable | Windows spooler queue name |
| `role` | String(32) | `cashier` \| `kitchen` \| `bar` \| `other` |
| `is_active` | Boolean | |

Seed defaults: Default Cashier + Default Kitchen (optional Default Bar if drinks host in env/legacy). `kitchen_printer_settings.default_printers_seeded` prevents re-seeding after an admin deletes all printers. Category map: `food`→kitchen, `drinks`→bar (fallback kitchen).

---

## `print_jobs`

One row per slip sent to a printer (kitchen ticket per order line, or cashier receipt). See `specs/feature-print-queue/`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `order_id` | Integer FK `orders.id` | Required; deleted with the order |
| `order_item_id` | Integer FK `order_items.id` nullable | Single-item kitchen slips only; null for receipts and combined kitchen slips (their lines are in `payload.ticket.items[].order_item_id`) |
| `kind` | String(16) | `kitchen` \| `receipt` |
| `route` | String(32) | `food` \| `drinks` \| `cashier` |
| `printer_id` | Integer nullable | Cashier printer chosen at checkout (no FK) |
| `payload` | JSON | Data needed to render the slip again |
| `print_status` | String(16) | `pending` \| `printed` \| `failed` (check constraint `ck_print_jobs_status_valid`) |
| `error_message` | String(1024) nullable | Reason of the last failure |
| `attempts` | Integer | Send attempts |
| `created_at`, `updated_at` | DateTime | UTC |
| `printed_at` | DateTime nullable | UTC |

Indexes: `(order_id, print_status)`, `(print_status, created_at)`. Created by `Base.metadata.create_all` at startup (no `ALTER TABLE`). On startup every `pending` row becomes `failed`.

---

## Pricing snapshots (read-only contract)

At order submit, server persists per line:

1. `unit_price_at_sale` = effective base (`takeaway_price` or `price`)
2. `unit_discount_at_sale` from `discount_type` / `discount_value` (or legacy `discount_price`)
3. `unit_tax_at_sale` on **discounted** price
4. `subtotal` = `(discounted + tax + modifiers) × quantity`

See `specs/feature-menu-item-discount/` and `specs/feature-menu-item-tax/`.

**Start-up backfill (`main._backfill_order_item_snapshots`)**: `menu_item_name_at_sale` / `category_name_at_sale` that are `NULL` or blank are filled from the live menu item / category. Real values are never overwritten; `unit_price_at_sale` is never invented (the price of an old sale is unknown). A legacy line's name is therefore frozen at the first start after the upgrade. Idempotent; a failure is logged and does not stop the server. See `specs/feature-snapshot-first-names/`.

---

## `predefined_instructions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `text` | String(255) | Unique quick-tag label |

See `specs/feature-predefined-instructions/`.

---

## Legacy / compatibility notes

| Item | Status |
|------|--------|
| `Order.table_number` | Written for compat; prefer `table_id` |
| `OrderItem.batch_status` | Written `"pending"`; not used for workflow |
| `MenuItem.discount_price` | Legacy admin UI; server migrates at pricing |
| `kitchen` user role | Cannot authenticate (removed from RBAC) |
