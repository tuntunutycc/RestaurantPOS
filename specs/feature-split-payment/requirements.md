# Feature: Split Payment Checkout

## Purpose
Allow cashiers to settle one bill with **Cash + Mobile Money** in a single checkout, while keeping fast one-method checkout (Full Cash / Full Mobile Money). Persist per-method amounts for accurate daily/monthly reports.

## Data model
| Field | Rule |
|-------|------|
| `Order.cash_amount` | Amount of the bill paid by cash (applied, ≥ 0) |
| `Order.mobile_money_amount` | Amount of the bill paid by mobile money (applied, ≥ 0) |
| `Order.payment_method` | `cash` \| `mobile_money` \| `split` (derived if omitted) |
| `Order.amount_tendered` | Cash physically given (may exceed applied cash → change) |
| `Order.change_amount` | `amount_tendered − cash_amount` (applied cash), ≥ 0 |

Invariant: `cash_amount + mobile_money_amount == grand_total` (applied). Tendered cash may be higher.

## Checkout request
- **Legacy / single method:** `payment_method` + `amount_tendered` (unchanged; server fills amount columns).
- **Split / explicit amounts:** optional `cash_amount`, `mobile_money_amount` (tendered per method).
  - Require `cash_amount + mobile_money_amount >= grand_total`.
  - Apply mobile first up to total; remainder from cash; change from excess cash.

## Change Due (cash overpay in split)
- When mobile is entered, Cash auto-fills with **exact remaining** (`grand_total − mobile`).
- Cashier may increase Cash tendered above remaining; UI shows **Change Due** = excess cash (`cash_tendered − remaining`).
- Checkout allowed when `cash_tendered + mobile >= grand_total`.
- Receipt for split shows: Grand Total, Paid via Mobile, Tendered Cash, Change Due.

## Analytics
- Sales breakdown sums `cash_amount` and `mobile_money_amount` (fallback to legacy `payment_method` + `total_amount` when amount columns null).

## Related
- `specs/feature-payment-method-analytics/`
- `specs/feature-cashier-three-pane/`
