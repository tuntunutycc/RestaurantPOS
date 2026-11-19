# Plan: Daily voucher number

Order (contract first):
1. `schemas.py`: `voucher_no: str | None = None` on `OrderResponseDetail`, `OrderDetailsResponse`, `DailyOrderHistoryOrder`. `api-reference.md`, `database-schema.md`.
2. `models.py`: `Order.voucher_date`, `Order.voucher_seq`, unique index `ux_orders_voucher`, property `Order.voucher_no`.
3. `main.py` startup: `ALTER TABLE orders ADD COLUMN voucher_date VARCHAR(8)` / `voucher_seq INTEGER`, then `CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_voucher`.
4. `services/voucher.py`: `business_date(now_utc)` (UTC+06:30), `format_voucher_no`, `next_voucher_seq(db, voucher_date)`, `assign_voucher(db, order, now_utc=None)`.
5. `routers/orders.py` checkout: apply payment fields and the voucher inside one retry loop (rollback + retry on `IntegrityError` of the voucher index; `503` after 5 tries). Pass `voucher_no` to the receipt.
6. `services/printing/receipt.py` + `service.py`: optional `voucher_no`; `Voucher:` line, fallback `Order: #id`.
7. `services/order_history.py`, `static/order-history.js` / `.html`: voucher in list, detail title, export column.
8. Tests (`tests/test_voucher_number.py`), CHANGELOG, `validation.md`.

Design notes
- The number is read as `MAX(voucher_seq)+1` for the day; the unique index is the guard against two checkouts racing. This works the same on SQLite and on PostgreSQL later, and needs no separate counter table that could drift from the orders (clearing sales resets the day automatically).
- Time is injected (`now_utc`) so tests can cross midnight without waiting.
