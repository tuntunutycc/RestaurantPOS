# Implementation: Cashier Name on Checkout & Receipt

- `models.Order.cashier_name`
- `schemas.OrderCheckoutRequest` / `OrderResponseDetail`
- `main.py` SQLite `ALTER TABLE orders ADD COLUMN cashier_name`
- `routers/orders.py` checkout persist + pass to receipt dispatch
- `services/printing/receipt.py` + `service.py`
- `static/counter.html` / `counter.js` — `currentCashierName`
- `tests/test_cashier_name_receipt.py`
