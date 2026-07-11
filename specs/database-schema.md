# Database Schema (Current)

Canonical ORM definition: `models.py`. Runtime column additions for SQLite dev: `main.py` lifespan migrations.

**Engine:** SQLite (dev/default). PostgreSQL planned for production.

---

## Entity relationship overview

```
Zone 1──* Table 1──* Order 1──* OrderItem *──1 MenuItem
                              │
                              └── checked_out_by → User
OrderItem.created_by → User
Category 1──* MenuItem
User 1──* UserSession
User (actor/target) → AdminAuditLog
KitchenPrinterSettings (singleton id=1)
PrinterRouteEndpoint (route_key PK)
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
| `image_url` | String(512) nullable | | |
| `is_available` | Boolean | true | Indexed; soft delete sets `false` |
| `is_promoted` | Boolean | false | Waiter incentive reporting |
| `is_deleted` | Boolean | false | Soft delete |
| `deleted_at` | DateTime nullable | | |
| `modifiers_config` | JSON | `[]` | Modifier groups/options |
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
| `payment_method` | String(32) nullable | | Set at checkout |
| `amount_tendered` | Float nullable | | |
| `change_amount` | Float nullable | | |
| `tax_amount` | Float nullable | 0.0 | Receipt tax breakdown (sum of line taxes) |
| `discount_type` | String(32) nullable | | Order-level checkout discount: `percentage` \| `amount` |
| `discount_value` | Float nullable | 0.0 | |
| `checked_out_by_id` | FK → users nullable | | Cashier attribution |
| `created_by_id` | FK → users nullable | | **Order-taking staff** (waiter/cashier who opened the order). Set on first `POST /api/orders/submit` or `POST /api/orders/`. Immutable after create. API exposes as `waiter_name`. |

**Attribution split:** `Order.created_by_id` = who **opened** the order; `OrderItem.created_by_id` = who submitted each batch; `Order.checked_out_by_id` = cashier at checkout.

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
| `selected_modifiers` | JSON | `[]` | |
| `note` | String(1024) nullable | | |
| `special_instructions` | String(1024) nullable | | Alias of note in API |
| `menu_item_name_at_sale` | String(255) nullable | | Snapshot |
| `unit_price_at_sale` | Float nullable | | Effective base at submit |
| `unit_discount_at_sale` | Float nullable | | Per-unit discount snapshot |
| `unit_tax_at_sale` | Float nullable | | Per-unit tax on discounted price |
| `category_name_at_sale` | String(255) nullable | | |
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

Singleton row `id=1`: `backend`, `render_mode`, `paper_width_px`.

---

## `printer_route_endpoints`

PK `route_key`: LAN `host`, `port` per kitchen route.

---

## Pricing snapshots (read-only contract)

At order submit, server persists per line:

1. `unit_price_at_sale` = effective base (`takeaway_price` or `price`)
2. `unit_discount_at_sale` from `discount_type` / `discount_value` (or legacy `discount_price`)
3. `unit_tax_at_sale` on **discounted** price
4. `subtotal` = `(discounted + tax + modifiers) × quantity`

See `specs/feature-menu-item-discount/` and `specs/feature-menu-item-tax/`.

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
