# Tech Stack

## Overview
This POS system is currently built with:
- **Frontend:** JavaScript static UI (served from FastAPI) for waiter/cashier/admin screens
- **Backend:** Python **FastAPI** for REST APIs + WebSocket realtime
- **Database:** **SQLAlchemy** ORM with models defined in `models.py`
  - **PostgreSQL:** planned for later (production target), currently defaulting to SQLite for local/dev

## Architecture (Current)
### Frontend (JavaScript UI)
- Frontend lives under `static/` and is served by FastAPI (HTML pages + plain JS modules like `waiter.js`, `counter.js`, `table-dashboard.js`)
- Styling uses Tailwind CSS via CDN and charts use Chart.js via CDN
- Auth token is used by client requests (JWT stored in `localStorage`)
- Realtime updates use WebSocket events from the backend (single `/ws` endpoint)

### Backend (FastAPI)
- Entry point: `main.py`
- API routers: `routers/*`
  - `routers/setup.py`: first-root bootstrap status
  - `routers/auth.py`: login/token issuance (password + PIN)
  - `routers/root_users.py`: root admin account governance + audit logs
  - `routers/users.py`: admin staff CRUD
  - `routers/orders.py`: order lifecycle, checkout, kitchen ticket dispatch
  - `routers/menu.py`: categories + menu item CRUD
  - `routers/tables.py`: zones/tables management
  - `routers/kitchen_printers.py`: kitchen printer settings
  - `routers/reports.py`: analytics endpoints
- Realtime: WebSocket broadcaster in `websocket_manager.py`
- Data access: SQLAlchemy session from `database.py`
- Auth: JWT utilities in `auth.py`
- Request/response contracts: Pydantic models in `schemas.py`

### Database (Schema)
- ORM entities are defined in `models.py`
- **Canonical schema doc:** `specs/database-schema.md`
- **API catalog:** `specs/api-reference.md`
- Startup bootstrapping and “ad-hoc” schema evolution happens in `main.py` (runtime `ALTER TABLE` / SQLite repair patterns)
- For production-grade evolution, we will later adopt proper migrations (e.g., Alembic) when moving fully to PostgreSQL.

## “Next.js / PostgreSQL” Notes
- **Next.js:** not present in the current repo; the current UI is static JavaScript. Next.js (or another richer frontend) is a planned later stage only.
- **PostgreSQL:** targeted for later production. Current code paths may include SQLite-specific repair/startup logic; contract-driven SDD will help keep migrations safe when we switch engines.

## API Naming Conventions
- All REST endpoints are under the `/api` prefix.
- Resource names are plural and use nouns (e.g., `orders`, `menu-items`, `tables`, `categories`).
- Mutations use HTTP verbs:
  - `GET` for reads
  - `POST` for create/submit actions
  - `PUT` for updates / idempotent updates
  - `DELETE` for deletions (where supported)
- Request and response bodies must be expressed with Pydantic schemas:
  - Update `schemas.py` first
  - Use FastAPI `response_model=...` and typed request models

## State Management Conventions
- Frontend state is a UI convenience layer (cart, current tab, selections).
- **Backend is source of truth** for:
  - order totals
  - order status / item status rules
  - payment finalization
- Realtime (`/ws`) is used to refresh UI views:
  - order batches for kitchen/KDS
  - table grid updates

## Realtime Event Contract (WebSocket)
- WebSocket events must be treated as part of the system contract.
- Event names follow a stable pattern like:
  - `new_order_batch`
  - `order_updated`
  - `takeaways_updated`
  - `table_status_changed`
  - `table_grid_updated`
- Each event payload should be documented in the feature spec (and validated where feasible).

## Coding Standards (SDD-aligned)
- **Spec-first development:** implement a feature only after writing/agreeing a spec and contract impact.
- **Contract-first:** update `schemas.py` and endpoint `response_model` before implementing UI changes.
- **Money correctness:** totals must be deterministic and consistent across:
  - submit/append
  - item status changes
  - checkout
  - discount calculations
- **Checkout tax rule (per-item, tax after discount):** each `MenuItem` has `discount_type`/`discount_value` and `tax_type`/`tax_value`. At submit:
  - `effective_base` = `takeaway_price` (if line takeaway) else `price`
  - `unit_discount` from discount config (legacy `discount_price` migrated at runtime)
  - `unit_tax` calculated on **discounted** price
  - line `subtotal` = `(discounted + unit_tax + modifiers) × quantity`
- At checkout:
  - `subtotal = sum(non-cancelled line subtotals)` (tax-inclusive)
  - `tax_amount = sum(unit_tax_at_sale × quantity)` (receipt breakdown)
  - `discount_amount` from **order-level** discount on `subtotal`
  - `grand_total = _round_money(max(subtotal - discount_amount, 0))`
  - Legacy fixed 5% order-level tax is **replaced** by per-item tax.
- **Waiter breakdown fields** on `GET /api/orders/{id}/details`: `breakdown_subtotal`, `breakdown_discount_total`, `breakdown_tax_total`, `breakdown_grand_total`
- Prefer explicit rounding rules (currently many computations round to 2 decimals; later we will move to `Decimal` + `Numeric` for stronger guarantees).
- Always validate input constraints on the server:
  - quantity >= 1
  - valid enum literals for statuses
  - tendered >= final total on checkout

## Mandatory Data Integrity Rules (Deletion Safety)
- **Historical data is immutable in meaning:** deleting reference/master entities must not remove or rewrite paid/completed historical order facts.
- **No destructive cascade on critical business history:** avoid `CASCADE` deletes on relationships that can erase orders/order-items/reporting evidence.
- **Preferred FK behavior by entity type:**
  - `User` references from transactional rows (e.g., `OrderItem.created_by_id`) must use `ON DELETE SET NULL` (or equivalent app-level nulling) so historical rows survive.
  - `Table` references from `Order.table_id` must allow `NULL`; deleting a table must detach historical orders (`table_id = NULL`).
  - `MenuItem` references from `OrderItem.menu_item_id` must preserve historical line items:
    - preferred: **soft delete** menu items (`is_deleted`) and keep FK intact, or
    - alternative: nullable FK + snapshot columns on `OrderItem` (e.g., item name/price at sale time) before using `SET NULL`.
  - `Order` deletion is disallowed for paid/completed history. Cancellation must be represented by status transitions, not hard-delete.
- **Backend null-safety contract:** API responses and report queries must never assume related rows exist; always use fallback labels for deleted references.
  - Required fallback examples:
    - deleted user -> `[Deleted User]`
    - deleted menu item -> `[Deleted Item]`
    - deleted table link -> `[Deleted Table]` (or existing detached table fallback)
- **Frontend null-safety contract:** UI rendering must tolerate missing related objects (`null` foreign references) without throwing, and must display explicit fallback labels.
- **Soft-delete policy (default for audit-heavy entities):**
  - apply soft delete to `users` and `menu_items` (at minimum), using `is_deleted`, `deleted_at`.
  - hidden from default active lists, but preserved for historical joins/reports/admin audit views.
- **Report stability invariant:** Daily/monthly/category/cancellation reports must remain queryable and correct even when referenced user/menu/table records are deleted or soft-deleted.
- **Test gate for deletion changes:** any deletion behavior change requires invariant tests proving:
  - historical orders/order-items persist,
  - reports still compute successfully,
  - UI/API fallback labels are returned for missing relations.

## Kitchen & Cashier Printing
- Printing is a **server-side** side effect (kitchen after order submit; cashier receipt after checkout commit).
- Supported backends:
  - `file` for local/dev validation without physical printers
  - `escpos_network` for LAN Xprinter/ESC/POS devices
- Supported render modes:
  - `text`: ESC/POS text payload (compatible fallback)
  - `image`: server-rendered raster image payload for Myanmar text compatibility
- Image mode auto-loads bundled Myanmar and Latin fallback fonts from `assets/fonts/`, with `KITCHEN_PRINT_FONT_PATH` available only as an override.
- Endpoint routes: menu categories stay **`drinks`** / **`food`**. Dispatch maps `food`→`kitchen` printer role and `drinks`→`bar` (fallback `kitchen`).
- Unified **`printers`** table (`Printer`: name, host, port, role=`cashier|kitchen|bar|other`, is_active). Admins CRUD unlimited printers via `GET/POST/PUT/DELETE /api/printers`.
- Fresh seed: **Default Cashier** + **Default Kitchen** only (`seed_default_printers` / `scripts/seed_root.py`).
- Global print mode (backend/render/paper): `GET/PUT /api/admin/kitchen-printers` (no fixed host cards).
- Checkout `printer_id` + Cashier UI `localStorage.selectedCashierPrinterId` for terminal selection.
- Kitchen print failures must not roll back order submit. Cashier receipt print failures must not roll back checkout; API may return `warning`.
- See `specs/feature-kitchen-printing/`, `specs/feature-cashier-receipt-printing/`, `specs/feature-dynamic-printer-management/`.

## Test Strategy (required for SDD merge gate)
- Introduce automated tests with a backend test runner (e.g., `pytest`) for each feature.
- Current suite (2026-07-06): **160 passed** — RBAC, kitchen printing, table management, walk-in takeaway, per-item tax/discount, waiter breakdown, money invariants, contracts.
- Feature specs must maintain `validation.md` with honest automated vs manual checklist separation.

## RBAC (current)
- Five roles: `root`, `admin`, `account`, `cashier`, `waiter`.
- Session-aware JWT (`jti` claim) with single-device enforcement for staff/account roles.
- Spec: `specs/feature-rbac/`; constants: `rbac.py`.
- Tests must verify:
  - correct HTTP response schemas
  - key business invariants (totals, cancellation effects, checkout validation)
  - role enforcement behavior (admin/waiter/cashier)

