# Implementation: Sales Period Reports

- `schemas.SalesPeriodReportResponse`, tax fields on `TodaySalesSummaryResponse` / `PaymentMethodTotalsResponse`
- `routers/reports.py` — `GET /api/reports/sales`; summary/today tax fields
- `routers/analytics.py` — sales-breakdown tax-aware revenue fields
- Dashboard **Sales Reports** + **Overview**: simultaneous Net / Tax / Gross (no Include Tax toggle)
- `static/counter.html` / `counter.js`
- `tests/test_sales_period_reports.py`
