# Mission

## Purpose
Build a fully functional, Myanmar-restaurant POS system that is reliable in daily use and designed so new features can be added safely over time.

## Target Audience
- `root`: top-level operator; manages admins, full reports, admin-panel POS configuration
- `admin`: manages staff accounts, menu, categories, zones, tables, kitchen printers, operational reports
- `account`: read-only financial reports (up to 90 days)
- `cashier`: counter checkout, may use waiter screen for ordering, own daily sales
- `waiter`: tablet order taking; no checkout

> Legacy three-role docs (`FULL_DOCUMENTATION_*.md`) predate RBAC expansion. Prefer `specs/feature-rbac/`, `specs/database-schema.md`, `specs/api-reference.md`, and `CHANGELOG.md`.

## Core Functional Requirements
### Authentication & Roles
- **Strict auth split:** `root`/`admin` → username + password (`POST /api/auth/login`); `cashier`/`waiter`/`account` → 4-digit PIN (`POST /api/auth/login-pin`) only
- Role-based access control for admin/waiter/cashier/account actions
- JWT-based session with single-device enforcement for PIN roles

### Menu Management
- CRUD for `categories` and `menu items`
- Enable/disable menu items (`is_available`)
- Support modifiers (required/optional groups and options with prices)
- Support menu item images

### Order Taking (Dine-in & Takeaway)
- Create a new order or append items to the existing open/dining order for a table
- **Walk-in takeaway:** `order_type=takeaway`, `table_id=NULL` — no dummy table
- Support `batch_number` behavior for kitchen ticketing (each submit becomes a new batch via `POST /api/orders/submit`)
- Capture per-line details:
  - quantity
  - selected modifiers
  - note / special instructions
  - per-line `is_takeaway` (dual pricing)
  - waiter attribution (`created_by_id` on each line)
- Per-item **discount** then **tax** pricing (see `specs/feature-menu-item-discount/`, `specs/feature-menu-item-tax/`)

### Realtime Kitchen / UI Updates
- Kitchen/KDS receives new order batches in realtime
- Table grid and cashier views update in realtime (WebSocket events)

### Order Status & Cancellation
- Update item-level status (e.g., `pending`, `cooking`, `served`, `cancelled`) via `PUT /api/orders/{id}/items/{item_id}/status`
- Item-level cancel is the primary waiter UX (no whole-order cancel button)
- When all items are cancelled, order auto-clears to `cancelled` and releases table / removes from active takeaway list
- Ensure order totals reflect cancellation rules consistently (data correctness is critical)

### Checkout (Cashier)
- Finalize payment for an order:
  - `payment_method`
  - `amount_tendered`
  - optional discount (`percentage` or fixed `amount`)
  - compute `change_amount`
- Ensure checkout validates tender amount >= final total
- Mark order status as paid and return receipt details

### Reporting & Analytics
- Sales summaries (today, daily trend, monthly trend)
- Top selling items and cancellation analytics

## Success Criteria (Mission KPIs)
- Low `order error rate` (especially totals and order state)
- Fast `checkout time`
- Low `staff training/adoption time` (clear UX + predictable behavior)

