# Restaurant POS — Full Documentation (English)

## 1. Overview
This project is a full-stack Restaurant POS (Point of Sale) system with:
1. **Menu management** (Categories + Menu Items)
2. **Waiter order taking** with a cart and table number
3. **Kitchen Display System (KDS)** for batch/ticket-based cooking
4. **Counter / Billing** with checkout and a thermal receipt print
5. **Security**: JWT authentication + role-based access control (RBAC)
6. **Staff attribution**: every order batch (ticket) is linked to the staff member who created it
7. **Admin User Management**: CRUD for staff PIN users

The system is designed for local-network use and real-time updates using WebSockets.

## 2. Tech Stack
Backend:
- FastAPI
- SQLAlchemy (ORM)
- SQLite (development) / PostgreSQL (production via `DATABASE_URL`)
- WebSockets (FastAPI)

Frontend:
- Vanilla HTML + JavaScript (Fetch API, WebSocket API)
- Tailwind CSS via CDN
- Lightweight toast UI (`static/toast.js`)

## 3. Deployment & Setup

### 3.1 Prerequisites
- Python 3.10+ recommended
- A virtual environment (recommended)
- A browser (PC/tablet/mobile) for the POS pages

### 3.2 Install and run
From the project root:
```bash
cd /Users/ttw/Documents/My_Project/RestaurantPOS
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open:
- Local PC: `http://localhost:8000`
- Other devices on the same network: `http://<HOST_IP>:8000`

### 3.3 Environment variables
Create `.env` (optional if you already have one) using `.env.example` as a reference:
- `DATABASE_URL` (SQLite default: `sqlite:///./pos.db`)
- `JWT_SECRET_KEY` (must be long and random for production; see Security section)

## 4. Database Schema (Core Tables)

### 4.1 `users`
Holds all authenticated accounts:
- `id` (PK)
- `username` (unique, required)
- `password_hash` (required; used for admin username/password login)
- `role` (required, one of: `admin`, `waiter`, `kitchen`, `cashier`)
- `pin_code` (unique, nullable; exactly 4 digits for staff PIN login)

### 4.2 `categories`
- `id` (PK)
- `name`

### 4.3 `menu_items`
- `id` (PK)
- `name`
- `price`
- `description` (nullable)
- `image_url` (nullable; served from `static/images/`)
- `category_id` (FK to `categories.id`)

### 4.4 `orders`
Represents a dining session per table (one active/open session per table enforced by a partial unique index in `main.py`):
- `id` (PK)
- `table_number`
- `status` (e.g. `pending`, `open`, `dining`, `completed`, `paid`)
- `total_amount`
- `created_at`
- cashier payment fields:
  - `payment_method`
  - `amount_tendered`
  - `change_amount`

### 4.5 `order_items`
Represents line items and also the concept of **batches/tickets**:
- `id` (PK)
- `order_id` (FK to `orders.id`)
- `menu_item_id` (FK to `menu_items.id`)
- `quantity`
- `subtotal`
- **batch tracking**:
  - `batch_number` (integer, ticket number within the table’s dining session)
  - `batch_status` (e.g. `pending`, `completed`)
- **staff attribution**:
  - `created_by_id` (FK to `users.id`)

Important:
- Kitchen works by expanding an order into multiple tickets using `batch_number`.
- Kitchen only shows items where `batch_status == 'pending'`.

## 5. Authentication & RBAC

### 5.1 JWT Authentication
Login endpoints:
1. **Admin login (username/password)**  
   `POST /api/auth/login`  
   Request: `{ "username": "...", "password": "..." }`  
2. **Staff login (4-digit PIN)**  
   `POST /api/auth/login-pin`  
   Request: `{ "pin_code": "1234" }`

On success, the API returns:
- `access_token`
- `token_type = "bearer"`
- `user` object (id, username, role)

Frontend must send JWT on protected calls:
- `Authorization: Bearer <access_token>`

### 5.2 RBAC (Roles)
Roles are restricted to:
- `admin`
- `waiter`
- `kitchen`
- `cashier`

RBAC behavior (current implementation):
- **Menu read** requires authentication.
- **Menu writes** (create category/menu item/upload) are **admin-only**.
- **Order endpoints** require authentication.
- **Checkout/payment** requires authentication (cashier UI is role-guarded on the frontend; backend also requires JWT).
- **User management CRUD** is admin-only via `/api/admin/users`.

### 5.3 Frontend route entry points
Pages:
- `/login` : Admin username/password login
- `/pin-login` : Staff PIN login (4-digit numpad)
- `/waiter` : Waiter UI
- `/kitchen` : KDS UI
- `/counter` : Counter/Cashier + Admin panels

Redirect behavior after PIN login:
- `waiter` -> `/waiter`
- `kitchen` -> `/kitchen`
- `cashier` -> `/counter`
- `admin` -> `/counter`

## 6. Admin Credentials & Staff PINs

### 6.1 Default admin (first run)
If no admin exists, the backend will create:
- Username: `admin`
- Password: `admin123`
- PIN: `1234` (also works in `/pin-login`)

### 6.2 Create staff PIN users
You can add staff users in either of two ways:
1. **Run the helper script** (quick setup)
   ```bash
   python scripts/add_staff_users.py
   ```
   Example PINs created by default:
   - waiter1: `1111`
   - waiter2: `2222`
   - kitchen1: `3333`
   - cashier1: `4444`
2. **Use the Admin User Management UI** (recommended after boot)
   Open `/counter` as admin and go to **User Management** tab.

## 7. WebSockets (Real-Time Events)
WebSocket endpoint:
- `/ws`

Broadcast events used by the frontend:
- `menu_item_added`: triggers UI menu updates
- `new_order_batch`: triggers KDS board refresh for new tickets/batches
- `batch_completed`: triggers removal of only the specific completed ticket
- Other legacy events may exist depending on which API endpoint the frontend uses.

## 8. API Reference

### 8.1 Health
- `GET /api/health`

### 8.2 Auth
- `POST /api/auth/login`
- `POST /api/auth/login-pin`
- `GET /api/auth/me`

### 8.3 Menu
- `GET /api/categories/`
- `POST /api/categories/` (admin-only)
- `GET /api/menu-items/` (optional `category_id`)
- `POST /api/menu-items/` (admin-only; JSON body)
- `POST /api/menu-items/upload` (admin-only; multipart form with image)

### 8.4 Image upload
- `POST /api/upload` (admin-only; general endpoint used by Counter menu management)

### 8.5 Orders

Core batching endpoints (used by Waiter -> Kitchen -> Counter):
1. `POST /api/orders/submit`
   - Request: `{ "table_id": number, "items": [ { "menu_item_id": number, "quantity": number } ] }`
   - Behavior:
     - Find existing open/dining dining session for the table
     - If none: create a new order and batch 1
     - If exists: create a new ticket batch number = max + 1
     - Assign `created_by_id` from decoded JWT user (backend does not trust the frontend user id)
     - Broadcast `new_order_batch` for KDS

2. `GET /api/orders/`
   - Supports filtering by `status` (used by KDS refresh)
   - Returns `OrderResponseDetail` including items expanded with `waiter_name` per ticket line

3. `PUT /api/orders/{order_id}/batches/{batch_number}/status`
   - Body: `{ "status": "completed" }`
   - Updates only that ticket batch
   - Broadcasts `batch_completed`

Cashier endpoints:
- `GET /api/orders/tables`
  - Returns canonical one-order-per-table view for cashier list
- `GET /api/orders/active-by-table/{table_id}`
  - Returns full consolidated order for that table
- `PUT /api/orders/{order_id}/checkout`
  - Body includes payment:
    - `{ "payment_method": "cash|mobile_money|...", "amount_tendered": number }`
  - Sets `order.status = "paid"`
  - Returns full receipt payload including `served_by_name`

### 8.6 Admin User Management
All admin-only under:
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`

## 9. Frontend Pages and UX

### 9.1 `/pin-login` (Staff 4-digit PIN numpad)
UX:
- Displays 4 dots
- Numpad 0-9 + Clear + Backspace
- Auto-submits on 4th digit
- Shows “Wrong PIN”, clears PIN, and shakes dots (CSS animation)

### 9.2 `/waiter`
UX:
- Sticky category tabs
- Menu items grid filtered by selected category
- Cart with +/- quantity controls
- Table number input
- “Submit Order” calls `POST /api/orders/submit`
- Uses WebSocket `menu_item_added` and triggers UI refresh

### 9.3 `/kitchen` (KDS)
UX:
- Kanban-style tickets grid
- Tickets are expanded by `batch_number`
- Each ticket shows:
  - Table number
  - Ticket # (`batch_number`)
  - **Waiter name** (“Waiter: John”)
  - Items for that batch only
- “Mark as Done” calls:
  - `PUT /api/orders/{order_id}/batches/{batch_number}/status`
- WebSocket `batch_completed` removes only that ticket.

### 9.4 `/counter` (Cashier + Admin)
UX:
- Tabbed interface:
  - Cashier / Billing (default)
  - Menu Management (admin)
  - User Management (admin)
- Cashier:
  - Loads active tables via `GET /api/orders/tables`
  - Selects a table and loads consolidated order via `GET /api/orders/active-by-table/{table_id}`
  - Shows receipt UI and live change calculation
  - “Confirm Payment” calls `PUT /api/orders/{order_id}/checkout`
  - Prints receipt using browser print CSS
- Receipt shows:
  - Table number
  - Items
  - Grand total
  - Payment details
  - **Served by: waiter name**

## 10. Order Flow (End-to-End)

### 10.1 Waiter creates an order batch
1. Waiter logs in with PIN -> gets JWT.
2. Waiter selects items and enters table number.
3. Waiter calls `POST /api/orders/submit` with table and items.
4. Backend:
   - Finds/creates the dining session order for the table
   - Creates a new batch/ticket (`batch_number`)
   - Assigns staff attribution using decoded JWT `current_user.id`
   - Creates `OrderItem` rows with `created_by_id`
   - Broadcasts `new_order_batch` for KDS.

### 10.2 Kitchen cooks batches
1. KDS fetches pending orders (and expands by `batch_number`).
2. KDS only shows items with `batch_status == pending`.
3. When chef marks done:
   - Only that ticket’s `batch_status` becomes `completed`
   - KDS removes that ticket after `batch_completed`.

### 10.3 Cashier bills
1. Cashier selects table from active list.
2. Cashier uses consolidated order payload for receipt.
3. Checkout stores payment fields on the order and sets `paid`.
4. Receipt displays served-by (computed from the latest batch’s creator).

## 11. Operational Notes & Troubleshooting

### 11.1 “Wrong PIN”
Cause:
- Staff user record does not exist in `users` table with that PIN.
Fix:
- Create staff users via `scripts/add_staff_users.py` or the User Management tab.

### 11.2 401 Unauthorized
Cause:
- You are calling protected APIs without a JWT.
Fix:
- Log in first, then reload the correct page.

### 11.3 “Served by” or “Waiter: —” is empty
Cause:
- Old orders created before the staff attribution migration will have `created_by_id = NULL`.
Fix:
- Create a new batch from the waiter (new batches will have attribution).

### 11.4 Users table missing
Cause:
- Database was created before the `User` model existed.
Fix:
- Run `python scripts/add_staff_users.py` (it creates missing tables before inserting staff).

## 12. Security Recommendations (Important)
1. Set `JWT_SECRET_KEY` to a long random value (min 32 bytes recommended).
2. Use HTTPS in production (for real deployments).
3. Do not expose the server publicly without firewall rules.
4. Use RBAC and keep admin endpoints restricted (already implemented).
5. Rotate admin/staff PINs if a device is compromised.

