# Implementation: Payment Method Analytics

## Checkout
- `schemas.OrderCheckoutRequest.payment_method` — required; normalized to `cash` \| `mobile_money`
- `PUT/POST /api/orders/{id}/checkout` persists `Order.payment_method`
- UI: `#pane-checkout` Cash / Mobile Money toggle (`static/counter.html` / `counter.js`)

## Analytics
- `GET /api/analytics/sales-breakdown` — `routers/analytics.py`
- Roles: root/admin/account store-wide; cashier = own `checked_out_by_id`; waiter **403**

## Tests
- `tests/test_payment_method_analytics.py`
