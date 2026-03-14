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
