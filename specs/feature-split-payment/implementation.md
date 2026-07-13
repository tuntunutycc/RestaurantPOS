# Implementation: Split Payment

- `models.Order.cash_amount`, `mobile_money_amount`
- `OrderCheckoutRequest` optional amounts; legacy `payment_method` + `amount_tendered` still work
- `routers/orders.py` checkout allocation + change
- `routers/analytics.py` sum applied amounts
- `static/counter.html` / `counter.js` Split mode UI
- `tests/test_split_payment.py`
