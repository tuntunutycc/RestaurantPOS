# Restaurant POS System

Restaurant POS built with **FastAPI + SQLAlchemy** (backend) and **Vanilla HTML/JS + Tailwind** (frontend).

> **SDD docs:** Governance and feature contracts live under `specs/`. For the latest RBAC and feature state, prefer `specs/feature-*/` and `CHANGELOG.md` over `FULL_DOCUMENTATION_*.md` (may predate RBAC). Next.js is a **future** frontend target (see `specs/roadmap.md` Phase 3).

This README is architecture-first so new programmers (and AI agents) can quickly understand how the system is wired before changing features.

---

## 1) Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic, WebSocket
- **Database:** SQLite (default dev), PostgreSQL-ready via `DATABASE_URL`
- **Frontend:** Static HTML + Vanilla JS + Tailwind CDN + Chart.js
- **Auth:** JWT (Bearer token), role-based access checks
- **UX Utilities:** `CustomDialog` (no native alert/confirm/prompt), custom i18n (`en` / `my`)

---

## 2) High-Level Architecture

### Backend core files

- `main.py`
  - FastAPI app bootstrap
  - Startup/lifespan DB patching and seeding
  - Static page routes (`/waiter`, `/counter`, `/table-dashboard`, `/login`, `/pin-login`)
  - WebSocket endpoint (`/ws`)
- `database.py`
  - `DATABASE_URL` loading
  - SQLAlchemy engine/session/base
- `auth.py`
  - JWT create/verify
  - password hash/verify
  - role dependency helpers
- `models.py`
  - ORM entities (`User`, `Category`, `MenuItem`, `Zone`, `Table`, `Order`, `OrderItem`)
- `schemas.py`
  - request/response schemas for routers
- `websocket_manager.py`
  - connection tracking + broadcast helper

### API routers

- `routers/auth.py` - login + who-am-I
- `routers/menu.py` - category/menu CRUD + availability toggle + upload
- `routers/orders.py` - ordering, takeaway list, item status updates (served/pending/cancelled), checkout
- `routers/tables.py` - zones/tables CRUD + status/grid
- `routers/users.py` - admin staff management
- `routers/reports.py` - summary + overview/history/insights reporting APIs

### Frontend pages

- `static/login.html` + `login.js` - username/password login
- `static/pin-login.html` + `pin-login.js` - PIN login
- `static/waiter.html` + `waiter.js` - waiter ordering workflow
- `static/counter.html` + `counter.js` - cashier/admin operations
- `static/table-dashboard.html` + `table-dashboard.js` - table-level live board
- `static/auth.js` - token storage and role guards
- `static/toast.js` - shared toast notifications
- `static/i18n.js` - bilingual translation dictionary + runtime language switching

---

## 3) Runtime Data Flow

1. User logs in and receives JWT.
2. Frontend stores token and sends `Authorization: Bearer <token>` on API calls.
3. Waiter creates active context (table or takeaway), then adds items to cart.
4. Waiter submits to `POST /api/orders/submit`.
5. Backend writes order/items, updates table status (for dine-in), emits WebSocket events.
6. Counter/dashboard/waiter refresh views based on WebSocket events.
7. Counter checks out via `POST/PUT /api/orders/{order_id}/checkout`.
8. Checkout emits completion events (including takeaway sync event), UI updates in near real-time.

---

## 4) Waiter Flow (Current)

### Active context first

- Waiter must choose:
  - a table (dine-in), or
  - a new takeaway context
- Only then can menu items be added.
- Cart header displays current context title.

### Order details sidebar behavior

- Clicking occupied table / existing takeaway opens details sidebar.
- Item statuses can be toggled served/pending there.
- Individual order items can also be cancelled from order details.
- Cancelled items are excluded from order totals after backend recalculation.
- "Add More Items" action is available for dine-in context.
- For takeaway details, add-more action is intentionally hidden.

### Context reset

- "Cancel / Clear Context" clears active context and cart.
- Successful submit also clears context + cart.

---

## 5) Realtime and Sync Strategy

- WebSocket endpoint: `/ws`
- Common events include:
  - `new_order_batch`
  - `order_updated`
  - `table_status_changed`
  - `table_grid_updated`
  - `order_completed`
  - `takeaways_updated`

### Takeaway sync

- On checkout of takeaway orders, backend broadcasts update events.
- Waiter takeaway view listens and reloads takeaway list.
- Fallback polling runs every 5 seconds **only when takeaway view is active**.

---

## 6) API Quick Map

### Auth

- `POST /api/auth/login`
- `POST /api/auth/login-pin`
- `GET /api/auth/me`

### Menu

- `GET /api/categories/`
- `POST /api/categories/` (admin)
- `GET /api/menu-items/`
- `POST /api/menu-items/` (admin)
- `PUT /api/menu-items/{item_id}` (admin)
- `PUT /api/menu-items/{item_id}/toggle-availability` (admin)
- `DELETE /api/menu-items/{item_id}` (admin, safe delete rule)
- `POST /api/menu-items/upload` (admin)

### Tables/Zones

- `GET /api/zones`
- `POST /api/zones` (admin)
- `PUT /api/zones/{zone_id}` (admin)
- `DELETE /api/zones/{zone_id}` (admin)
- `GET /api/tables`
- `POST /api/tables` (admin)
- `PUT /api/tables/{table_id}` (admin)
- `DELETE /api/tables/{table_id}` (admin)
- `GET /api/tables/status`
- `GET /api/tables/grid`

### Orders

- `GET /api/orders/`
- `POST /api/orders/`
- `POST /api/orders/submit`
- `GET /api/orders/active-takeaways`
- `GET /api/orders/tables`
- `GET /api/orders/active-by-table/{table_id}`
- `GET /api/orders/{order_id}/details`
- `PUT /api/orders/{order_id}/status`
- `PUT /api/orders/{order_id}/items/{item_id}/status`
- `POST /api/orders/{order_id}/checkout`
- `PUT /api/orders/{order_id}/checkout`

### Admin Users / Reports

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`
- `GET /api/reports/summary/today`
- `GET /api/reports/top-items`
- `GET /api/reports/hourly-trend`
- `GET /api/reports/daily-sales`
- `GET /api/reports/monthly-sales`
- `GET /api/reports/category-sales`
- `GET /api/reports/cancellations`

### Reports Endpoint Shape (Quick Reference)

- `GET /api/reports/top-items` -> `[ { item_name, quantity_sold } ]`
- `GET /api/reports/hourly-trend` -> `[ { hour, total } ]`
- `GET /api/reports/daily-sales?start_date=&end_date=` -> `[ { date, total } ]`
- `GET /api/reports/monthly-sales?year=` -> `[ { month, total } ]`
- `GET /api/reports/category-sales` -> `[ { category_name, total_sales } ]`
- `GET /api/reports/cancellations` -> `{ total_cancelled_items, total_lost_revenue, top_cancelled_items[] }`

---

## 7) Roles and Page Access

- **admin**: full access
- **waiter**: waiter + dashboard operations
- **cashier**: counter checkout flows
- **kitchen**: kitchen-related status workflows (via API/role rules)

Main pages:

- `/login`
- `/pin-login`
- `/waiter`
- `/counter`
- `/table-dashboard`

---

## 8) Setup

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Create `.env`:
   - `DATABASE_URL=sqlite:///./pos.db`
   - `JWT_SECRET_KEY=<your-secret>`
3. Run:
   - `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
4. Open:
   - `http://localhost:8000/login`
   - `http://localhost:8000/pin-login`

Default admin:

- Username: `admin`
- Password: `admin123`
- PIN: `1234`

---

## 9) Notes for Contributors and AI Agents

- Start reading in this order:
  1. `main.py`
  2. `models.py` + `schemas.py`
  3. `routers/orders.py`
  4. `static/waiter.js`
  5. `static/counter.js`
- Prefer modifying shared helpers first (e.g., `toast.js`, `auth.js`) before duplicating logic.
- Keep UI dialogs consistent via `window.CustomDialog`; do not reintroduce native browser dialogs.
- Keep the cart-first waiter workflow and takeaway-as-virtual-zone behavior intact.
- For UI text changes, update `static/i18n.js` keys and `data-i18n` mappings together.
- Keep WebSocket event names and payloads backward compatible when possible.
- If changing order lifecycle, verify:
  - waiter submit
  - takeaway list sync
  - counter checkout
  - table status updates

---

## 10) Additional Docs

- `DATABASE_DESIGN_VISUAL.md`
- `FULL_DOCUMENTATION_EN.md`
- `FULL_DOCUMENTATION_MM.md`

