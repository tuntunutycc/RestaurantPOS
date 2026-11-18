# Feature: KPay / MMQR payments and per-cashier payment report

## Purpose
The owner wants to know, for each cashier, how much was taken in **Cash**, **KPay** and **MMQR** (client list items 9 and 16). Until now checkout only knew `cash`, `mobile_money` and `split`, so the two mobile methods could not be told apart.

## Decisions (confirmed with the owner, 2026-11-18)

| Topic | Decision |
|-------|----------|
| Checkout methods | **Cash**, **KPay**, **MMQR**, **Split**. The **Mobile** button is removed. |
| Split | Any combination of Cash, KPay and MMQR, one amount each. |
| "Each cashier" | The **login account** that confirmed the payment (`Order.checked_out_by_id`). The free-text Cashier Name on the receipt is not used for grouping. Each cashier therefore needs their own PIN. |
| Old "Mobile Money" sales | The deployed shop restarts with cleared sales, so none are expected. If any exist they are reported as **Mobile (unspecified)**; they are never guessed to be KPay or MMQR and never dropped from a total. |
| KPay / MMQR as the only method | Amount must equal the bill; no change is ever given for a transfer. |
| Clearing sales | A script removes sales only and keeps staff, menu, tables and printers (FR-KM7). |

## FR-KM1: Data
- `orders.kpay_amount` `Float NULL`, `orders.mmqr_amount` `Float NULL`: the part of the bill paid by each method. Added to existing databases at startup.
- `orders.mobile_money_amount` is kept and is always `kpay_amount + mmqr_amount` for a new checkout, so every existing "mobile" total stays correct.
- `orders.payment_method`: `cash` | `kpay` | `mmqr` | `split`. (`mobile_money` only on rows from before this feature.)
- Invariant for every checkout made with this feature:
  `cash_amount + kpay_amount + mmqr_amount == total_amount`.

## FR-KM2: Checkout request (`OrderCheckoutRequest`)
- `payment_method`: `cash`, `kpay`, `mmqr` or `split` (case and spaces ignored, as before).
- New optional `kpay_amount`, `mmqr_amount` (≥ 0; negative → `422`).
- `payment_method = mobile_money`, or `mobile_money_amount` > 0, → `422` telling the client to use KPay or MMQR. The server does not guess which one was meant.
- **One method** (`payment_method` + `amount_tendered`, no amounts): the whole bill is recorded under that method.
  - `cash`: `amount_tendered` must cover the total; extra is change (as before).
  - `kpay` / `mmqr`: a transfer is an exact amount, so `amount_tendered` must **equal** the total. Less → `400` (as before); more → `400` ("… must equal the total"), never recorded as change. (Decided 2026-11-18.)
- **Amounts given** (any of `cash_amount`, `kpay_amount`, `mmqr_amount`):
  - `kpay_amount + mmqr_amount` must not be more than the total → otherwise `400`. A transfer is an exact amount; the server will not decide which of the two to reduce.
  - `cash_amount` is the cash handed over. `cash_amount + kpay_amount + mmqr_amount` must cover the total → otherwise `400`.
  - Applied cash = total − KPay − MMQR. Change = cash handed over − applied cash.
  - Stored `payment_method`: the single method that has an amount, or `split` when more than one has. A bill of 0 is stored as `cash`.
- A rejected checkout changes nothing: the order stays unpaid.

## FR-KM3: Checkout response and order details
`OrderResponseDetail` (and `OrderCheckoutResponse`) gain `kpay_amount`, `mmqr_amount`. `mobile_money_amount` stays (their sum).

## FR-KM4: Per-cashier report
`GET /api/reports/sales/by-cashier` (root, admin, account; unchanged roles, date range and ordering). Each row gains:

| Field | Meaning |
|-------|---------|
| `cash` | Cash part of that cashier's paid orders |
| `kpay` | KPay part |
| `mmqr` | MMQR part |
| `mobile_unspecified` | Mobile money from before this feature (0 on a cleared database) |

`total_sales` and `order_count` are unchanged. For orders paid with this feature `cash + kpay + mmqr == total_sales`.

## FR-KM5: Store totals
- `GET /api/analytics/sales-breakdown`: `today` and `month` gain `kpay`, `mmqr`. `mobile_money` stays and is all mobile money (KPay + MMQR + unspecified). Cashiers still see only their own checkouts.
- `GET /api/reports/sales`: gains `total_kpay`, `total_mmqr`. `total_mobile` stays (all mobile money).

## FR-KM6: Receipt
- `Payment:` shows `Cash`, `KPay`, `MMQR`, or `Split (…)` naming the methods used, e.g. `Split (Cash + KPay)`.
- A split receipt lists `Paid via KPay:` and/or `Paid via MMQR:` with their amounts; `Tendered Cash:` and `Change Due:` only when cash was part of the payment.
- Receipts recorded before this feature (`mobile_money`) still print as before on Retry.

## FR-KM7: Clear sales, keep the setup (`scripts/clear_sales.py`)
- Deletes all orders, order lines and print jobs; sets every table to `available`.
- Keeps users and their sessions, menu and categories, zones and tables, printers and print settings, predefined instructions, the admin audit log.
- Without `--yes` it only prints what would be deleted. With `--yes` it first copies a SQLite database file next to itself (`<name>.backup-YYYYmmdd-HHMMSS`), then deletes in one transaction. If the copy cannot be made it deletes nothing; an existing backup is never overwritten. A database that is not a SQLite file needs `--no-backup` to confirm the operator made their own. Backups are git-ignored (`*.db.backup-*`).
- Order numbers start again from 1.

## FR-KM8: Admin / cashier UI (`static/counter.html`, `counter.js`)
- Check Out: buttons **Cash**, **KPay**, **MMQR**, **Split**. Split shows **KPay Amount**, **MMQR Amount**, **Cash Tendered**; cash is filled with what is left after KPay + MMQR and can be raised for change. Confirm is disabled, with a message, when KPay + MMQR is more than the total or the three do not cover it.
- Dashboard → Staff Performance → **Sales by Cashier**: a table under the chart with one row per cashier: Cash, KPay, MMQR, Total, Orders, and a totals row. A **Mobile (unspecified)** column appears only when a row has such an amount.
- Dashboard today / month cards and Sales Reports show **KPay** and **MMQR** instead of one Mobile Money line; an unspecified line appears only when there is such an amount.
- Order History detail shows the method name and, for a split, the amounts.

## Non-goals
- Other wallets (Wave, AYA Pay, cards) or an admin-defined list of methods.
- Grouping by the free-text Cashier Name.
- Converting old `mobile_money` sales to KPay or MMQR.
- Shift open/close, cash drawer counting, refunds.
- Payment columns in the Excel export (existing gap, unchanged).
- Report days are still UTC days of `created_at`, like every other report.

## Related
- `specs/feature-split-payment/` (two-method split; superseded where it says Cash + Mobile Money)
- `specs/feature-payment-method-analytics/`
- `specs/feature-cashier-reports/`
