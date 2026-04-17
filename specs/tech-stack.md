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
  - `routers/auth.py`: login/token issuance
  - `routers/orders.py`: order lifecycle, checkout, kitchen ticket dispatch (mock)
  - `routers/menu.py`: categories + menu item CRUD
  - `routers/tables.py`: zones/tables management
  - `routers/users.py`: admin staff management
  - `routers/reports.py`: analytics endpoints
- Realtime: WebSocket broadcaster in `websocket_manager.py`
- Data access: SQLAlchemy session from `database.py`
- Auth: JWT utilities in `auth.py`
- Request/response contracts: Pydantic models in `schemas.py`

### Database (Schema)
- ORM entities are defined in `models.py`
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
- **Checkout tax rule (fixed 5%):** tax is calculated **after** discount is applied (tax on net amount), with backend as source of truth:
  - `taxable_amount = max(subtotal - discount_amount, 0.0)`
  - `tax_amount = _round_money(taxable_amount * 0.05)`
  - `grand_total = _round_money(taxable_amount + tax_amount)`
  - Safety constraint: if discount would make taxable amount negative, taxable amount, tax amount, and grand total are clamped safely at `0.0`.
- Prefer explicit rounding rules (currently many computations round to 2 decimals; later we will move to `Decimal` + `Numeric` for stronger guarantees).
- Always validate input constraints on the server:
  - quantity >= 1
  - valid enum literals for statuses
  - tendered >= final total on checkout

## Test Strategy (required for SDD merge gate)
- Introduce automated tests with a backend test runner (e.g., `pytest`) for each feature.
- Tests must verify:
  - correct HTTP response schemas
  - key business invariants (totals, cancellation effects, checkout validation)
  - role enforcement behavior (admin/waiter/cashier)

