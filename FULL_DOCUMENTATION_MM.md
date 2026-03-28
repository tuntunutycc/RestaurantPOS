# Restaurant POS — Full Documentation (မြန်မာ)

## 1. ခြုံငုံသုံးသပ်ချက်
ဒီပရောဂျက်က Restaurant POS (Point of Sale) စနစ်တစ်ခုဖြစ်ပြီး အောက်ပါလုပ်ငန်းတွေကို တစ်စုတစ်စည်းတည်း ထောက်ပံ့ပါတယ်။
1. **Menu စီမံခန့်ခွဲမှု** (Categories + Menu Items)
2. **Waiter အော်ဒါယူခြင်း** (Cart + Table Number)
3. **Kitchen Display System (KDS)** (Batch/Ticket အလိုက်ချက်ပြုတ်ရန်)
4. **Counter/Billing** (Checkout + Thermal Receipt Printing)
5. **Security**: JWT Authentication + RBAC (Role-Based Access Control)
6. **Staff attribution**: Order batch (ticket) တစ်ခုချင်းစီကို အော်ဒါဖန်တီးတဲ့ ဝန်ထမ်းနဲ့ချိတ်ဆက်ထားခြင်း
7. **Admin User Management**: ဝန်ထမ်း PIN အသုံးပြုသူများကို CRUD လုပ်နိုင်ခြင်း

Local network ပေါ်မှာ အလုပ်လုပ်ရန်ရည်ရွယ်ထားပြီး WebSockets နဲ့ real-time update တွေကို အသုံးပြုထားပါတယ်။

## 2. နည်းပညာ Stack
Backend:
- FastAPI
- SQLAlchemy (ORM)
- SQLite (Development) / PostgreSQL (Production `DATABASE_URL` နဲ့ ပြောင်း)
- WebSockets (FastAPI)

Frontend:
- Vanilla HTML + JavaScript (Fetch API, WebSocket API)
- Tailwind CSS (CDN)
- Toast UI ( `static/toast.js` )

## 3. Setup & Run

### 3.1 Install
```bash
cd /Users/ttw/Documents/My_Project/RestaurantPOS
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

ဖွင့်ရန်:
- ဒီကွန်ပျူတာမှာ: `http://localhost:8000`
- Network ထဲက အခြားကိရိယာတွေမှ: `http://<HOST_IP>:8000`

### 3.2 Environment
`.env` ကိုလိုအပ်ရင် `.env.example` ကိုသုံးပြီး တင်ပါ။
- `DATABASE_URL`
- `JWT_SECRET_KEY` (production အတွက် အလွန်ရှည်ပြီး random ဖြစ်အောင်ထားပါ)

## 4. Database Schema (အဓိကဇယားများ)

### 4.1 `users`
အသုံးပြုသူအကောင့်တွေ:
- `id` (PK)
- `username` (unique)
- `password_hash` (admin username/password login အတွက်)
- `role` (admin/waiter/kitchen/cashier)
- `pin_code` (staff PIN login အတွက် 4-digit, unique)

### 4.2 `categories`
- `id`
- `name`

### 4.3 `menu_items`
- `id`
- `name`
- `price`
- `description` (nullable)
- `image_url` (nullable; `static/images/` မှ serve)
- `category_id` (FK)

### 4.4 `orders`
Table တစ်ခုအတွက် dining session ကိုကိုယ်စားပြု:
- `id`
- `table_number`
- `status` (pending/open/dining/completed/paid စသည်)
- `total_amount`
- `created_at`
- cashier checkout fields:
  - `payment_method`
  - `amount_tendered`
  - `change_amount`

### 4.5 `order_items`
Order line item + Batch/Ticket အတွက် core:
- `order_id`
- `menu_item_id`
- `quantity`
- `subtotal`
- `batch_number` (ticket number)
- `batch_status` (pending/completed)
- **`created_by_id`** (ဒီ batch/ticket ကိုဖန်တီးတဲ့ ဝန်ထမ်း user id)

Kitchen က `batch_number` အလိုက် ticket ခွဲပြပြီး `batch_status == pending` ကိုသာပြပါတယ်။

## 5. Authentication & RBAC

### 5.1 JWT Login
Login API:
1. Admin (username/password)
   - `POST /api/auth/login`
2. Staff (PIN)
   - `POST /api/auth/login-pin`

အောင်မြင်ရင် token + user info ပြန်ပေးပြီး frontend က protected API များကို
`Authorization: Bearer <token>` နဲ့ ပို့ရပါတယ်။

### 5.2 Role
ခွင့်ပြု role များ:
- `admin`
- `waiter`
- `kitchen`
- `cashier`

RBAC အကျဉ်း:
- Categories/Menu Items **read**: authentication လိုအပ်
- Categories/Menu Items **write/create**: **admin only**
- Orders/Checkout: authentication လိုအပ်
- User Management: **admin only**

## 6. Login URLs & Default Credentials

### 6.1 Default Admin
ပထမဆုံး run မှာ admin မရှိသေးရင် default create လုပ်နိုင်ပါတယ်။
- Username: `admin`
- Password: `admin123`
- PIN: `1234` (pin-login နဲ့လည်းဝင်လို့ရ)

### 6.2 Staff PIN Users
Staff PIN တွေကို `users` table ထဲထည့်ဖို့လိုပါတယ်။
နည်း ၂ ခုရှိပါတယ်။
1. script နဲ့
   - `python scripts/add_staff_users.py`
2. Admin UI နဲ့
   - `/counter` → **User Management** tab

## 7. WebSockets (Real-time)
WebSocket endpoint:
- `/ws`

အသုံးပြု event များ:
- `menu_item_added`
- `new_order_batch`
- `batch_completed`

## 8. API Reference (အရေးကြီး endpoints)

### Auth
- `POST /api/auth/login`
- `POST /api/auth/login-pin`
- `GET /api/auth/me`

### Menu
- `GET /api/categories/`
- `POST /api/categories/` (admin-only)
- `GET /api/menu-items/` (optional `?category_id=`)
- `POST /api/menu-items/` (admin-only)
- `POST /api/menu-items/upload` (admin-only)

### Image upload
- `POST /api/upload` (admin-only)

### Orders (Batch/Ticket flow)
- `POST /api/orders/submit`
- `GET /api/orders/` (KDS refresh အတွက်)
- `PUT /api/orders/{order_id}/batches/{batch_number}/status` (ticket done)
- Cashier:
  - `GET /api/orders/tables`
  - `GET /api/orders/active-by-table/{table_id}`
  - `PUT /api/orders/{order_id}/checkout`

### Admin User Management (CRUD)
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`

## 9. Frontend Pages (User Experience)

### `/pin-login` (Staff 4-digit PIN numpad)
- 4 dots display
- Auto-submit အတွက် 4th digit ထည့်တာနဲ့ API ခေါ်
- Wrong PIN ဖြစ်ရင် clear + dots shake + error

### `/waiter`
- Sticky category tabs
- Menu grid + Cart
- Table number
- Submit Order → `POST /api/orders/submit`

### `/kitchen` (KDS)
- Ticket grid (batch_number အလိုက်)
- Ticket header မှာ:
  - Table number
  - Ticket #
  - **Waiter name (“Waiter: John”)**
- Mark as Done → batch_status update (အဲ့ ticket တစ်ခုသာ)

### `/counter` (Cashier + Admin)
- Tabs:
  - Cashier / Billing
  - Menu Management
  - User Management (admin)
- Receipt:
  - **Served by: waiter name**
  - Checkout ပြီးနောက် print CSS နဲ့ thermal receipt print

## 10. Order Flow (End-to-End)

1. Waiter → `/pin-login` ဝင် → `/waiter`
2. Waiter submit → backend က JWT ထဲက user id ကို ယူပြီး
   `created_by_id` ကို `OrderItem` rows ထဲထည့်
3. KDS fetch/expand → Ticket တစ်ခုချင်းစီမှာ Waiter name ပြ
4. Chef done → ticket batch_status updated + KDS remove only that ticket
5. Cashier checkout → payment fields save + receipt print

## 11. Troubleshooting

### Wrong PIN
- သက်ဆိုင်ရာ PIN နဲ့ staff user မရှိတာဖြစ်နိုင်ပါတယ်။
- script သို့မဟုတ် User Management tab မှာ staff အသစ် create လုပ်ပါ။

### 401 Unauthorized
- JWT မပါဘဲ protected API ကိုခေါ်ထားတာဖြစ်နိုင်ပါတယ်။
- မှန်ကန်တဲ့ login နဲ့ role မှန်မှန်ဝင်ပါ။

### “Served by / Waiter: —” မပေါ်
- အရင်က batch များ (migration မပြီးခင်က) မှာ `created_by_id` မရှိနိုင်ပါတယ်။
- နောက်ထပ် batch အသစ် create လုပ်ပြီးမှ ပေါ်လာပါမယ်။

## 12. Security Recommendations
1. `JWT_SECRET_KEY` ကို long random string သတ်မှတ်ပါ။
2. Production မှာ HTTPS သုံးပါ။
3. Server ကို firewall နဲ့ ကာကွယ်ပါ။
4. Admin endpoints ကို RBAC ဖြင့် စစ်ဆေးထားပြီးသားဖြစ်ပါတယ်။

