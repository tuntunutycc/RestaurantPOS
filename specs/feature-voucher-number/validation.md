# Validation: Daily voucher number

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` (result at the bottom).

## Automated
- [x] Format `YYYYMMDD-NNNN`; 10000th of a day is `-10000`
- [x] Myanmar day boundary: 17:29:59 UTC and 17:30:00 UTC (= 23:59:59 / 00:00:00 +06:30) fall on different days; year-end rollover
- [x] First checkout of a day is `-0001`; consecutive checkouts `-0002`, `-0003`; a new day restarts at `-0001`; days independent
- [x] Unpaid and cancelled orders have no voucher; a cancelled order leaves no gap
- [x] A voucher is kept when the same order is checked out again
- [x] Clashing number (simulated race) → retried with the next number, payment recorded once; 5 clashes → `503`, order still unpaid
- [x] Unique index rejects two orders with the same `(voucher_date, voucher_seq)`; NULL rows are allowed many times
- [x] Contract: `voucher_no` in checkout, `GET .../details`, `PUT .../status`, daily history; `null` before payment; request cannot set it
- [x] Receipt text: `Voucher:` line; no voucher → `Order: #id`; kitchen slip unchanged
- [x] Daily history list and `.xlsx` carry the voucher
- [x] Roles: checkout roles unchanged (waiter `403`, anonymous `401`)
- [x] After `scripts/clear_sales.py` the next voucher of the day is `-0001`
- [x] Existing databases without the columns are upgraded at startup

## Review checklist
- Security / roles: no new endpoint; clients cannot choose the number.
- Money: no change to totals or payment rules; the voucher is assigned in the same transaction as the payment.
- Edge cases: day boundary, race, repeated checkout, sales cleared, old orders without a voucher.
