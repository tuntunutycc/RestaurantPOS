# Requirements: Payment Method Analytics

## Purpose
Enable restaurant owners and cashiers to reconcile daily and monthly sales by **Cash** vs **Mobile Money**. Payment method is captured at checkout and aggregated on the Counter Dashboard.

## Data model

| Field | Rule |
|-------|------|
| `Order.payment_method` | Set at checkout. Canonical: `cash` \| `mobile_money` \| `split`. |
| `Order.cash_amount` / `mobile_money_amount` | Applied bill portions per method (split-aware). |
| Display labels | UI shows **Cash**, **Mobile Money**, **Split**; API accepts aliases. |

## FR-PM1: Checkout payment method
- `PUT /api/orders/{order_id}/checkout` accepts `payment_method` and/or explicit `cash_amount` / `mobile_money_amount`.
- Allowed method values: `cash`, `mobile_money`, `split`.
- Invalid method → **422**.
- Persisted on `Order.payment_method` when status becomes `paid`.
- Prefer summing `cash_amount` / `mobile_money_amount` for reports (see split-payment feature).

## FR-PM2: Sales breakdown API
- `GET /api/analytics/sales-breakdown`
- **Roles:** `root`, `admin`, `account` → store-wide totals; `cashier` → own checkout totals (`Order.checked_out_by_id`).
- Response:

```json
{
  "today": { "cash": 300.0, "mobile_money": 200.0, "total": 500.0 },
  "month": { "cash": 9000.0, "mobile_money": 6000.0, "total": 15000.0 }
}
```

- **Today:** UTC calendar day, `Order.status IN ('paid','completed')`.
- **Month:** current UTC calendar month (1st 00:00 through next month 1st 00:00).
- Invariant: `total == cash + mobile_money` (uses applied amount columns; legacy rows fall back to `payment_method` + `total_amount`).

## FR-PM3: Cashier checkout UI
- Counter Check Out pane shows **Cash**, **Mobile Money**, and **Split** toggles.
- Single-method: amount tendered + `payment_method`.
- Split: cash + mobile inputs (auto-fill remainder); see `specs/feature-split-payment/`.

## FR-PM4: Dashboard UI (Counter — `static/counter.js`)
- Overview tab shows payment breakdown cards:
  - **Today's Sales** total with Cash / Mobile Money lines.
  - **Monthly Sales** total with Cash / Mobile Money lines (hidden for cashier per existing dashboard RBAC).
- Totals must match `GET /api/analytics/sales-breakdown`.

## Authorization summary

| Role | Breakdown scope | Monthly section |
|------|-----------------|-----------------|
| root, admin, account | Store-wide | Visible |
| cashier | Own checkouts only | Hidden |

## Related
- `specs/database-schema.md` — `orders.payment_method`
- `specs/api-reference.md` — checkout + analytics contracts
- `specs/feature-cashier-reports/` — cashier checkout attribution
