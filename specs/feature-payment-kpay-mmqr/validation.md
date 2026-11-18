# Validation: KPay / MMQR payments and per-cashier payment report

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` → **474 passed** (2026-11-18; 82 in `tests/test_payment_kpay_mmqr.py`, 18 in `tests/test_clear_sales.py`).

## Automated

### Checkout (FR-KM1 – FR-KM3)
- [x] Cash, KPay, MMQR as a single method: stored method, the whole bill under that method, the other amounts 0, `mobile_money_amount` = KPay + MMQR
- [x] Method name in any case / with spaces (`" MMQR "`)
- [x] Split of Cash + KPay + MMQR; split of KPay + MMQR without cash; amounts given for one method only are stored as that method, not `split`
- [x] KPay / MMQR alone: above the bill (`10000.01`, `10001`, `15000`) → `400` "must equal the total"; below → `400`; exact → `200`; after a 10% discount 10000 is refused and 9000 accepted. Cash alone above the bill still gives change
- [x] Extra cash gives change; applied cash = total − KPay − MMQR; amounts with cents
- [x] `cash_amount + kpay_amount + mmqr_amount == total_amount` on every accepted checkout, also after a discount
- [x] KPay + MMQR above the total → `400`, order stays unpaid (also when the total was lowered by a discount)
- [x] Amounts below the total → `400`, order stays unpaid
- [x] `payment_method = mobile_money` / `mobile` → `422`; `mobile_money_amount` above 0 → `422`; `mobile_money_amount = 0` is harmless
- [x] Negative amounts, unknown method, text instead of a number → `422`
- [x] `NaN` / `Infinity` in any money field (11 bodies) → `422` (not `500`), order stays unpaid
- [x] Roles: waiter and account `403`, anonymous `401`, cashier / admin / root `200`

### Reports (FR-KM4, FR-KM5)
- [x] `by-cashier`: two cashiers paying with every method on the same day each get their own Cash / KPay / MMQR; split bills are divided by part; another day and unpaid orders are left out
- [x] `cash + kpay + mmqr + mobile_unspecified == total_sales` per cashier
- [x] A sale from before the feature (mobile money without KPay/MMQR) is reported as `mobile_unspecified`, not as KPay or MMQR, and stays in the total
- [x] `by-cashier` roles: root / admin / account `200`, cashier / waiter `403`
- [x] `sales-breakdown`: `kpay`, `mmqr` and `mobile_money` rise by the right amounts; a cashier sees only their own checkouts
- [x] `reports/sales`: `total_cash`, `total_kpay`, `total_mmqr`, `total_mobile`
- [x] `daily-history`: every order carries its payment parts

### Receipt (FR-KM6)
- [x] `Payment:` shows `Cash`, `KPay`, `MMQR`, or `Split (…)` naming only the methods used
- [x] Split prints `Paid via KPay` / `Paid via MMQR`; the cash lines only when cash was part of it
- [x] A receipt for an old Cash + Mobile split prints as before
- [x] End to end: the receipt printed after a split checkout carries the same amounts as the stored order

### Existing database
- [x] Real app startup on a database without the columns adds `kpay_amount` and `mmqr_amount` and keeps the existing orders

### Clear sales script (FR-KM7)
- [x] Counting changes nothing
- [x] Deletes orders, order lines and print jobs; users, sessions, menu, categories, zones, printers, print settings, instruction tags and the audit log are identical row for row before and after
- [x] Every table ends `available`; the next order and order line are number 1; running it twice is harmless
- [x] Backup is a full copy containing the old sales; an existing backup is never overwritten; a missing database file is an error
- [x] Command without `--yes` shows counts and changes nothing, writes no file
- [x] Command with `--yes` writes the backup, then deletes
- [x] Backup impossible (not a SQLite file) or failing → exit code 1, nothing deleted; `--no-backup` deletes without a copy
- [x] A failure part way through leaves every sale and table status as it was
- [x] Database file missing (wrong folder), with or without `--yes` / `--no-backup`: exit 1, no file created, nothing deleted; a relative `DATABASE_URL` is printed as the full path

### UI
- [x] The dashboard caches are declared before the page opens the dashboard (see Fixed below)

### Test strength
Forty-nine deliberate breakages were each caught by a test: mobile amounts above the total accepted or capped; underpayment accepted; change computed from the wrong amount; MMQR stored as KPay (single and split); split not detected; amounts not saved; receipt job without the KPay amount; `mobile_money` accepted as KPay; `mobile_money_amount` ignored; negative amounts accepted; response without the new field; report columns swapped, summing the wrong thing, counting unpaid orders or readable by a cashier; unspecified mobile money dropped or counted as KPay; receipt lines missing or always printed; the script keeping order lines, leaving tables occupied, not rolling back, deleting without `--yes`, deleting without a backup, overwriting a backup, deleting sessions and audit log; migration removed; the missing-file check removed; `NaN` accepted by `amount_tendered`, `cash_amount`, `kpay_amount`, `discount_value`; the 422 handler not installed; the KPay/MMQR equal-to-bill rule removed, applied to cash too, or applied to KPay only.

## Manual (2026-11-18, real app with its print queue on a temporary database, file print backend, desktop browser 1024 px wide)
- [x] Two cashiers (own PINs), seven bills: cash, KPay, MMQR and three kinds of split. API rejected `mobile_money` (`422`), `mobile_money_amount` (`422`), KPay + MMQR above the total (`400`), underpayment (`400`)
- [x] Checkout panel: buttons **Cash / KPay / MMQR / Split**. KPay with too little entered keeps **Confirm Payment** disabled
- [x] Split: KPay 1000 → Cash auto-fills 2500; + MMQR 500 → Cash 2000; MMQR 3000 → "KPay + MMQR is more than the total", confirm disabled; Cash 1000 → "Insufficient", disabled; Cash 5000 → Change Due 3,000 Ks, enabled. Confirmed: order stored as `split` 2000 / 1000 / 500, tendered 5000, change 3000, table freed
- [x] Single KPay (bill 3,500): choosing KPay fills in 3,500; typing 5,000 shows "Must equal the total" and disables confirm; 3,000 shows "Insufficient"; 3,500 enables it; cash 5,000 still shows change 1,500. Confirmed KPay stored as `kpay` 3500
- [x] Printed receipt of that bill: `Payment: Split (Cash + KPay + MMQR)`, `Paid via KPay: 1000.00`, `Paid via MMQR: 500.00`, `Tendered Cash: 5000.00`, `Change Due: 3000.00`
- [x] Dashboard → Staff Performance → **Cash / KPay / MMQR by cashier**: one row per cashier and an **All cashiers** row; figures equal the sums of the stored orders
- [x] Cashier's own dashboard shows only their Cash / KPay / MMQR; Sales Reports cards show Cash / KPay / MMQR Received
- [x] An old-style Cash + Mobile sale inserted by hand: a **Mobile (unspecified)** column / line appears in the three places with its amount; hidden when there is none
- [x] Order History details: `KPay`, `MMQR`, `Split: Cash … + KPay … + MMQR …`, old sale `Split: Cash … + Mobile …`
- [x] `scripts/clear_sales.py` on the temporary database while it held 9 orders and one occupied table: dry run changed nothing; `--yes` wrote the backup (9 orders inside) and left 0 orders / lines / print jobs, 4 users, 3 menu items, 8 tables all available, 2 printers. PIN login still worked and the next order was #1
- [x] The developer's real `pos.db` had the same checksum before and after all of the above

## Fixed while validating
- Counter page: the dashboard figures stayed at 0 after opening the page until the **Dashboard** tab was clicked. The page opened the dashboard before the two variables that hold the figures were declared, so the load stopped with an error that was never shown. The problem was already there before this feature; the declarations were moved up and a test checks their position.

## Not verified
- [ ] Checkout panel and the per-cashier table on a phone-sized or tablet screen. At 1024 px the table needs a sideways scroll to show the **Orders** column
- [ ] Burmese (မြန်မာ) language mode: the new labels are English only
- [ ] A real receipt printer (only the file backend was used here; the text is the same)
- [ ] `scripts/clear_sales.py` on Windows and on the deploy machine's database
- [ ] The Account page (`/account`) still lists cashier totals only, without the Cash / KPay / MMQR split
- [ ] Excel export of the order history has no payment columns (non-goal)
