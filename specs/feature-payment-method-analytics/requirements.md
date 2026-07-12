# Requirements: Payment Method Analytics

## Purpose
Enable restaurant owners and cashiers to reconcile daily and monthly sales by **Cash** vs **Mobile Money**. Payment method is captured at checkout and aggregated on the Counter Dashboard.

## Data model

| Field | Rule |
|-------|------|
| `Order.payment_method` | Set at checkout only. Canonical values: `cash` \| `mobile_money` (stored lowercase snake_case). |
| Display labels | UI shows **Cash** and **Mobile Money**; API accepts common aliases and normalizes to canonical values. |

## FR-PM1: Checkout requires payment method
- `PUT /api/orders/{order_id}/checkout` body **must** include `payment_method`.
- Allowed values (after normalization): `cash`, `mobile_money`.
- Invalid or missing value → **422**.
- Persisted on `Order.payment_method` when status becomes `paid`.

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
- Invariant: `total == cash + mobile_money` (orders with null/unknown `payment_method` excluded from both buckets).

## FR-PM3: Cashier checkout UI
- Counter Check Out pane (`#pane-checkout`) shows two large toggle buttons: **💵 Cash** (default) and **📱 Mobile Money**.
- Selected value sent as `payment_method` in checkout payload (`cash` or `mobile_money`).

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
