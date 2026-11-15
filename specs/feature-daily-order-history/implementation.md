# Implementation: Daily Order History

## Backend
- `rbac.ORDER_HISTORY_ROLES` = root, admin, cashier
- `schemas.DailyOrderHistory*` contracts
- `services/order_history.py` — day query + `openpyxl` workbook builder
- `routers/orders.py` — `GET /api/orders/daily-history` + `/export`

## Frontend
- `static/order-history.html` / `order-history.js`
- Routes: `/order-history`, `/admin/sales-history`, `/cashier/history`
- `auth.js` nav link for root/admin/cashier

## Tests
- `tests/test_daily_order_history.py`
