# Feature: Daily voucher number

## Purpose
The owner wants the voucher (receipt) number to **restart at 1 every day** and to be written together with the date, for example `20261119-0001`. Until now the receipt printed `Order: #<orders.id>`, a counter that never restarts.

## Decisions (confirmed with the owner, 2026-11-19)

| Topic | Decision |
|-------|----------|
| When the number is given | At **checkout** (when the order becomes `paid`). Unpaid and cancelled orders never get one, so there are no gaps from cancelled orders. |
| Day change | Midnight **Myanmar time (UTC+06:30)**. Myanmar has no daylight saving, so a fixed offset is used. |
| Format | `YYYYMMDD-NNNN`, e.g. `20261119-0001` (sequence is at least 4 digits; the 10000th voucher of a day is `20261119-10000`). |
| Orders from before this feature | Not renumbered. They have no voucher and keep showing `#<order id>`. (The owner clears the test sales, so none are expected.) |
| Clearing sales | After `scripts/clear_sales.py`, the next voucher of the day is `-0001` again, because the next number is read from the orders that exist. |
| `orders.id` | Unchanged. It stays the internal key (print jobs, API paths, kitchen slips). |

## FR-V1: Data
- `orders.voucher_date` `String(8) NULL` (`YYYYMMDD`, Myanmar date of checkout) and `orders.voucher_seq` `Integer NULL`. Added to existing databases at startup.
- Unique index on `(voucher_date, voucher_seq)`: two orders can never share a voucher number. Rows without a voucher (NULL) do not conflict.
- `Order.voucher_no` is **derived** (`f"{voucher_date}-{voucher_seq:04d}"`, `None` when either part is missing). It is not stored, so it cannot disagree with its parts.

## FR-V2: Assignment
- `PUT/POST /api/orders/{id}/checkout` gives the order `voucher_seq = (highest seq for that voucher_date) + 1`, in the same database transaction as the payment.
- If another checkout took the same number at the same moment (unique index violation), the checkout is **retried** with the next number (up to 5 times). A payment is never lost or refused because of a number clash; after 5 failed attempts the request answers `503` and the order stays unpaid.
- A checkout of an order that already has a voucher **keeps** it; a number is never re-issued or changed.
- The sequence of a day is `1, 2, 3, …` in checkout order. Different days are independent.

## FR-V3: API contract
- `voucher_no: str | null` is added to the responses that describe an order: checkout (`OrderCheckoutResponse`), `OrderResponseDetail`, `OrderDetailsResponse` (`GET .../details`, `PUT .../items/{id}/status`) and `DailyOrderHistoryOrder`.
- It is `null` for an unpaid order and for orders made before this feature.
- Requests do not accept a voucher number; the server alone decides it.

## FR-V4: Printed and shown
- **Cashier receipt:** first line `Voucher: 20261119-0001`. When the order has no voucher (old queued receipt), the old `Order: #<id>` line is printed.
- **Kitchen slips:** unchanged (`Order: #<id>`); they are printed before payment, when no voucher exists yet.
- **Order History** (list, detail window, `.xlsx` export): shows the voucher; falls back to `#<id>` for orders without one. The export gets a `Voucher No` column after `Order ID`.
- The Print Jobs page and waiter screens keep `#<id>`.

## Known limits (stated so nobody is surprised)
- **Order History and the sales reports still cut the day at UTC midnight** (06:30 Myanmar time), as before. Between 00:00 and 06:30 Myanmar time a voucher is dated with the new Myanmar day while the order still appears under the previous UTC day. Moving the reports to Myanmar days is a separate change (it touches every report) and is not part of this feature.
- The voucher date is the date of **checkout**, while Order History groups by the date the order was **opened**. An order opened before midnight and paid after midnight carries the later date.
- Voucher numbers are not guaranteed gap-free if a database row is deleted by hand.

## Out of scope
- Renumbering old orders; a configurable time zone; a voucher search box; per-printer or per-cashier sequences.
