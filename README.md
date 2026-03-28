# Restaurant POS System

A full-stack Restaurant POS built with **FastAPI + SQLAlchemy** (backend) and **Vanilla HTML/JS + Tailwind** (frontend).

FastAPI + SQLAlchemy (backend) နှင့် Vanilla HTML/JS + Tailwind (frontend) ဖြင့် တည်ဆောက်ထားသော စားသောက်ဆိုင် POS စနစ် ဖြစ်သည်။

---

## 1) Architecture | ဗိသုကာ

### English

- **Backend**
  - `main.py`: app startup/lifespan migrations, page routes, static mount, upload API, WebSocket endpoint.
  - `auth.py`: JWT create/verify, password hash/verify, role guard helpers.
  - `database.py`: `DATABASE_URL` loading, SQLAlchemy engine/session/base.
  - `models.py`: ORM models (`User`, `Category`, `MenuItem`, `Zone`, `Table`, `Order`, `OrderItem`).
  - `routers/`: modular APIs (`auth`, `menu`, `orders`, `users`, `tables`).
- **Frontend**
  - `static/login.html` + `login.js`: admin username/password login.
  - `static/pin-login.html` + `pin-login.js`: staff 4-digit PIN login.
  - `static/waiter.*`, `static/kitchen.*`, `static/counter.*`, `static/table-dashboard.*`.
  - `static/auth.js`: token/user storage, role guards, auth headers.
- **Realtime**
  - `/ws` WebSocket broadcasts for menu/order/table updates.
- **Database**
  - Dev: SQLite (`pos.db`)
  - Prod-ready: PostgreSQL by changing `DATABASE_URL` in `.env`.

### မြန်မာ

- **Backend**
  - `main.py`: app စတင်ချိန် migration များ၊ page routes၊ static mount၊ upload API၊ WebSocket endpoint။
  - `auth.py`: JWT ဖန်တီး/စစ်ဆေး၊ password hash/verify၊ role guard helper များ။
  - `database.py`: `DATABASE_URL` ဖတ်ခြင်းနှင့် SQLAlchemy engine/session/base တည်ဆောက်ခြင်း။
  - `models.py`: ORM models (`User`, `Category`, `MenuItem`, `Zone`, `Table`, `Order`, `OrderItem`)။
  - `routers/`: `auth`, `menu`, `orders`, `users`, `tables` အလိုက် API ခွဲထားသည်။
- **Frontend**
  - `static/login.html` + `login.js`: admin username/password login။
  - `static/pin-login.html` + `pin-login.js`: staff PIN ၄ လုံး login။
  - `static/waiter.*`, `static/kitchen.*`, `static/counter.*`, `static/table-dashboard.*`
  - `static/auth.js`: token/user သိမ်းခြင်း၊ role guard၊ auth headers။
- **Realtime**
  - `/ws` WebSocket ဖြင့် menu/order/table update တိုက်ရိုက်ပို့သည်။
- **Database**
  - Dev: SQLite (`pos.db`)
  - Prod: `.env` ထဲက `DATABASE_URL` ကို PostgreSQL URL ပြောင်းပြီးသုံးနိုင်သည်။

---

## 2) Authentication & Roles | လော့ဂ်အင်းနှင့် Role များ

### English

- Roles: `admin`, `waiter`, `kitchen`, `cashier`
- Admin login URL: `http://localhost:8000/login`
- Staff PIN login URL: `http://localhost:8000/pin-login`
- Default admin credentials:
  - Username: `admin`
  - Password: `admin123`
  - PIN: `1234`
- JWT token is stored in `localStorage` and sent as `Authorization: Bearer <token>`.
- Route protection is enforced both on backend and frontend guards.

### မြန်မာ

- Role များ: `admin`, `waiter`, `kitchen`, `cashier`
- Admin login URL: `http://localhost:8000/login`
- Staff PIN login URL: `http://localhost:8000/pin-login`
- Default admin account:
  - Username: `admin`
  - Password: `admin123`
  - PIN: `1234`
- JWT ကို `localStorage` ထဲသိမ်းပြီး API ခေါ်ရာတွင် `Authorization: Bearer <token>` ဖြင့်ပို့သည်။
- Backend + Frontend နှစ်ဖက်လုံးတွင် route guard ကာကွယ်ထားသည်။

---

## 3) Main Features | အဓိက လုပ်ဆောင်ချက်များ

### English

- Category/Menu management (admin)
- Menu image upload (local storage)
- Menu availability toggle (`is_available`) with Sold Out handling
- Safe menu delete (admin only, blocked if order history exists)
- Zone/Table management (admin)
- Waiter order submit with table selection and add-on batches
- Kitchen ticket view and item-level status updates
- Counter checkout and receipt flow
- Realtime updates via WebSocket

### မြန်မာ

- Category/Menu စီမံခန့်ခွဲမှု (admin)
- Menu image local upload
- `is_available` ဖြင့် Sold Out toggle
- Menu delete ကို safe rule ဖြင့်ကာကွယ်ထားသည် (order history ရှိပါက မဖျက်နိုင်)
- Zone/Table စီမံခန့်ခွဲမှု (admin)
- Waiter မှ table ရွေးပြီး order submit/add-on batches
- Kitchen ticket view နှင့် item-level status update
- Counter checkout နှင့် receipt flow
- WebSocket ဖြင့် realtime update

---

## 4) Menu Availability & Delete Rules | Sold Out နှင့် Delete စည်းကမ်း

### English

- `PUT /api/menu-items/{item_id}/toggle-availability`
  - Flips `is_available` true/false.
  - Waiter UI disables sold-out items (`opacity/grayscale`, badge, add button disabled).
- `DELETE /api/menu-items/{item_id}`
  - Admin only.
  - If item was used in any `order_items`, API returns:
    - `Cannot delete item with order history. Disable it instead.`
  - If never used, hard delete is allowed.

### မြန်မာ

- `PUT /api/menu-items/{item_id}/toggle-availability`
  - `is_available` ကို true/false ပြောင်းသည်။
  - Waiter UI တွင် sold-out ဖြစ်လျှင် card ကို မှိန်/gray ပြပြီး badge ပြထားပြီး add button ပိတ်ထားသည်။
- `DELETE /api/menu-items/{item_id}`
  - Admin သာခွင့်ပြုသည်။
  - Item ကို အရင် order တွင်သုံးဖူးပါက:
    - `Cannot delete item with order history. Disable it instead.`
  - မသုံးဖူးသေးပါက delete လုပ်နိုင်သည်။

---

## 5) Key URLs | အဓိက URL များ

- `GET /api/health`
- Pages:
  - `/login`
  - `/pin-login`
  - `/waiter`
  - `/kitchen`
  - `/counter`
  - `/table-dashboard`
- Realtime:
  - `/ws`

---

## 6) API Summary | API အနှစ်ချုပ်

### Auth
- `POST /api/auth/login`
- `POST /api/auth/login-pin`
- `GET /api/auth/me`

### Menu & Category
- `GET /api/categories/`
- `POST /api/categories/` (admin)
- `GET /api/menu-items/`
- `POST /api/menu-items/` (admin)
- `POST /api/menu-items/upload` (admin)
- `PUT /api/menu-items/{item_id}/toggle-availability` (admin)
- `DELETE /api/menu-items/{item_id}` (admin, safe-delete rule)

### Users (Admin)
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`

### Tables & Zones
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
- `GET /api/orders/tables`
- `GET /api/orders/active-by-table/{table_id}`
- `GET /api/orders/{order_id}/details`
- `PUT /api/orders/{order_id}/status`
- `PUT /api/orders/{order_id}/batches/{batch_number}/status`
- `PUT /api/orders/{order_id}/items/{item_id}/status`
- `PUT /api/orders/{order_id}/checkout`

---

## 7) Setup & Run | Setup နှင့် Run

### English

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure `.env`:
   - `DATABASE_URL=sqlite:///./pos.db`
   - `JWT_SECRET_KEY=<your-secret>`
3. Run server:
   - `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
4. Open:
   - `http://localhost:8000/login` (admin)
   - `http://localhost:8000/pin-login` (staff)

### မြန်မာ

1. Dependency တင်ပါ:
   - `pip install -r requirements.txt`
2. `.env` သတ်မှတ်ပါ:
   - `DATABASE_URL=sqlite:///./pos.db`
   - `JWT_SECRET_KEY=<your-secret>`
3. Server run:
   - `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
4. Browser ဖွင့်:
   - `http://localhost:8000/login` (admin)
   - `http://localhost:8000/pin-login` (staff)

---

## 8) Troubleshooting | ပြဿနာဖြေရှင်းခြင်း

### English

- **405 on new endpoint**: restart server (old code still running).
- **Image 404**: DB has URL but file is missing in `static/images` or `static/images/menu`.
- **Unauthorized/403**: check role and token expiration.
- **PIN fails**: ensure exact 4 digits and existing user record.

### မြန်မာ

- **Endpoint အသစ်တွင် 405**: server restart လုပ်ပါ (code ဟောင်း run နေသေးနိုင်သည်)။
- **Image 404**: DB URL ရှိပေမယ့် file မရှိနိုင် (`static/images` / `static/images/menu`)။
- **Unauthorized/403**: role နှင့် token expiry စစ်ပါ။
- **PIN မဝင်**: ၄ လုံးတိတိဖြစ်ရမည်၊ user record ရှိရမည်။

---

## 9) Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | `sqlite:///./pos.db` (dev) or PostgreSQL URL (prod) |
| `JWT_SECRET_KEY` | JWT signing secret (set a strong value in production) |

---

## License

Use and modify for your project.
# Restaurant POS System

A full-stack Point of Sale (POS) system for restaurants: menu management, order taking, kitchen display, and counter/billing. Built with **FastAPI** (backend) and vanilla **HTML/JavaScript** (frontend).

ဤစနစ်သည် စားသောက်ဆိုင်များအတွက် မီနူးစီမံခန့်ခွဲမှု၊ အမှာစာယူခြင်း၊ ချက်ပြုတ်ခန်းပြသခြင်းနှင့် ငွေကောက်ခံ/အကြီးတန်းစီမံခန့်ခွဲမှုပါဝင်သော **FastAPI** (နောက်ခံ) နှင့် **HTML/JavaScript** (ရှေ့မျက်နှာစာ) ဖြင့်တည်ဆောက်ထားသော POS စနစ်ဖြစ်သည်။

---

## Architecture | ဗိသုကာ

### English

The system has three layers:

1. **Backend (FastAPI + SQLAlchemy)**  
   - **main.py**: FastAPI app, lifespan (creates DB tables on startup), static file mount, and routes that serve each UI page (`/`, `/waiter`, `/kitchen`, `/counter`).  
   - **database.py**: Loads `DATABASE_URL` from `.env` (via `python-dotenv`), creates the SQLAlchemy engine (with `check_same_thread=False` for SQLite), `SessionLocal`, `Base`, and `get_db()` dependency for request-scoped sessions.  
   - **models.py**: SQLAlchemy ORM models — `Category`, `MenuItem`, `Order`, `OrderItem` — with relationships (Order → OrderItems → MenuItem; MenuItem → Category).  
   - **schemas.py**: Pydantic v2 models for request/response validation (e.g. `CategoryCreate`, `CategoryResponse`, `OrderCreate`, `OrderResponseDetail`).  
   - **routers/**:  
     - **menu.py**: Categories and menu items CRUD (POST/GET `/api/categories/`, POST/GET `/api/menu-items/`).  
     - **orders.py**: Create order (POST `/api/orders/`), list orders with optional status filter (GET `/api/orders/`), update status (PUT `/api/orders/{id}/status`), pay order (PUT `/api/orders/{id}/pay`).

2. **Database**  
   - Development: **SQLite** (`pos.db`). Production: set `DATABASE_URL` in `.env` to a **PostgreSQL** URL; no code change needed.

3. **Frontend (static)**  
   - All UIs live under **static/**: `index.html` (menu & categories test), `waiter.html` (take orders), `kitchen.html` (KDS, mark done), `counter.html` (counter/admin with Cashier and Menu Management tabs). Each page has a matching `.js` that uses the **Fetch API** to call the backend.

Data flow: **Browser** → HTTP (Fetch) → **FastAPI** → **SQLAlchemy** → **SQLite/PostgreSQL**; responses are JSON (API) or HTML (page routes).

---

### မြန်မာ

စနစ်တွင် အလွှာသုံးခုရှိသည်။

1. **နောက်ခံ (FastAPI + SQLAlchemy)**  
   - **main.py**: FastAPI အက်ပ်လီကေးရှင်း၊ စတင်တက်သည့်အခါ ဒေတာဘေ့စ်ဇယားများဖန်တီးခြင်း၊ static ဖိုင်များ တပ်ခြင်းနှင့် စာမျက်နှာတစ်ခုချင်းအတွက် route များ (`/`, `/waiter`, `/kitchen`, `/counter`)။  
   - **database.py**: `.env` မှ `DATABASE_URL` ကို ဖတ်ခြင်း (`python-dotenv`)，SQLAlchemy engine ဖန်တီးခြင်း (SQLite အတွက် `check_same_thread=False`)，`SessionLocal`၊ `Base` နှင့် request တစ်ခုချင်းအတွက် `get_db()` dependency။  
   - **models.py**: SQLAlchemy ORM မော်ဒယ်များ — `Category`, `MenuItem`, `Order`, `OrderItem` — ဆက်စပ်မှုများဖြင့် (Order → OrderItems → MenuItem; MenuItem → Category)။  
   - **schemas.py**: တောင်းခံ/ပြန်ကြားချက် စစ်ဆေးမှုအတွက် Pydantic v2 မော်ဒယ်များ (ဥပမာ `CategoryCreate`, `OrderCreate`, `OrderResponseDetail`)။  
   - **routers/**:  
     - **menu.py**: ကတ်တဂိုရီနှင့် မီနူးပစ္စည်းများ CRUD (POST/GET `/api/categories/`, POST/GET `/api/menu-items/`)။  
     - **orders.py**: အမှာစာဖန်တီးခြင်း (POST `/api/orders/`)，အမှာစာစာရင်းနှင့် status စစ်ထုတ်ခြင်း (GET `/api/orders/`)，status အပ်ဒိတ် (PUT `/api/orders/{id}/status`)，ငွေချေခြင်း (PUT `/api/orders/{id}/pay`)။

2. **ဒေတာဘေ့စ်**  
   - ဖွံ့ဖြိုးမှု: **SQLite** (`pos.db`)။ ထုတ်လုပ်မှု: `.env` တွင် `DATABASE_URL` ကို **PostgreSQL** URL သတ်မှတ်ပါ။ ကုဒ်ပြောင်းစရာမလို။

3. **ရှေ့မျက်နှာစာ (static)**  
   - UI အားလုံး **static/** အောက်တွင် — `index.html` (မီနူး/ကတ်တဂိုရီ စမ်းသပ်စာ)，`waiter.html` (အမှာစာယူခြင်း)，`kitchen.html` (ချက်ပြုတ်ခန်းပြသခြင်း၊ ပြီးပါက မှတ်ချက်)，`counter.html` (ငွေကောက်ခံ/မီနူးစီမံခန့်ခွဲမှု tab များ)။ စာမျက်နှာတိုင်းတွင် နောက်ခံ API ကို **Fetch API** ဖြင့်ခေါ်သော `.js` ပါရှိသည်။  

ဒေတာစီးဆင်းမှု: **ဘရောက်ဆာ** → HTTP (Fetch) → **FastAPI** → **SQLAlchemy** → **SQLite/PostgreSQL**။ ပြန်ကြားချက်များမှာ JSON (API) သို့မဟုတ် HTML (စာမျက်နှာ route များ) ဖြစ်သည်။

---

## Authentication & RBAC | အတည်ပြုခြင်းနှင့် ခွင့်ပြုချက်

### English

- **Login URLs** (replace `localhost` with your server IP if needed):
  - **Admin:** `http://localhost:8000/login` — username `admin`, password `admin123`.
  - **Staff (PIN):** `http://localhost:8000/pin-login` — 4-digit PIN (default admin PIN: `1234`; run `python scripts/add_staff_users.py` for waiter/kitchen/cashier PINs).
- **JWT**: After login, the API returns a JWT. The frontend stores it in `localStorage` and sends it in the `Authorization: Bearer <token>` header on every API request.
- **Roles**: `admin`, `waiter`, `kitchen`, `cashier`. Only **admin** can create/update/delete categories and menu items; all authenticated users can use order and table endpoints appropriate to their role.
- **Route guards**: `/` (menu management) is admin-only; `/waiter` for waiter/admin; `/kitchen` for kitchen/admin; `/counter` for cashier/admin. Unauthenticated users are redirected to `/login`. Wrong-role access redirects to the user’s default page with an “Unauthorized” message.
- **Backend**: `auth.py` provides JWT creation/validation and `require_roles(["admin"])`. `routers/auth.py` exposes `POST /api/auth/login` and `GET /api/auth/me`. Set `JWT_SECRET_KEY` in `.env` for production.

### မြန်မာ

- **လော့ဂ်အင်း URL များ** (လိုအပ်ပါက `localhost` ကို ဆာဗာက IP နှင့်အစားထိုးပါ):
  - **အကြီးတန်း:** `http://localhost:8000/login` — username `admin`, password `admin123`။
  - **ဝန်ထမ်း (PIN):** `http://localhost:8000/pin-login` — PIN ၄ လုံး (ပုံသက်ရိုက် admin PIN: `1234`; waiter/kitchen/cashier PIN များအတွက် `python scripts/add_staff_users.py` ကို လည်ပတ်ပါ)။
- **JWT**: လော့ဂ်အင်းပြီးပါက API က JWT ပြန်ပေးသည်။ ရှေ့မျက်နှာစာက `localStorage` တွင် သိမ်းပြီး API တောင်းခံတိုင်းတွင် `Authorization: Bearer <token>` ဟက်ဒါဖြင့် ပို့သည်။
- **အခန်းကဏ္ဍများ**: `admin`, `waiter`, `kitchen`, `cashier`။ **admin** သာ ကတ်တဂိုရီနှင့် မီနူးပစ္စည်းများ ဖန်တီး/ပြင်ဆင်/ဖျက်နိုင်သည်။ အတည်ပြုထားသော အသုံးပြုသူအားလုံး မိမိအခန်းကဏ္ဍနှင့် ကိုက်ညီသော အမှာစာ/စားပွဲ API များကို သုံးနိုင်သည်။
- **Route ကာကွယ်မှု**: `/` (မီနူးစီမံခန့်ခွဲမှု) သည် admin သက်သက်။ `/waiter` — waiter/admin၊ `/kitchen` — kitchen/admin၊ `/counter` — cashier/admin။ အတည်မပြုထားသူများကို `/login` သို့ ပြန်ညွှန်းသည်။ အခန်းကဏ္ဍမကိုက်ပါက သက်ဆိုင်ရာ စာမျက်နှာသို့ ပြန်ညွှန်းပြီး “Unauthorized” ပြသသည်။

---

## Project structure | ပရောဂျက်ဖွဲ့စည်းပုံ

```
RestaurantPOS/
├── main.py              # FastAPI app, routes for /login, /waiter, /kitchen, /counter
├── database.py           # DB engine, SessionLocal, get_db
├── auth.py               # JWT auth, get_current_user, require_roles, password hashing
├── models.py             # Category, MenuItem, Order, OrderItem, User
├── schemas.py            # Pydantic request/response (incl. LoginRequest, TokenResponse)
├── requirements.txt      # fastapi, uvicorn, sqlalchemy, python-dotenv, pyjwt, passlib[bcrypt]
├── .env                  # DATABASE_URL, JWT_SECRET_KEY (see .env.example)
├── .env.example          # Example env vars for collaborators
├── routers/
│   ├── __init__.py
│   ├── auth.py           # POST /api/auth/login, GET /api/auth/me
│   ├── menu.py           # /api/categories/, /api/menu-items/ (admin for writes)
│   └── orders.py         # /api/orders/ (all authenticated)
└── static/
    ├── login.html        # Login screen (default entry)
    ├── login.js
    ├── auth.js           # Token storage, route guards, nav bar, getAuthHeaders
    ├── index.html        # Menu & categories (admin only)
    ├── app.js
    ├── waiter.html       # Take orders (waiter/admin)
    ├── waiter.js
    ├── kitchen.html      # Kitchen display (kitchen/admin)
    ├── kitchen.js
    ├── counter.html      # Counter/Admin (cashier/admin)
    └── counter.js
```

---

## API endpoints | API လိပ်စာများ

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/categories/` | List categories |
| POST | `/api/categories/` | Create category |
| GET | `/api/menu-items/` | List menu items (optional `?category_id=`) |
| POST | `/api/menu-items/` | Create menu item |
| GET | `/api/orders/` | List orders (optional `?status=pending`) |
| POST | `/api/orders/` | Create order (table_number, items) |
| PUT | `/api/orders/{id}/status` | Update order status (body: `{"status": "completed"}`) |
| PUT | `/api/orders/{id}/pay` | Mark order as paid |

---

## Usage | အသုံးပြုနည်း

### English

1. **Setup**  
   - Copy `.env.example` to `.env` if needed; set `DATABASE_URL=sqlite:///./pos.db` for development.  
   - Install: `pip install -r requirements.txt`  
   - Run: `uvicorn main:app --reload` (or `uvicorn main:app --host 0.0.0.0 --port 8000` for network access).  
   - Open in browser: `http://localhost:8000` (or `http://<your-IP>:8000` from other devices).

2. **Login URLs & credentials**  
   - **Admin (username + password):**  
     - URL: `http://localhost:8000/login`  
     - Username: `admin`  
     - Password: `admin123`  
   - **Staff (4-digit PIN):**  
     - URL: `http://localhost:8000/pin-login`  
     - Default admin PIN: `1234`  
   - **Staff users** (waiter, kitchen, cashier) and their PINs are created by running:  
     `python scripts/add_staff_users.py`  
     Then: `1111` = waiter1, `2222` = waiter2, `3333` = kitchen1, `4444` = cashier1.  
   Change these in production.

3. **Pages**  
   - **/** (`index.html`): Add categories and menu items; view lists. Use this or the Counter’s “Menu Management” tab to build the menu.  
   - **/waiter**: Waiter POS. Select items from the menu grid, adjust quantities in the cart, enter table number, then “Submit Order”. Orders are created with status `pending`.  
   - **/kitchen**: Kitchen Display. Shows pending orders as tickets (table, time, items). “Mark as Done” sets status to `completed`. List refreshes every 5 seconds.  
   - **/counter**: Counter/Admin. Two tabs:  
     - **Cashier / Billing**: Lists unpaid orders (pending/completed). Click an order to see the receipt; “Process Payment” calls the pay API and refreshes the list.  
     - **Menu Management**: Same as home — add categories and menu items, view lists.

4. **Order flow**  
   Waiter creates order (pending) → Kitchen sees it and marks done (completed) → Counter shows unpaid orders, processes payment (paid).

---

### မြန်မာ

1. **ပြင်ဆင်ခြင်း**  
   - လိုအပ်ပါက `.env.example` ကို `.env` သို့ကူးပါ။ ဖွံ့ဖြိုးမှုအတွက် `DATABASE_URL=sqlite:///./pos.db` သတ်မှတ်ပါ။  
   - တပ်ခြင်း: `pip install -r requirements.txt`  
   - လည်ပတ်ခြင်း: `uvicorn main:app --reload` (သို့မဟုတ် ကွန်ယက်မှ ဝင်ရန် `uvicorn main:app --host 0.0.0.0 --port 8000`)။  
   - ဘရောက်ဆာဖွင့်ခြင်း: `http://localhost:8000` (သို့မဟုတ် အခြားစက်မှ `http://<your-IP>:8000`)။

2. **လော့ဂ်အင်း URL နှင့် အကောင့်များ**  
   - **အကြီးတန်း (username + password):**  
     - URL: `http://localhost:8000/login`  
     - Username: `admin`  
     - Password: `admin123`  
   - **ဝန်ထမ်း (PIN ၄ လုံး):**  
     - URL: `http://localhost:8000/pin-login`  
     - ပုံသက်ရိုက် admin PIN: `1234`  
   - **ဝန်ထမ်းအကောင့်များ** (waiter, kitchen, cashier) နှင့် PIN များကို ဤဖြင့်ဖန်တီးသည် —  
     `python scripts/add_staff_users.py`  
     ထို့နောက်: `1111` = waiter1, `2222` = waiter2, `3333` = kitchen1, `4444` = cashier1။  
   ထုတ်လုပ်မှုတွင် ပြောင်းပါ။

3. **စာမျက်နှာများ**  
   - **/** (`index.html`): ကတ်တဂိုရီနှင့် မီနူးပစ္စည်းများ ထည့်ခြင်း၊ စာရင်းကြည့်ခြင်း။ မီနူးတည်ဆောက်ရန် ဤစာမျက်နှာ သို့မဟုတ် Counter ၏ “Menu Management” tab ကို အသုံးပြုပါ။  
   - **/waiter**: ဝိုင်တာ POS။ မီနူးဂရစ်မှ ပစ္စည်းများရွေးချယ်၊ ခြင်းတန်းတွင် အရေအတွက် ပြင်ဆင်၊ စားပွဲနံပါတ်ထည့်၊ “Submit Order” နှိပ်ပါ။ အမှာစာများကို status `pending` ဖြင့်ဖန်တီးသည်။  
   - **/kitchen**: ချက်ပြုတ်ခန်းပြသခြင်း။ pending အမှာစာများကို တစ်ကတ်ချင်း (စားပွဲ၊ အချိန်၊ ပစ္စည်းများ) ပြသည်။ “Mark as Done” သည် status ကို `completed` သတ်မှတ်သည်။ စာရင်းကို ၅ စက္ကန့်တစ်ခါ ပြန်စတင်သည်။  
   - **/counter**: ငွေကောက်ခံ/အကြီးတန်း။ tab နှစ်ခု —  
     - **Cashier / Billing**: ငွေမချေရသေးသော အမှာစာများ (pending/completed) စာရင်း။ အမှာစာတစ်ခုကို နှိပ်ပြီး ပြေစာကြည့်ပါ။ “Process Payment” သည် pay API ကိုခေါ်ပြီး စာရင်းကိုပြန်စတင်သည်။  
     - **Menu Management**: ပင်မစာမျက်နှာကဲ့သို့ — ကတ်တဂိုရီနှင့် မီနူးပစ္စည်းများ ထည့်ခြင်း၊ စာရင်းကြည့်ခြင်း။

4. **အမှာစာ စီးဆင်းမှု**  
   ဝိုင်တာက အမှာစာဖန်တီး (pending) → ချက်ပြုတ်ခန်းက မြင်ပြီး ပြီးပါက မှတ် (completed) → ငွေကောက်ခံက ငွေမချေရသေးသော အမှာစာများပြပြီး ငွေချေခြင်း လုပ်သည် (paid)။

---

## Environment | ပတ်ဝန်းကျင်

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite: `sqlite:///./pos.db`. Production: e.g. `postgresql://user:pass@host:5432/dbname` |

---

## License

Use and modify as needed for your project.
