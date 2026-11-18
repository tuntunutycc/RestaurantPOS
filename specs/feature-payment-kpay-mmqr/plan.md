# Plan: KPay / MMQR payments and per-cashier payment report

Order follows `.cursorrules`: contract first, then server, then UI, then tests and docs.

1. **Contract** (`schemas.py`)
   - `OrderCheckoutRequest`: `kpay_amount`, `mmqr_amount`; `payment_method` accepts `cash|kpay|mmqr|split`; `mobile_money` and `mobile_money_amount > 0` rejected.
   - `OrderResponseDetail`: `kpay_amount`, `mmqr_amount`.
   - `CashierSalesPointResponse(StaffSalesPointResponse)`: `cash`, `kpay`, `mmqr`, `mobile_unspecified`.
   - `PaymentMethodTotalsResponse`: `kpay`, `mmqr`. `SalesPeriodReportResponse`: `total_kpay`, `total_mmqr`.
2. **Data** (`models.py`, `main.py` lifespan): two nullable Float columns + `ALTER TABLE` blocks (existing pattern).
3. **Checkout** (`routers/orders.py::_resolve_checkout_payment`): rules of FR-KM2; store the two amounts; pass them to the receipt job.
4. **Reports**: one shared set of SQL expressions (`services/payment_totals.py`) used by `by-cashier`, `sales-breakdown` and `reports/sales`, so the three cannot disagree.
5. **Receipt** (`services/printing/receipt.py`, `service.py`): labels and split lines.
6. **Script** `scripts/clear_sales.py` + README section.
7. **UI** (`static/counter.html`, `counter.js`, `order-history.js`).
8. **Tests** `tests/test_payment_kpay_mmqr.py`, `tests/test_clear_sales.py`; update tests that paid with `mobile_money`.
9. **Docs**: `api-reference.md`, `database-schema.md`, split-payment and payment-analytics specs, `validation.md`, `CHANGELOG.md`.
