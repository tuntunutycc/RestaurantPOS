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

## 8) Setup & Deployment

### First-time install (local)

1. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment** — copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Minimum variables:
   - `DATABASE_URL=sqlite:///./pos.db` (default SQLite file in project root)
   - `JWT_SECRET_KEY=<random-32+-char-secret>` (required in production)

3. **Start the server**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   On first startup, SQLAlchemy creates tables automatically (`main.py` lifespan).

4. **Bootstrap the first root user** (required before anyone can log in)

   **Production / recommended — CLI:**
   ```bash
   PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'
   ```
   Idempotent: if a root already exists, the script exits without changes.

   **Local dev only — Setup UI:**
   - Open `http://localhost:8000/login`
   - When no root exists, you are redirected to `/setup`
   - Create the first root account there  
   - **Do not expose `/setup` on a public production URL** while `needs_setup` is true (unauthenticated).

5. **Log in and configure the restaurant**
   - Root → `/counter` → create admin/staff, menu, tables, printers
   - Staff PIN login → `/pin-login`
   - Password roles (root, admin) → `/login`
   - PIN roles (cashier, waiter, account) → `/pin-login`

### Fresh database reset (start from zero)

Use this when you want to wipe all users, menu, orders, and sales history.

1. **Stop the running server** (Ctrl+C in the terminal running `uvicorn`).

2. **Delete the SQLite database file**
   ```bash
   rm -f pos.db
   ```
   If you use a custom path, delete the file matching `DATABASE_URL` in `.env`.

3. **Recreate tables and seed root**
   ```bash
   PYTHONPATH=. python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
   PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'
   ```

4. **Restart the server**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Clear browser session** (recommended) — remove `pos_token` and `pos_user` from Local Storage, or log out, so old JWTs are not reused.

**What is wiped:** all users, menu, zones/tables, orders, reports history, audit logs, and sessions. You must seed root again and reconfigure the restaurant.

### Native Windows Deployment (Required for USB Receipt Printing)

Cashier USB / installed-queue receipt printing uses **`pywin32`** and the **Windows Print Spooler**. On the cashier PC, run the app **natively on Windows 11** — not inside Docker.

> **Important — do not use Docker on the cashier machine.**  
> `Dockerfile` / `docker-compose.yml` exist for Linux-style deploys, but a Linux container **cannot** access the Windows USB/Bluetooth print spooler. Use Docker only where USB receipts are not required (or use LAN `escpos_network` printers instead).

1. **Prerequisites**
   - [Git for Windows](https://git-scm.com/download/win)
   - [Python 3.11+](https://www.python.org/downloads/) (check **Add python.exe to PATH** during install)
   - Windows printer online in **Settings → Bluetooth & devices → Printers & scanners** (e.g. `POSPrinter POS-80(300DPI)`)

2. **Clone the repository**
   ```bat
   git clone https://github.com/tuntunutycc/RestaurantPOS.git
   cd RestaurantPOS
   ```

3. **Create and activate a virtual environment**
   ```bat
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Install dependencies (includes `pywin32`)**
   ```bat
   pip install -r requirements-windows.txt
   ```
   `requirements-windows.txt` installs `requirements.txt` plus `pywin32`.

5. **Configure environment**
   ```bat
   copy .env.example .env
   ```
   Edit `.env` and set at least a strong `JWT_SECRET_KEY` (32+ characters).

6. **Seed the first root user** (first install only)
   ```bat
   set PYTHONPATH=.
   python scripts\seed_root.py --username root --password "YourSecurePass123"
   ```

7. **Run the server**
   ```bat
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000/login`.

8. **Enable Windows receipt printing in Admin**
   - Counter → Kitchen Printer Settings → Print mode = **Windows printer (USB / installed queue)**
   - Set **Render mode = Image mode** for correct Myanmar text
   - Printers → edit the **cashier** printer → select the Windows queue (e.g. `POSPrinter POS-80(300DPI)`) → Save
   - Checkout with **Print Receipt** enabled

9. **Printer diagnostic log file**
   - After any print job, open:
     `logs\printing\print.log`
   - That file records backend, render mode, Windows queue / LAN target, Myanmar font path loaded (or missing), shaping backend (`raqm` / `harfbuzz`), and success/failure details.
   - The font line appears only when printing in **image** mode. Text mode will log that Myanmar may look wrong.
   - If Myanmar vowels like `ေ` sit in the wrong place, confirm the log shows `shaping=raqm` or `shaping=harfbuzz` (not `basic`), then reinstall deps: `pip install -r requirements.txt`.

Kitchen/bar thermal printers can still use LAN IP (`host`/`port` on those printer rows) while cashier uses Windows USB.

### Production notes

| Topic | Guidance |
|-------|----------|
| **Database** | SQLite is fine for single-instance dev. For production, set `DATABASE_URL` to PostgreSQL when ready (see `specs/roadmap.md`). |
| **Secrets** | Set a strong `JWT_SECRET_KEY` in the host environment; never commit `.env`. |
| **Root bootstrap** | Use `scripts/seed_root.py` on the server after deploy; avoid relying on `/setup` in production. |
| **Persistent disk** | On Cloud Run / containers, mount a volume for `pos.db` (or use PostgreSQL); otherwise data is lost on redeploy. |
| **HTTPS** | Terminate TLS at your reverse proxy or platform; app serves same-origin static + API. |
| **Windows USB receipts** | See **Native Windows Deployment** above. Do not run the cashier machine in Docker Linux. |

### Default dev credentials (after reset)

Only applies if you used the seed command above during a local reset:

| Role | Login | Credentials |
|------|-------|---------------|
| root | `/login` (password) | `root` / `ChangeMe123` |

Change the root password immediately after first login. Create admin, cashier, and waiter staff from Counter → Staff Management.

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

