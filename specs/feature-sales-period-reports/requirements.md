# Feature: Sales Period Reports (Revenue Breakdown)

## Purpose
Admin/account users need Daily and Monthly sales aggregates with a **simultaneous** financial breakdown: Net Sales + Tax Collected = Gross Sales — so owners see the full picture at a glance (no hide-via-toggle).

## API: `GET /api/reports/sales`
| Query | Rule |
|-------|------|
| `period` | `daily` \| `monthly` (required) |
| `date` | Daily: `YYYY-MM-DD`; Monthly: `YYYY-MM` (required) |

**Roles:** `root`, `admin`, `account` (`FULL_REPORT_ROLES`). Account role subject to 90-day lookback.

**Paid statuses:** `paid`, `completed`.

**Response (`SalesPeriodReportResponse`):**
| Field | Definition |
|-------|------------|
| `period`, `date` | Echo of request |
| `total_orders` | Count of paid orders in range |
| `subtotal_revenue` | Sum of (`total_amount − tax_amount`) — net / tax-exclusive |
| `total_tax` | Sum of `tax_amount` |
| `grand_total_revenue` | Sum of `total_amount` — gross / tax-inclusive |
| `total_cash` | Sum of applied `cash_amount` (legacy fallback by `payment_method`) |
| `total_mobile` | Sum of applied `mobile_money_amount` (legacy fallback) |

## Frontend (Dashboard → Sales Reports)
- Period Daily/Monthly + date/month picker (no Include Tax toggle)
- **Revenue breakdown** shown together:
  1. Net Sales ← `subtotal_revenue`
  2. Tax Collected ← `total_tax`
  3. Gross Sales ← `grand_total_revenue` (most prominent)
- Payment: Cash Received / Mobile Received + Total Orders

## Frontend (Dashboard → Today's Overview)
- Same principle: Net / Tax / Gross visible together (no tax toggle)
- Cash & Mobile remain payment-received amounts
- AOV based on Gross Sales ÷ orders

## Related
- `specs/feature-payment-method-analytics/`
- `specs/feature-account-reports/`
- `specs/feature-split-payment/`
