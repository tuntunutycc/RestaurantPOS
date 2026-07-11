# Validation: Payment Method Analytics

```bash
PYTHONPATH=. pytest tests/test_payment_method_analytics.py -v
PYTHONPATH=. pytest -q
```

## Automated

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Checkout with `mobile_money` | **200**; `order.payment_method == 'mobile_money'` |
| 2 | Checkout with invalid payment method | **422** |
| 3 | `GET /api/analytics/sales-breakdown` after cash + mobile checkouts today | Today cash/mobile sums match order totals |
| 4 | Cashier breakdown scoped | Only orders with `checked_out_by_id` = cashier |
| 5 | Waiter denied analytics | **403** |

## Manual
- [ ] Cashier checkout: toggle Cash / Mobile Money; confirm payment succeeds
- [ ] Admin Dashboard Overview: Today's and Monthly breakdown totals add up
- [ ] Cashier Dashboard: today breakdown shows own checkouts only; no monthly block
