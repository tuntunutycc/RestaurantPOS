# Changelog

## 2026-11-19 — Fix: `GET /api/orders/tables` 500 and the missing "Confirm Delete" label

### Fixed
- `GET /api/orders/tables` answered `500` (`TypeError`, sorting `None` against an int) whenever an open takeaway order existed next to an open table order. Orders that have no table (takeaways) are now left out of this list; they were never a table, and `GET /api/orders/active-takeaways` lists them. Response shape unchanged. (Decision made by the assistant from the endpoint's documented purpose, "checkout-ready tables"; tell me if takeaways should appear here instead.)
- The delete confirmation button showed the raw key `confirm_delete`. Added the `confirm_delete` label to `i18n.js` (en / my).

### Tests
- `tests/test_orders_tables_endpoint.py` (4); `tests/test_snapshot_first_names.py` now also asserts the sold-as name on `/orders/tables`.
- `tests/test_mixed_takeaway_kitchen_slip.py` (6): one dine-in table with some lines takeaway. Locks in that the `(ပါဆယ်)` marker is on the takeaway lines only (both kitchen slip modes, later batches, image mode, receipt, Table Details, Order History) and that the header stays `Table: N`. Suite: 674 passed.

## 2026-11-19 — Linked add-ons (an add-on can follow a main menu item's price)

### Summary
An add-on option (e.g. "extra egg") can now optionally be linked to a main menu item, so when the owner raises that item's price the add-on price follows. Add-ons that are not linked work exactly as before. No database column, table or migration: the two new keys live inside the existing `modifiers_config` JSON.

### Added
- `ModifierOption.linked_menu_item_id` and `price_override` (optional; `0` is a real override). `SelectedModifier.linked_menu_item_id`.
- Saving a menu item: the link target must exist (`404`) and not be the item itself (`422`); a blank add-on name is filled with the target's name; the server stores the effective price in `option.price` (fallback, never `0` by accident); `price_override` without a link and duplicate `(group, name)` in an item with a link are refused (`422`).
- When a main item's price changes, add-ons that follow it (no override) get the new stored price in the same transaction and `menu_item_updated` is sent for the item and each changed holder.
- Deleting a menu item that is still linked is refused with `400`; the message lists the menu items (name + id) that link to it.
- Ordering (create / add to order / submit): a linked add-on is priced by the server from the live menu; the price a screen sends is ignored. The order line snapshot stores `linked_menu_item_id` for future reports (unlinked add-ons store nothing extra).
- Admin form (`counter.js` / `counter.html`): per option a "Link to menu item" select, name auto-fill (only when empty, editable), price shown read-only with "Custom price" / "Follow main price". Waiter screen refreshes linked add-on prices of cart lines when `menu_item_updated` arrives. Labels in `i18n.js` (en / my).

### Not changed
- Recorded money: open bills, paid orders, receipts, kitchen slips, Order History and reports keep the price each add-on was sold at (locked in by tests).
- Add-ons that are not linked still take their price from the waiter's screen (as before).

### Rules (confirmed by the owner)
- Name stays the add-on's own; price = target's `price` only (not discount / takeaway / tax); no option ids (matching by `group` + `name`); defaults D1-D10 in the spec.

### Spec
- `specs/feature-linked-addons/`; `api-reference.md`, `database-schema.md`, `feature-priced-modifiers/requirements.md`.

### Tests
- `tests/test_linked_addons.py` (37). Suite: 664 passed. 22 deliberate code breakages, all caught (a 23rd, in a fallback branch that valid data never reaches, is equivalent).
- Not verified: the admin form and waiter screen in a real browser (helper functions checked with Node only).

## 2026-11-19 — Snapshot-first item names (renaming a menu item no longer rewrites old bills)

### Summary
Prices were already stored per sold line, but several screens showed the **live** menu name instead of the name the line was sold under. After renaming a dish, old bills, the Order History detail and the order lists showed the new name. They now keep the sold-as name, like the receipt, kitchen slip and reports already did.

### Fixed
- `menu_item_name` of an order line is now `menu_item_name_at_sale` first; the live name is used only for legacy lines without one, then `[Deleted Item]` (`GET /orders/`, `/orders/active-by-table/{id}`, `/orders/tables`, `GET /orders/{id}/details`, create / submit / checkout responses, daily Order History). One shared helper (`services/item_names.py`) is used by both code paths.
- Start-up backfill of empty `menu_item_name_at_sale` / `category_name_at_sale` on legacy order lines (from the live name; never overwrites a stored value, never touches `unit_price_at_sale`, never uses the `__system_archived__` category). A legacy line's name is frozen at the first start after upgrading.

### Behaviour to know
- On an **open** bill, lines already ordered keep the old name after a rename and lines added afterwards carry the new name (same as prices).

### Found, not changed
- `GET /api/orders/tables` answers `500` (`TypeError`, sorting `None` against an int) when an open takeaway order and an open table order exist at the same time. No screen calls it today. Separate fix.
- The "promoted sales" report still filters on the live `is_promoted` flag.

### Spec
- `specs/feature-snapshot-first-names/`; `api-reference.md`, `database-schema.md`.

### Tests
- `tests/test_snapshot_first_names.py` (17). Suite: all passing, +17 tests (506 passed on a clean checkout of this commit; measured). 8 deliberate code breakages, all caught.

## 2026-11-19 — Safe menu price changes (no system error when prices change)

### Summary
Checked what happens when the owner raises or lowers a price. The design was already right: every sold line keeps its own price, so open bills, paid orders and reports do not change. But editing the menu could cause a `500` or save a value that broke ordering later. Fixed.

### Already correct (now locked in by tests)
- An open bill keeps the old price on lines already ordered; items added afterwards use the new price (one bill can show both). Paid orders, Order History and the reports never change when a price changes.

### Fixed
- `PUT /api/menu-items/{id}` with `null` for `price`, `name`, `category_id`, `discount_type`, `discount_value`, `tax_type`, `tax_value`, `is_available`, `is_promoted` or `modifiers_config` answered `500`; now `422`.
- `price` / `discount_value` = `NaN` answered `500`; `Infinity` was **saved** and then the answer crashed, after which ordering that item failed. Now `422`.
- Negative price, takeaway price or discount, a percentage discount above 100 %, and a price of 1e308 were saved and later broke ordering (`500`) or the totals. Now `422`.
- Blank menu item name and a `category_id` that does not exist (the item vanished from the menu) were accepted. Now `422` / `404`.
- Ordering: a modifier price of `NaN` / `Infinity` sent by a device answered `500`, and with `Infinity` an order with an infinite total was **created**. Now `422`.
- Ordering an item whose stored data is bad (negative price, infinite price or tax, negative modifier total) answered `500`. Now `400` naming the item, and nothing is saved.
- A percentage item discount above 100 % could push a line below 0 (`500`). It is now capped at the price, like a fixed discount.

### Rules (assistant's choices, easy to change)
- Money fields of a menu item: finite, `0 … 1,000,000,000`. Price `0` stays allowed. Percentages (discount, tax) `≤ 100`. Modifier option prices may be negative but finite and within the same limit.

### Spec
- `specs/feature-menu-price-safety/` (requirements, plan, validation); `api-reference.md`.

### Tests
- `tests/test_menu_price_safety.py` (86). Suite: 610 passed. 18 of 20 deliberate breakages caught; the other 2 are duplicate guards.

### Review checklist
- Security / roles: only `root` / `admin` edit the menu (unchanged).
- Money: recorded lines and totals never recomputed from the live price; a refused order writes nothing.
- Not changed: a waiter's modifier prices still come from the waiter's screen (kept current by `menu_item_updated`); the server does not re-check them against the menu.

## 2026-11-19 — Daily voucher number (restarts at 1 every day)

### Summary
Every paid order now gets a voucher number made of the date and a number that starts at `0001` each day, for example `20261119-0001`. The receipt prints it instead of the old `Order: #<id>`.

### Added
- `orders.voucher_date` (`YYYYMMDD`) and `orders.voucher_seq`, added to existing databases at startup, with a unique index so two orders can never share a number. The API field `voucher_no` is built from the two parts (never stored separately).
- The number is given **at checkout**, in the same transaction as the payment. The day changes at **midnight Myanmar time (UTC+06:30)**. Unpaid and cancelled orders get none, so cancelled orders leave no gaps.
- If two checkouts take the same number at the same moment the checkout is retried with the next number (the payment is never lost); after 5 failed attempts it answers `503` and the order stays unpaid.
- `voucher_no` in the checkout answer, `GET /api/orders/{id}/details`, `PUT /api/orders/{id}/items/{item_id}/status`, order lists, and `GET /api/orders/daily-history`. `null` before payment and on orders from before this change. Clients cannot send it.
- Receipt: first line `Voucher: 20261119-0001` (`Order: #<id>` is still printed for an order that has none). Order History (list, detail window) shows the voucher; the Excel export has a new `Voucher No` column after `Order ID`.
- After `scripts/clear_sales.py` the next voucher of the day is `-0001` again (the next number is read from the orders that exist).

### Not changed
- `orders.id` stays the internal key. Kitchen slips, the Print Jobs page and waiter screens still show `#<id>` (a kitchen slip is printed before payment, when no voucher exists yet).
- Old orders are not renumbered.

### Known limits
- Order History and the sales reports still cut the day at UTC midnight (06:30 Myanmar time). Between 00:00 and 06:30 Myanmar time a voucher carries the new Myanmar date while the order still shows under the previous UTC day. Moving the reports to Myanmar days is a separate change.
- The voucher date is the date of checkout; Order History groups by the date the order was opened.

### Spec
- `specs/feature-voucher-number/` (requirements, plan, validation); `api-reference.md`, `database-schema.md`.

### Tests
- `tests/test_voucher_number.py` (35): Myanmar day boundary (incl. year end, leap day), format, sequence per day, new day restarts, cancelled / failed checkout leave no gap, repeated checkout keeps the voucher, client cannot choose it, roles, clash retried once, 503 after 5 clashes, unique index, receipt text, queued receipt, history, Excel export, clear-sales restart, startup upgrade of an old database. 16 deliberate code breakages were all caught.
- Existing receipt, history-export and kitchen-slip tests updated for the `Voucher:` line / new column. Suite: 524 passed.

### Review checklist
- Security / roles: no new endpoint; checkout roles unchanged (waiter `403`, anonymous `401`); the number is chosen by the server only.
- Money: totals and payment rules untouched; the voucher is saved with the payment in one transaction.
- Edge cases: day boundary, race, repeated checkout, sales cleared, old orders, old queued receipts without a voucher.
- Not verified: a real receipt printer; behaviour of two real devices paying in the same second (simulated in tests).

## 2026-11-18 — Waiter: "Mark as Served" failed after a few taps

### Fixed
- Waiter **Table Details**: after a few **Mark as Served** / **Undo** taps the next tap showed *Load Failed*. The server answered the item update with a body that had **no item `id`**; the panel redrew its list from that answer, so every button pointed at item `undefined` until a second refresh fixed it. On a slow Wi-Fi (or when the refresh arrived first) the broken buttons stayed. Reproduced in the browser: the redraw with `id=undefined` happens on every tap, and is corrected only ~3 ms later on a local machine.

### Changed
- `PUT /api/orders/{order_id}/items/{item_id}/status` now returns `OrderDetailsResponse` (the same body as `GET /api/orders/{order_id}/details`: items with `id` and `menu_item_id`, plus `breakdown_*`). Before it returned `OrderResponseDetail`. All old top-level fields the pages read (`status`, `total_amount`, `items[].item_status`, …) are still there. Shared builder `_build_order_details_response`.

- `scripts/clear_sales.py`: when run without the project's virtual environment it now prints which package is missing and the exact command to use (`venv\Scripts\python.exe scripts\clear_sales.py` / `venv/bin/python scripts/clear_sales.py`) instead of a Python traceback. README *Clear sales only* says to activate the virtual environment first.

### Spec
- `specs/api-reference.md`: response type of the item status endpoint.

### Tests
- `tests/test_item_status_response.py` (15): ids in the answer, answer equals `GET /details`, six serves and six undos in a row, totals unchanged by serving, cancel keeps ids and lowers the total, last-item cancel cancels the order, roles (waiter/cashier/admin/root allowed, no login refused), invalid status `422`, unknown ids `404`. Putting the old response back makes 14 of them fail.

### Review checklist
- Security / roles: unchanged (`POS_ORDER_ROLES`); no new data exposed (same fields as `/details`, which the same roles already read).
- Money: serving / undo never touch `total_amount`; cancel recalculates as before; a paid order's total is still not recalculated.
- Edge cases: last item cancelled → `status = cancelled` and the panel closes; invalid status `422`; unknown order / item `404`.
- Not covered: the `table-dashboard.js` page ignores the answer (it reloads details), so it is unaffected; no automated browser test exists.

## 2026-11-18 — KPay / MMQR payments, Cash / KPay / MMQR per cashier, clear-sales script

### Summary
Checkout now records **Cash**, **KPay** and **MMQR** separately (a split can combine all three), and the admin dashboard shows how much each cashier took by each method. A new script clears sales only and keeps staff, menu, tables and printers.

### Changed (breaking for old clients)
- Checkout no longer accepts `payment_method = mobile_money` or `mobile_money_amount` above 0 (`422`). A counter page left open from before the update must be reloaded; its **Mobile** button is refused, nothing is recorded wrongly.

### Added
- `orders.kpay_amount`, `orders.mmqr_amount`; added to existing databases at startup. `mobile_money_amount` is kept as their sum.
- `PUT /api/orders/{id}/checkout`: `payment_method` `cash | kpay | mmqr | split`; `kpay_amount`, `mmqr_amount`. Response and order details carry both amounts.
- `GET /api/reports/sales/by-cashier`: `cash`, `kpay`, `mmqr`, `mobile_unspecified` per cashier.
- `GET /api/analytics/sales-breakdown`: `kpay`, `mmqr`. `GET /api/reports/sales`: `total_kpay`, `total_mmqr`. `GET /api/orders/daily-history`: payment parts per order.
- Counter: **Cash / KPay / MMQR / Split** buttons; split has KPay, MMQR and Cash inputs. Dashboard → Staff Performance: **Cash / KPay / MMQR by cashier** table. Overview and Sales Reports show KPay and MMQR. Order History shows the method and split parts.
- Receipt: `Payment: KPay`, `MMQR`, or `Split (Cash + KPay + MMQR)` with a line per mobile method.
- `scripts/clear_sales.py` (README: *Clear sales only*). Shows counts by default; `--yes` backs up the SQLite file, then deletes orders, order lines and print jobs and frees every table. `*.db.backup-*` is git-ignored.

### Behaviour
- A cashier in the report is the **login account** that confirmed the payment, not the free-text Cashier Name. Each cashier needs their own PIN.
- KPay + MMQR may not be more than the bill (`400`); cash covers the rest and only extra cash gives change. The server never guesses or adjusts a mobile amount.
- Paying with KPay or MMQR alone: the amount must **equal** the bill (`400` if more or less). A transfer never produces change; only cash can be more than the bill. The counter fills the bill amount in when KPay / MMQR is chosen and keeps **Confirm Payment** disabled until it is exact.
- Every checkout satisfies `cash_amount + kpay_amount + mmqr_amount == total_amount`.
- Mobile money recorded before this change is shown as **Mobile (unspecified)** (only when there is some). It is never counted as KPay or MMQR and never dropped from a total.
- The three reports use the same SQL expressions (`services/payment_totals.py`).

### Fixed
- Checkout refused `NaN` / `Infinity` in `amount_tendered`, `cash_amount`, `kpay_amount`, `mmqr_amount`, `mobile_money_amount` and `discount_value` (`422`). Before, `NaN` marked the order paid with no money counted, `Infinity` marked it paid and then failed to answer (and could break every report summing it), and an infinite discount made the bill 0. Present before this change for the first three fields.
- A `422` caused by `NaN` / `Infinity` is now answered as a normal `422` (`services/validation_errors.py`, same shape as before) instead of a `500`.
- `scripts/clear_sales.py` stops with a message when the database file does not exist (for example run from the wrong folder) instead of creating an empty `pos.db` and reporting 0 orders.
- Counter page: dashboard figures stayed at 0 after the page opened until the Dashboard tab was clicked (variables used before their declaration; present before this change).

### Spec
- `specs/feature-payment-kpay-mmqr/` (requirements, plan, validation); `api-reference.md`, `database-schema.md`; notes in the split-payment and payment-method-analytics specs; final review items 9 and 16.

### Tests
- `tests/test_payment_kpay_mmqr.py` (82), `tests/test_clear_sales.py` (18); four existing test files now pay with KPay/MMQR instead of `mobile_money`. Suite: 474 passed.

### Review checklist
- Security: no new endpoint. Amounts are bounded by the schema (≥ 0, finite) and by the bill. The clear script runs only from the server's command line, deletes nothing without `--yes`, and refuses to delete when it cannot write a backup. The backup contains sales and password hashes and is git-ignored.
- Roles: checkout stays root / admin / cashier (`403` waiter, account). The per-cashier report stays root / admin / account (`403` cashier, waiter). A cashier's own dashboard shows only their own checkouts.
- Money: invariant above tested for every method, split, discount and cents; rejected checkouts leave the order unpaid; report rows add up to the cashier's total.
- Edge cases: KPay/MMQR above, below and exactly the bill (also after a discount), cash still allowed above the bill, split without cash, amounts for a single method, zero amounts, KPay + MMQR equal to the bill, overpaying with cash, old mobile-money rows, existing database without the columns, clearing an already empty database, failure in the middle of clearing.
- Not verified: phone/tablet layout, Burmese labels (new labels are English), a real receipt printer, the script on Windows. The Account page still shows cashier totals without the split.

## 2026-11-16 — Kitchen slip copies with a large COPY banner

### Summary
With **All items on one slip**, admins can print each kitchen slip 1, 2 or 3 times. Every copy starts with a large `COPY 1 / 3` banner (white on a black bar across the paper) so staff can tell the copies apart and see how many there should be.

### Added
- `kitchen_printer_settings.kitchen_slip_copies` (1–3, default 1); added to existing databases at startup.
- `GET/PUT /api/admin/kitchen-printers`: `kitchen_slip_copies` (optional on PUT; omitted keeps the stored value; anything but an integer 1–3 → `422`).
- Menu Management → Kitchen Printer Settings: **Copies** select next to **Kitchen slip**; greyed out while **One slip per item** is selected.

### Behaviour
- Copies apply only to combined kitchen slips. Single-item slips and receipts are always printed once.
- Each copy is its own print job, sent one after another to the same printer. A copy that fails is listed as `… (copy 2/3)` under **Print failed** and Retry prints only that copy.
- With 1 copy nothing changes: no banner, same jobs, same bytes sent to the printer.
- Banner by print mode: image mode draws a black bar with large white text; text mode uses ESC/POS centre + double size + reverse; the file backend writes a framed three-line block.
- The setting is read when the order is submitted, like the slip mode.

### Spec
- `specs/feature-kitchen-slip-mode/` (FR-SM7, plan step 9, validation), `api-reference.md`, `database-schema.md`.

### Tests
- `tests/test_kitchen_slip_mode.py` (52). Suite: 374 passed.

### Review checklist
- Security: no new endpoint; the value is bounded by the schema (1–3, strict integer), so a request cannot make the printer produce an arbitrary number of slips. A bad value already in the database behaves as 1.
- Roles: only root/admin can change it (`403` waiter/cashier/account — tested).
- Money/state: copies add print jobs only; order lines and totals are unchanged (tested).
- Edge cases: 1 copy, `per_item` with copies stored, food + drinks order, one copy failing, printer lost between copies, line cancelled before retry, older client that does not send the field, existing database without the column.
- Not verified: a real thermal printer. In text mode the banner needs ESC/POS reverse printing (`GS B`); a printer without it shows the banner large but black on white.

## 2026-11-16 — Kitchen slip mode: one slip per item or all items on one slip

### Summary
Admins can choose how an order is printed for the kitchen: **One slip per item** (default, as before) or **All items on one slip**. In combined mode each submit prints one slip per printer route, so a mixed order still gives one food slip and one drinks slip.

### Added
- `kitchen_printer_settings.kitchen_slip_mode` (`per_item` | `combined`); added to existing databases at startup.
- `GET/PUT /api/admin/kitchen-printers`: `kitchen_slip_mode` (optional on PUT; omitted keeps the stored value).
- Menu Management → Kitchen Printer Settings: **Kitchen slip** select.

### Behaviour
- The mode is read when the order is submitted. A slip already recorded keeps its form on **Retry**.
- A combined slip sent late or retried leaves out lines cancelled since; if all are cancelled it is not printed and disappears from the **Print failed** list.
- Totals, order lines, batch numbers and `OrderSubmitResponse` are the same in both modes.

### Fixed (tests)
- `tests/conftest.py` now points the app database at a throwaway file before anything imports `database`. `test_order_history_page_routes` boots the real app lifespan, which was running `create_all` / `ALTER TABLE` / startup clean-up on the developer's real `pos.db` on every test run.
- `tests/conftest.py` also sends the file print backend to a throwaway folder, so test slips are no longer appended to the local `*_printer_output.txt` files.

### Spec
- `specs/feature-kitchen-slip-mode/` (requirements, plan, validation); kitchen-printing, print-queue, `api-reference.md`, `database-schema.md`.

### Tests
- `tests/test_kitchen_slip_mode.py` (28). Suite: 350 passed.
- Includes real-socket tests with one listener per printer: in both modes kitchen slips reach only the kitchen printer and the receipt only the cashier printer (LAN and Windows cashier queue).

### Review checklist
- Security: no new endpoint; the setting is validated by the schema (`422` for anything but the two values).
- Roles: only root/admin can read or change it (`401` anonymous, `403` waiter/cashier/account — tested).
- Money/state: printing form never changes totals or lines (tested by submitting the same order in both modes).
- Edge cases: mixed food/drinks, second batch, takeaway, cancelled lines, all lines cancelled, cancelled order, mode changed between failure and retry, unknown stored value, older client that does not send the field, existing database without the column.
- Not verified: a real thermal printer (paper length / cut of a long combined slip), Myanmar-language label for the new control (the form is English-only like the rest of that section).

## 2026-11-16 — Print queue + retry

### Summary
Slips are no longer sent inside the request. Every kitchen slip and receipt is stored as a `print_jobs` row and sent by a background queue: one queue per physical printer, one slip at a time, with a pause between slips (`PRINT_QUEUE_DELAY_SECONDS`, default 1 s). Before, one order with five lines opened five connections to the same printer at once, which is what makes LAN thermal printers drop tickets. A slip that fails is recorded with its reason and can be reprinted.

### Behaviour changes
- `POST /api/orders/submit` and checkout return as soon as the slips are queued. Response shapes are unchanged.
- `warning` on submit still reports a printer that is already offline. A slip that fails later is no longer in `warning`; it becomes `print_status='failed'`, is broadcast as WebSocket `print_job_updated`, and shows in the new **Print failed (N)** button.
- `warning` on checkout is now set only when the receipt could not be queued. This replaces the `Receipt was not printed: <reason>` behaviour from the entry below: the reason is now on the failed print job and in the **Print failed** list.
- Slips still `pending` when the server stops are marked `failed` at the next start (not printed automatically).
- A kitchen slip whose line or order was cancelled while it waited is not printed.

### Added
- Table `print_jobs` (`print_status`: `pending` | `printed` | `failed`, `error_message`, `attempts`). Created automatically at startup.
- `POST /api/orders/{order_id}/retry-print`, `GET /api/orders/{order_id}/print-jobs`, `GET /api/print-jobs/failed`.
- `services/printing/print_queue.py`, `services/printing/print_jobs.py`; queue started/stopped in the FastAPI lifespan.
- Waiter + counter: **Print failed (N)** button, list by order, **Retry** (`static/print-jobs.js`).
- `.env.example`: `PRINT_QUEUE_DELAY_SECONDS`.

### Changed
- Print Test goes through the same per-printer queue.
- LAN "no address" error now points to Menu Management > Printers instead of only `.env` variables.
- `scripts/seed_root.py`: `seed_root(db=...)` creates tables in that session's database (a test was creating them in the real `pos.db`).

### Spec
- `specs/feature-print-queue/` (requirements, plan, validation)
- `specs/feature-cashier-receipt-printing/`, `specs/feature-kitchen-printing/`, `specs/api-reference.md`, `specs/database-schema.md`, `specs/tech-stack.md`

### Tests
- `tests/test_print_queue.py` (36). Suite: 322 passed.

### Review checklist
- Security: new endpoints require a token; retry takes no body; job payloads (receipt amounts) are never returned, only labels. UI writes job text with `textContent`.
- Roles: retry / lists = root, admin, cashier, waiter (`account` → 403). A waiter cannot see or reprint receipts.
- Money/state: no change to totals, payment or order status; printing can never roll them back (tested).
- Data consistency: retry only flips rows that are still `failed`, so a double click cannot print twice.
- Edge cases: printer offline, failure mid-queue, cancelled line/order, unknown order, server restart, queue not running, slips cannot be queued.
- Not verified: real thermal printer and Windows spooler, phone layout, Myanmar UI strings (see `validation.md`).

## 2026-11-16 — Print path review: wrong-printer test slip, hidden receipt errors, false online/offline

### Summary
Review of every print path (kitchen/bar tickets, cashier receipt, Print Test, Check, print log). Kitchen/bar routing and receipt printing behaved correctly end to end over real TCP sockets; the fixes below are for diagnostics that could mislead.

### Fixed
- **Print Test could print on a different printer.** Under Windows print mode, a kitchen/bar/other row with no host reported `target=file` while the slip went to another row's (or the `.env`) LAN host for that route. It now fails with `502` and says the row needs IP:port.
- **Checkout hid why the receipt did not print.** `warning` was always "Receipt printer offline or unreachable"; it is now `Receipt was not printed: <reason>`, the Counter toast shows that reason, and it is written to `logs/printing/print.log`.
- **Windows Check could say "ready" for an unplugged USB printer.** The probe now also reads the queue's work-offline attribute, and reports the port and number of waiting jobs.
- **Admin Check now warned about inactive printers.** Aggregate health lists active printers only.
- **Print log lines could repeat.** When the project folder was reached through a symlink/junction, each print attached another log handler.
- **Tests wrote into the real `logs/printing/print.log`.** Test runs now log to a temp folder.
- **`.env.example` shipped live placeholder printer IPs** (`192.168.1.101-103`). They are now commented out. An existing `.env` copied from the old example still has them and must be edited by hand.

### Spec
- `specs/feature-printer-test-print/` FR-TP3, FR-TP5
- `specs/feature-cashier-receipt-printing/` FR-CR3, FR-CR5
- `specs/api-reference.md`

### Tests
- `tests/test_printer_test_print.py`, `tests/test_printer_named_health.py`, `tests/test_cashier_receipt_printing.py`, `tests/test_windows_cashier_printing.py`, `tests/conftest.py`

### Review checklist
- Security: no new endpoints; error text returned to the client is the exception message already shown by Print Test (no secrets, no stack traces).
- Roles: unchanged (`test-print` / per-printer health admin+root; checkout roles unchanged).
- Money/state: checkout still returns `200` + `paid` when printing fails; no change to totals or order transitions.
- Edge cases: row without host, missing Windows queue name, inactive printers, unreachable LAN host, non-Windows host.
- Not verified: real Windows spooler and physical printers (logic covered with a fake spooler and local TCP listeners only).

## 2026-11-16 — Printer Check (online) + clearer print errors

### Summary
Each Printers row has **Check** (Windows queue / LAN reachability, no paper) plus clearer **Print Test** failure dialogs (`message` + hint to `logs/printing/print.log`). Admin **Check now** also lists every named printer status.

### Spec
- `specs/feature-printer-test-print/` FR-TP5

## 2026-11-16 — Stop re-seeding default printers after admin delete-all

### Summary
Deleting every printer no longer brings back Default Cashier / Kitchen / Bar on the next list. First-install seed still runs once; `KitchenPrinterSettings.default_printers_seeded` records that. (Three defaults appear when `.env` has a drinks LAN host.)

### Spec
- `specs/feature-dynamic-printer-management/`

## 2026-11-16 — Admin Print Test on Printers table

### Summary
Each Printers row has **Print Test** (admin/root). `POST /api/printers/{id}/test-print` sends a short TEST PRINT slip to that printer (Windows queue / LAN host / file) and returns success or a clear `502` error. Does not replace LAN health **Check now**.

### Spec
- `specs/feature-printer-test-print/`

## 2026-11-16 — Restore full Windows printer queue list for cashier setup

### Summary
Admin cashier printer setup again lists **all** Windows queues (USB / Bluetooth / local / network), not a partial network-only set. Enumeration now merges separate LOCAL + CONNECTIONS (+ NETWORK) passes across info levels. Opening Add/Edit Printer refreshes print mode from the API so the Windows queue field is not stuck behind LAN-only fields. Queue picker is a datalist input (select or type exact name).

### Spec
- `specs/feature-windows-cashier-printing/` FR-W3

## 2026-11-15 — seed_root creates tables before inserting root

### Summary
`scripts/seed_root.py` now runs `Base.metadata.create_all` first so a fresh Windows/local install can seed root without a separate “create tables” command (fixes `no such table: users`).

## 2026-11-15 — Kitchen: one slip per line item (modifiers stay under parent)

### Summary
Order submit prints **one kitchen ticket per cart line** again (not one combined slip per printer route). Submenu/modifiers (e.g. မုန့်ဟင်းခါး + ပဲကြော်) still print on that same slip under the parent item (Pattern A). No prices on kitchen tickets. No DB schema change.

### Spec
- `specs/feature-kitchen-printing/` FR-2, FR-6

## 2026-11-15 — Review UI/print polish (#29, #24, #23/#30, #18, #27)

### Summary
Waiter order-details modal shows takeaway / modifiers / notes. Cashier checkout groups lines by batch, shows notes, and uses pre-tax line amounts. Printed receipts include notes and pre-tax line amounts (footer tax unchanged). Selecting an available table no longer jumps the view down to the cart.

### Spec
- `specs/POS_final_review_2026-11-09.md`
- `specs/feature-cashier-receipt-printing/` FR-CR8

## 2026-11-15 — Cashier file-backend receipt without printer host

### Summary
With print backend `file` (no physical printer), selecting a cashier printer that has no `host` no longer aborts receipt dispatch. Receipt text still appends to `cashier_printer_output.txt` for local testing.

### Spec
- `specs/feature-cashier-receipt-printing/` FR-CR7

## 2026-11-15 — Cashier receipt money footer fix

### Summary
Receipt (and checkout pane) now show Subtotal = base + modifiers, Discount = item (+ order) discount, Tax separate, Grand = payable — so Tax is no longer double-implied against a tax-inclusive “Subtotal”.

### Spec
- `specs/feature-cashier-receipt-printing/` FR-CR8

## 2026-11-15 — Cashier receipt text archive

### Summary
Cashier receipts always append to `cashier_printer_output.txt` (same output dir as kitchen), including when printing via Windows queue or LAN — not only when backend is `file`.

### Spec
- `specs/feature-cashier-receipt-printing/` FR-CR7

## 2026-11-15 — Daily Order History + Excel export

### Summary
Admin and Cashier can open `/order-history` (also `/admin/sales-history`, `/cashier/history`), filter paid orders by day, view line details (modifiers + takeaway), and download a structured `.xlsx` via `openpyxl`.

### Also documented (completed work in this release window)
- Menu schema supports priced add-ons via JSON `modifiers_config` (`ModifierGroup` / options; not separate DB tables).
- Line-level `is_takeaway` for dine-in vs takeaway pricing and print tags.
- Waiter POS UI: modifier selection + per-line takeaway toggle.
- Kitchen print: combined batch slips with modifiers and `(ပါဆယ်)` on takeaway lines.
- Daily Order History view + Excel export (this section).

### Spec
- `specs/feature-daily-order-history/`

### API / UI
- `GET /api/orders/daily-history?date=YYYY-MM-DD`
- `GET /api/orders/daily-history/export?date=YYYY-MM-DD`
- `static/order-history.html` + nav **Order History** for root/admin/cashier
- Dependency: `openpyxl`

## 2026-11-15 — Legacy-safe menu `modifiers_config`

### Summary
Older databases without / with NULL `modifiers_config` no longer break Admin menu list or add. Startup still adds the column and now backfills NULLs to `[]`; API schemas coerce null/flat legacy shapes into the current group format.

## 2026-11-14 — Line-level takeaway markers on kitchen + receipt

### Summary
When Waiter ticks 🛍️ Takeaway on a cart line (including dine-in table orders), kitchen slips and cashier receipts mark that line as `{qty}x {name} (ပါဆယ်)` (option B). Cashier checkout UI shows a takeaway badge. Pricing still uses `takeaway_price` via existing dual-pricing rules.

### Spec
- `specs/feature-menu-pricing/` FR-P6
- `specs/feature-kitchen-printing/` FR-6
- `specs/feature-cashier-receipt-printing/` FR-CR6

## 2026-11-14 — Retire menu item photos from UI

### Summary
Admin no longer uploads or edits menu images; Waiter menu cards are text-only. Backend `image_url` stays nullable for API/DB compatibility. Saving a menu item from Admin clears `image_url` so old photos stop appearing. Order totals, kitchen print, and cashier flows are unchanged.

## 2026-11-14 — Kitchen print miss: stop silent file fallback

### Summary
Confirmed that under `windows_printer` with no kitchen/bar LAN host, tickets were written to a local file and treated as success (kitchen got no paper). Now that case returns a submit `warning`, logs an error, and health marks the route offline. Dine-in and takeaway both verified to dispatch kitchen slips. Regression test updated to expect file backup + `RuntimeError` (no silent OK).

## 2026-11-13 — Kitchen printer online check (warn only)

### Summary
`GET /api/printers/health` probes food/drinks LAN reachability. Waiter badge + Admin status panel show online/offline. Order submit still succeeds when offline and returns `warning` (file/dev backend is treated as OK).

## 2026-11-13 — Combined kitchen batch slip (no prices)

### Summary
Order submit prints one kitchen slip per printer route for the whole batch (items + modifiers + notes), instead of one slip per line. Prices stay off kitchen tickets.

## 2026-11-13 — Priced modifiers (sub-menu toppings)

### Summary
Any menu item can have priced modifier groups (Admin UI). Waiters pick toppings with quantity; line totals include `price × qty`. Kitchen tickets use Pattern A (toppings under the parent item). Cashier checkout and receipts show modifiers. Instruction tags remain note-only.

### Spec
- `specs/feature-priced-modifiers/`

## 2026-11-12 — Myanmar vowel shaping for image print

### Summary
Image-mode tickets shape Myanmar text with Pillow RAQM when available, otherwise HarfBuzz + FreeType, so left-side vowels like `ေ` print in visual order. Adds `uharfbuzz` / `freetype-py` and shaping regression tests.

## 2026-11-12 — Printer diagnostic log file

### Summary
Every print job writes diagnostics to `logs/printing/print.log` (backend, render mode, target queue/host, Myanmar font resolution, success/failure). Console logging remains; `logs/` is gitignored.

## 2026-11-11 — Prefer Pyidaungsu for Myanmar print fonts

### Summary
Image-mode kitchen tickets and cashier receipts now prefer `Pyidaungsu.ttf` over NotoSansMyanmar. Bundled MCF Pyidaungsu 2.5.3 Regular under `assets/fonts/` (`Pyidaungsu.ttf` + versioned copy + NOTICE).

## 2026-11-05 — Windows cashier receipt printing

### Summary
Cashier receipts can print to a Windows installed USB/Bluetooth queue (`windows_printer` backend) selected in Admin UI. Under that mode kitchen/bar still use LAN when a host is configured; otherwise file. Spooler errors are mapped to actionable messages. LAN (`escpos_network`) and file backends unchanged.

### Spec
- `specs/feature-windows-cashier-printing/`

### Backend / Frontend / Tests
- `Printer.windows_printer_name`; `GET /api/admin/windows-printers`; `escpos_windows` RAW send
- Counter Admin: Windows print mode + queue dropdown
- `tests/test_windows_cashier_printing.py`; `requirements-windows.txt` (`pywin32`)

## 2026-10-05 — Docker Desktop packaging

### Summary
Linux image and Compose file for Windows Docker Desktop. SQLite and file-backend tickets use named volumes. First boot creates tables and seeds root from `ROOT_USERNAME` / `ROOT_PASSWORD`.

### Files
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `entrypoint.sh`

## 2026-07-13 — Cashier name on checkout receipt

### Summary
Checkout stores an optional free-text `cashier_name` and prints `Cashier: …` on the receipt. Counter UI persists the name in `localStorage` (`currentCashierName`).

### Spec
- `specs/feature-cashier-name-on-receipt/`

### Backend / Frontend / Tests
- `Order.cashier_name`; checkout request/response; receipt builder
- Cashier pane name input + checkout payload
- `tests/test_cashier_name_receipt.py`

## 2026-07-13 — Revenue breakdown replaces Include Tax toggle

### Summary
Sales Reports (and Overview) show Net Sales, Tax Collected, and Gross Sales together instead of hiding one view behind a toggle. Cash/Mobile remain visible as payment received.

### Frontend / Spec
- `static/counter.html` / `counter.js` — remove Include Tax toggles; bind `subtotal_revenue`, `total_tax`, `grand_total_revenue`
- Specs + CHANGELOG updated

## 2026-07-13 — Overview Include Tax toggle

### Summary
Today's Overview can switch Gross (with tax) vs Net (without tax) revenue via Include Tax. Cash/Mobile stay as received amounts.

### Backend / Frontend / Spec
- `summary/today` + `sales-breakdown` return subtotal / tax / grand fields
- Overview toggle in `counter.html` / `counter.js`
- Specs + CHANGELOG for sales period reports

## 2026-07-13 — Sales period reports (tax inclusive / exclusive)

### Summary
Admins can load Daily or Monthly paid-order aggregates via `GET /api/reports/sales`, and the Dashboard **Sales Reports** tab toggles Gross (with tax) vs Net (without tax) revenue without re-fetching.

### Spec
- `specs/feature-sales-period-reports/`
- Updated `specs/api-reference.md`, account reports matrix

### Backend
- `SalesPeriodReportResponse`; `GET /api/reports/sales?period=&date=`
- Aggregates orders, subtotal (tax-exclusive), tax, grand total, cash, mobile

### Frontend
- Dashboard sub-tab **Sales Reports** with period picker and Include Tax toggle

### Tests
- `tests/test_sales_period_reports.py`

## 2026-07-13 — E2E release audit tests

### Summary
Added integration coverage for waiter multi-qty submit + table occupied, mixed food/drinks → kitchen/bar hosts, split change due 5000/3000/3000, and admin printer create/404-delete.

### Tests
- `tests/test_e2e_release_audit.py` (4 cases); full suite **204 passed**

## 2026-07-13 — Split payment Change Due display

### Summary
Split checkout shows a highlighted **Change Due** when cash is over-tendered; receipts print Paid via Mobile, Tendered Cash, and Change Due. Mobile input still auto-fills exact cash remaining; cash can be raised for change.

### Frontend / Backend / Tests
- `static/counter.html` / `counter.js` — Change Due box + autofill rules
- `services/printing/receipt.py` — split receipt lines
- `tests/test_split_payment.py` — 5000 / 3000 / 3000 → change 1000

## 2026-07-13 — Split payment checkout

### Summary
Cashiers can split one bill across Cash and Mobile Money. Orders store `cash_amount` and `mobile_money_amount` for accurate reports; single-method checkout remains unchanged.

### Spec
- `specs/feature-split-payment/`
- Updated payment analytics, api-reference, database-schema

### Backend
- `Order.cash_amount` / `mobile_money_amount`; `payment_method` may be `split`
- Checkout validates sum ≥ total; change from excess cash
- Analytics sums applied amounts

### Frontend
- Check Out: Cash / Mobile / Split; split inputs with auto-fill remainder

### Tests
- `tests/test_split_payment.py`

## 2026-07-13 — Dynamic printer management (unified Printer CRUD)

### Summary
Admins create/edit/delete unlimited named printers with roles (`cashier`, `kitchen`, `bar`, `other`). Fresh installs seed only Default Cashier + Default Kitchen. Category tickets map `food`→kitchen and `drinks`→bar (fallback kitchen). Fixed host cards removed from Menu Management.

### Spec
- `specs/feature-dynamic-printer-management/`
- Updated tech-stack, api-reference, database-schema

### Backend
- `models.Printer` replaces `CashierPrinter`
- `GET/POST/PUT/DELETE /api/printers`
- `seed_default_printers` + `scripts/seed_root.py` seed
- Kitchen-printers API = print mode only

### Frontend
- Printer table + Add/Edit modal in `counter.html` Menu Management
- Cashier dropdown still loads `GET /api/printers?role=cashier` on refresh

### Tests
- CRUD + seed + drinks→bar fallback coverage

## 2026-07-13 — Terminal-based cashier printer selection

### Summary
Cashiers pick a dedicated receipt printer per terminal. Selection persists in `localStorage` and is sent as checkout `printer_id`. Backend resolves named `cashier_printers` (fallback: first active / legacy `cashier` route).

### Spec
- `specs/feature-cashier-receipt-printing/` — multi-cashier architecture
- `specs/api-reference.md`, `tech-stack.md`, `database-schema.md`

### Backend
- `CashierPrinter` model + seed from legacy cashier route
- `OrderCheckoutRequest.printer_id`
- `GET /api/printers?role=cashier`, `GET/PUT /api/admin/cashier-printers`
- Checkout print target by `printer_id`

### Frontend
- `#cashier-printer-select` + `localStorage.selectedCashierPrinterId`

### Tests
- `tests/test_cashier_receipt_printing.py` — list API, `printer_id` targeting, invalid id

## 2026-07-13 — Fix ghost table named "None" on startup

### Summary
Startup legacy backfill no longer turns walk-in takeaways (`table_id`/`table_number` null) into a physical table named `"None"`. Existing ghost tables are removed and unlinked.

### Backend / Tests
- `services/legacy_table_backfill.py` — safe backfill + ghost cleanup
- `main.py` lifespan uses the repair helper
- `tests/test_legacy_table_backfill.py`

## 2026-07-13 — Waiter pane color swap (Menu rose / Floor green)

### Summary
Waiter two-pane tints: left Menu+Cart = subtle rose/red; right Tables = subtle emerald/green. Active-order modal + cart qty isolation unchanged.

### Spec / Frontend
- `specs/feature-waiter-two-pane-layout/`
- `static/waiter.html` pane background classes

## 2026-07-13 — Fix Cashier dine-in table name display

### Summary
Check Out header no longer shows a random/numeric id for tables named like `F1`. Labels resolve from the floor-grid table name / `table_id` lookup instead of legacy integer `order.table_number`. Takeaway labels unchanged.

### Spec
- `specs/feature-walk-in-takeaway/requirements.md` — Cashier label rules clarified

### Frontend
- `static/counter.js` — `resolveCashierDineInTableLabel`, `selectOrder` passes `source.name`

## 2026-07-12 — Waiter qty-adjuster isolation audit

### Summary
Verified cart `+`/`-` and modifier-modal qty are isolated from Active Order Modal cancel flow; specs isolation notes tightened; full pytest green (184).

### Spec
- `feature-waiter-cart-breakdown` FR-WB2 isolation
- `feature-waiter-two-pane-layout` cart qty mention
- `feature-predefined-instructions` validation FR-Q3b

### Tests
- `pytest`: 184 passed

## 2026-07-12 — Modifier modal quantity before add-to-cart

### Summary
Customize Item popup includes `+` / `-` quantity (min 1). Add to Cart uses that qty; button total scales with qty × (base + modifiers).

### Spec
- `specs/feature-predefined-instructions/requirements.md` — FR-Q3b

### Frontend
- `static/waiter.html` — `#modifier-modal-qty-*`
- `static/waiter.js` — `modifierModalQty`, `addToCart(..., quantity)`

## 2026-07-12 — Waiter cart inline quantity adjusters

### Summary
New Order Cart lines use `+` / `-` qty controls; qty 0 removes the line. Notes/modifiers retained. Active-order modal unchanged.

### Spec
- `specs/feature-waiter-cart-breakdown/` — FR-WB1c
- `specs/qa_test_plan.md` — Waiter qty check

### Frontend
- `static/waiter.js` — `increaseCartItemQty` / `decreaseCartItemQty` → `updateCartQuantity` → `renderCart()`

## 2026-07-12 — System audit QA test plan

### Summary
Full automated baseline re-verified; added human E2E routine for System Analyst QA.

### Spec
- `specs/qa_test_plan.md`

### Tests
- `pytest`: 184 passed

## 2026-07-12 — Cashier network receipt printing

### Summary
Checkout receipts print from the server over LAN (Pillow/ESC/POS image path shared with kitchen). Cashier UI **Print Receipt** (`issue_receipt`) gates printing; printer failures return `warning` without failing payment. Browser `window.print()` removed.

### Spec
- `specs/feature-cashier-receipt-printing/`
- Updated `specs/tech-stack.md`, `specs/api-reference.md`, `specs/database-schema.md`

### Backend / Frontend / Tests
- `cashier` `PrinterRouteEndpoint`; `SHOP_NAME`; `OrderCheckoutResponse.warning`
- Counter Print Receipt checkbox + toast; admin Cashier printer IP fields
- `tests/test_cashier_receipt_printing.py`

## 2026-07-12 — Pre-E2E system audit (SDD sync)

### Summary
Documentation and frontend health check against current Cashier 3-pane / Waiter two-pane reality. No new product features. Specs updated for modal/pane wording; waiter legacy sidebar DOM fallbacks removed; full pytest green (181).

### Spec
- Synced pane/modal language across walk-in, cancellation, cart-breakdown, payment-method, table-all-view, api-reference, menu-item-tax/discount
- Added `feature-menu-item-tax/implementation.md` and `feature-payment-method-analytics/implementation.md` (explicitly notes **No Receipt / tax exemption is not implemented**)

### Frontend
- `static/waiter.js` — removed orphaned `#waiter-table-details-sidebar` / backdrop fallbacks; modal-only open/close

### Tests
- `pytest`: 181 passed

## 2026-07-12 — Cashier 3-pane billing layout

### Summary
Cashier / Billing is a single-page **Tables | Takeaways | Check Out** grid. Selecting an occupied table or takeaway fills the right pane without a modal; checkout controls and listeners stay intact.

### Spec
- `specs/feature-cashier-three-pane/`
- Updated `specs/feature-counter-ui/requirements.md`

### Frontend
- `static/counter.html` — `#pane-tables`, `#pane-takeaways`, `#pane-checkout`
- `static/counter.js` — selection highlighting; `selectOrder(order, source)`

## 2026-07-12 — Waiter two-pane layout & active-order modal

### Summary
Waiter screen splits into Menu+Cart (left) and Tables/Takeaways (right). Occupied tables and active takeaways open a centered pop-out modal so viewing an order never overrides the new-order cart.

### Spec
- `specs/feature-waiter-two-pane-layout/`
- Updated `specs/feature-waiter-cart-breakdown/` (FR-WB1b)

### Frontend
- `static/waiter.html` — tinted two panes; `#active-order-modal`
- `static/waiter.js` — modal open/close; available tables set cart context only

## 2026-07-11 — Waiter cart footer: Submit below price breakdown

### Summary
Cart sidebar groups price breakdown and Submit Order at the bottom so waiters review totals before confirming.

### Spec
- Updated `specs/feature-waiter-cart-breakdown/requirements.md` (FR-WB1b), `implementation.md`, `validation.md`

### Frontend
- `static/waiter.html` — `#cart-footer` with breakdown then `#submit-order`; table selection moved above footer

## 2026-07-11 — Table grid status labels (Free + compact typography)

### Summary
Floor grid cards show **Free** instead of raw `available` / `AVAILABLE`, with smaller status text so table names stand out.

### Spec
- Updated `specs/feature-table-all-view/requirements.md` (FR-TA5), `implementation.md`, `validation.md`

### Frontend
- `static/table-display.js` — `displayTableStatus()`, typography helpers
- `waiter.js`, `counter.js`, `table-dashboard.js` — consistent status rendering

## 2026-07-11 — Payment method analytics (Cash vs Mobile Money)

### Summary
Checkout requires and persists `payment_method` (`cash` | `mobile_money`). Dashboard Overview shows today/monthly sales split by payment method for reconciliation.

### Spec
- `specs/feature-payment-method-analytics/`
- Updated `specs/database-schema.md`, `specs/api-reference.md`, `specs/feature-counter-ui/requirements.md`

### Backend
- `OrderCheckoutRequest` validates/normalizes payment method
- `GET /api/analytics/sales-breakdown` — today + current month totals by payment method (`routers/analytics.py`)

### Frontend
- `counter.html` / `counter.js` — Cash/Mobile Money toggle buttons at checkout; payment breakdown cards on Dashboard Overview

### Tests
- `tests/test_payment_method_analytics.py` (4 scenarios)

## 2026-07-11 — Cashier takeaway display & order waiter attribution

### Summary
Walk-in takeaway orders no longer show "Deleted Table" / "Unknown" in the Cashier UI. Orders track who opened them via `Order.created_by_id`; API exposes `waiter_name` and Cashier checkout shows **Served by: [Name]**.

### Spec
- Updated `specs/database-schema.md`, `specs/feature-walk-in-takeaway/requirements.md`, `specs/api-reference.md`

### Backend
- `Order.created_by_id` FK + startup migration/backfill from earliest order item
- `waiter_name` / `served_by_name` on `OrderResponseDetail`, `OrderDetailsResponse`, `ActiveTakeawayOrderResponse`
- Set `created_by_id` on new orders in `POST /api/orders/submit` and `POST /api/orders/`

### Frontend
- `static/counter.js` — `cashierOrderDisplayLabel()`, `orderServedByLabel()` for takeaway list + checkout modal

### Tests
- Extended `tests/test_walk_in_takeaway.py` (order + active-takeaways `waiter_name`)

## 2026-07-11 — Table ALL view & compact table names

### Summary
Waiter, Cashier, and Table Dashboard floor grids default to an **ALL** zone tab showing every table in a dense responsive grid. UI strips leading `"Table "` from dine-in labels (e.g. `Table G1` → `G1`); takeaway labels unchanged.

### Spec
- `specs/feature-table-all-view/`
- Updated `specs/feature-table-management/requirements.md`, `specs/api-reference.md`

### Frontend
- `static/table-display.js` — shared `displayTableName()`
- `waiter.js`, `counter.js`, `table-dashboard.js` — ALL tab + grid density + formatted labels

### Tests
- `tests/test_table_all_view.py`

## 2026-07-11 — Menu management RBAC (admin vs cashier availability)

### Summary
Admins retain full menu CRUD. Cashiers may toggle sold-out/in-stock via `PATCH /api/menu-items/{id}/availability` only. Counter Menu Management tab shows availability-only UI for cashiers.

### Spec
- `specs/feature-menu-rbac/`
- Updated `specs/feature-rbac/requirements.md`, `specs/feature-menu-items/requirements.md`, `specs/api-reference.md`

### Backend
- `MENU_AVAILABILITY_ROLES` in `rbac.py`
- `MenuItemAvailabilityUpdate` schema; `PATCH /api/menu-items/{item_id}/availability`

### Frontend
- `counter.html` / `counter.js` — cashier stock toggles; admin-only sections hidden

### Tests
- `tests/test_menu_rbac_availability.py`

## 2026-07-06 — Menu category navigation pills (Counter + Waiter)

### Summary
Category ALL + per-category pills for client-side menu filtering. Counter Menu Management list gains tabs; waiter grid behavior documented (already implemented).

### Spec
- `specs/feature-menu-category-navigation/`

### Frontend
- `counter.html` / `counter.js` — `#menu-category-tabs`, `filterMenu()`, `hidden` row filter
- Waiter: existing `#category-tabs` in `waiter.js` (unchanged)

### Tests
- `tests/test_menu_category_navigation.py`; full suite **166 passed**

## 2026-07-06 — Predefined instruction quick tags

### Summary
Waiters can tap predefined instruction chips in the special-instructions modal; admins manage tags from Menu Management.

### Spec
- `specs/feature-predefined-instructions/`

### Backend
- `PredefinedInstruction` model; CRUD at `/api/predefined-instructions`
- Default Myanmar seed tags on empty table

### Frontend
- `waiter.html` / `waiter.js` — chip buttons append to textarea
- `counter.html` / `counter.js` — admin add/delete tags

### Tests
- `tests/test_predefined_instructions.py`; full suite **165 passed**

## 2026-07-06 — Spec/code baseline audit (SDD sync)

### Summary
Synchronized `specs/` with the current working codebase. Added canonical `database-schema.md` and `api-reference.md`. No new product features.

### Spec updates
- `tech-stack.md`, `mission.md`, `roadmap.md` — pricing, roles, router list, test count (160)
- Feature specs: menu discount/tax, waiter breakdown, walk-in takeaway, RBAC validation (90-day cap)
- New: `feature-menu-item-discount/implementation.md`, `validation.md`; `feature-waiter-cart-breakdown/implementation.md`

### Code cleanup
- Removed unused `_base_price_with_discount()` from `routers/orders.py`

## 2026-07-06 — Per-item menu discount + tax-after-discount pricing

### Summary
Menu items support `discount_type` (`none` / `percentage` / `fixed`) and `discount_value`. Standard POS math: tax is applied on the **discounted** price. Waiter cart shows per-item breakdown (Base | Disc | Tax) and footer includes Total Discount.

### Spec
- `specs/feature-menu-item-discount/` — new requirements
- `specs/feature-menu-pricing/`, `specs/feature-menu-item-tax/`, `specs/feature-waiter-cart-breakdown/` — updated formulas

### Backend
- `MenuItem.discount_type`, `MenuItem.discount_value`; `OrderItem.unit_discount_at_sale`
- `_calculate_order_line_pricing()` — discount then tax; legacy `discount_price` migrated at runtime
- `breakdown_discount_total` on order details / active takeaways; per-item `unit_discount_at_sale` in responses

### Frontend
- `waiter.html` / `waiter.js` — item-level breakdown rows, Total Discount footer row, sidebar item pricing

### Tests
- `tests/test_menu_item_discount.py` — 10% discount + 5% tax on discounted price; grand total formula
- Full suite **160 passed**

## 2026-07-06 — Waiter cart price breakdown (Subtotal / Tax / Grand Total)

### Summary
Waiter cart footer and active-order sidebar show a 3-line price breakdown. Backend `GET /api/orders/{id}/details` returns `breakdown_subtotal`, `breakdown_tax_total`, `breakdown_grand_total`.

### Spec
- `specs/feature-waiter-cart-breakdown/`

### Backend
- `_order_price_breakdown()`; fields on `OrderDetailsResponse` and `ActiveTakeawayOrderResponse`
- `unit_price_at_sale` on `OrderItemDetailsResponse`

### Frontend
- `waiter.html` / `waiter.js` — cart summary + order details sidebar breakdown; live update on takeaway toggle

### Tests
- `tests/test_waiter_cart_breakdown.py` — **1 passed**; full suite **157 passed**

## 2026-07-06 — Per-item tax on menu items

### Summary
Menu items support `tax_type` (`none` / `percentage` / `fixed`) and `tax_value`. Tax is calculated on the active base price (dine-in vs takeaway) at order submit and included in line subtotals. Checkout sums per-line tax for receipt display; legacy 5% global tax replaced.

### Spec
- `specs/feature-menu-item-tax/` — requirements + validation
- `specs/tech-stack.md` — updated checkout tax rules
- `specs/feature-menu-pricing/` — cross-reference

### Backend
- `MenuItem.tax_type`, `MenuItem.tax_value`; `OrderItem.unit_tax_at_sale`
- `_calculate_order_line_pricing()` in `routers/orders.py`
- Checkout uses sum of line taxes (no global 5%)

### Frontend
- `counter.html` / `counter.js` — Tax Type + Tax Value on menu form; checkout tax from lines
- `waiter.js` — `computeUnitTax()` in cart/display pricing

### Tests
- `tests/test_menu_item_tax.py` — **3 passed**; full suite **156 passed**

## 2026-07-06 — Auto-clear empty takeaway orders (last item cancel)

### Summary
When the last active item is cancelled, the order auto-transitions to `cancelled`. Cancelled takeaways are excluded from `active-takeaways` and removed from the UI via `order_cancelled` WebSocket. Waiter cart/sidebar dismisses automatically.

### Spec
- `specs/feature-order-cancellation/` — FR-C4 auto-clear behavior
- `specs/feature-walk-in-takeaway/` — active list removal documented

### Backend
- `_release_table_if_order_fully_cancelled` returns auto-cancel flag; broadcasts `order_cancelled` on full clear
- `GET /api/orders/active-takeaways` excludes `cancelled` orders

### Frontend
- `waiter.js` — `handleRemoteOrderClosed`, always refresh takeaway list; dismiss cart/sidebar
- `counter.js` — only clear checkout on cancelled/paid takeaway updates

### Tests
- `test_last_takeaway_item_cancel_auto_clears_from_active_list` — **passed**; full suite **153 passed**

## 2026-07-06 — Takeaway item-level cancel parity (corrects whole-order UI)

### Summary
Walk-in takeaway now mirrors dine-in for **item-level** cancellation: clicking an active takeaway card opens the order details sidebar with per-item Cancel controls. Removed "Cancel Entire Order" buttons from waiter/cashier UI. Customer name prompt uses modal or native `prompt()` fallback.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W6/W7: view order sidebar + item cancel parity
- `specs/feature-order-cancellation/` — reframed as item-level primary UX

### Frontend
- `waiter.js` — takeaway card → `openOrderDetails()`; `promptForCustomerName()`; removed whole-order cancel UI
- `counter.js` / `counter.html` — removed cashier Cancel Order button

### Tests
- `tests/test_walk_in_takeaway.py::test_cancel_takeaway_order_item_without_table` — **passed**

## 2026-07-06 — Walk-in customer prompt & whole-order cancellation

### Summary
Walk-in Takeaway button now prompts for optional customer name. New `POST /api/orders/{order_id}/cancel` cancels active orders, frees tables, and broadcasts realtime updates. Cancel Order buttons on waiter cart/sidebar and cashier checkout.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W4 customer name prompt
- `specs/feature-order-cancellation/` — cancel flow requirements + validation

### Backend
- `POST /api/orders/{order_id}/cancel` — cancel items + order, release table, WebSocket (`order_updated`, `takeaways_updated`, `table_status_changed`)
- Verified `customer_name` on `OrderCreate` / submit (unchanged)

### Frontend
- `waiter.js` — walk-in name prompt; Cancel Order in cart (append) + order details sidebar
- `counter.js` — Cancel Order on checkout panel

### Tests
- `tests/test_order_cancellation.py` — **3 passed**; full suite **151 passed**

## 2026-07-06 — Walk-in takeaway append mode

### Summary
Active walk-in takeaway orders are clickable on the waiter dashboard. Clicking opens cart **Append Mode** bound to `order_id`. `POST /api/orders/submit` accepts optional `order_id` to add batches without creating a duplicate order.

### Spec
- `specs/feature-walk-in-takeaway/` — FR-W6 append parity with occupied tables

### Backend
- `schemas.OrderSubmitRequest.order_id` optional
- `routers/orders.py` — takeaway append lookup (`table_id IS NULL`, open/dining)

### Frontend
- `waiter.js` — `activateTakeawayAppendContext()`, submit sends `order_id`, header "Adding to Takeaway: …"

### Tests
- `tests/test_walk_in_takeaway.py` — +2 scenarios; full suite green

## 2026-07-06 — Direct walk-in takeaway (`table_id = NULL`)

### Summary
Walk-in takeaway orders use no physical table. Waiter attribution via `OrderItem.created_by_id` from JWT session. UI adds **[ + Walk-in Takeaway ]** button; Cashier/kitchen display **🛍️ Takeaway #\<id\>**. Cart items default `is_takeaway=true` with dual pricing.

### Spec
- `specs/feature-walk-in-takeaway/` — requirements, plan, implementation, validation
- Audited: no dummy-table / `is_takeaway_zone` logic in codebase

### Backend
- Verified nullable `table_id` + `created_by_id` on submit; kitchen ticket header `Takeaway #<id>`
- `new_order_batch` WebSocket includes `order_type`

### Frontend
- `waiter.html` / `waiter.js` — walk-in button, cart defaults
- `counter.js` — `formatTakeawayOrderLabel`, cashier takeaway list/checkout headers
- `table-dashboard.html` / `table-dashboard.js` — active walk-in takeaway panel (kitchen board)

### Tests
- `tests/test_walk_in_takeaway.py` — **4 passed**; full suite **146 passed**

## 2026-07-06 — Dual pricing (dine-in vs takeaway per line)

### Summary
Menu items can have an optional `takeaway_price`. Order lines accept `is_takeaway`; server resolves unit price (takeaway price when set, else dine-in base). Waiter cart shows a per-line 🛍️ Takeaway checkbox with live subtotal updates.

### Spec
- `specs/feature-menu-pricing/` — requirements, plan, implementation, validation

### Backend
- `models.py` — `MenuItem.takeaway_price`, `OrderItem.is_takeaway`
- `schemas.py`, `routers/orders.py`, `routers/menu.py`, `main.py` migrations

### Frontend
- `static/counter.html`, `static/counter.js` — optional Takeaway Price on menu form
- `static/waiter.js` — per-line takeaway toggle + dynamic pricing

### Tests
- `tests/test_menu_dual_pricing.py` — **4 passed**; full suite **142 passed**

## 2026-07-06 — Counter primary nav highlighting & category edit modal

### Summary
Dashboard, Cashier/Billing, and Menu Management tabs use enhanced primary styling. Category rename uses a modal instead of `window.prompt`; Edit/Delete were already wired to backend CRUD.

### Spec
- `specs/feature-counter-ui/requirements.md` (new) — FR-N1–FR-N3 primary nav UX
- `specs/feature-category-crud/` — FR-3/FR-4 UI modal + full CRUD matrix

### Frontend
- `static/counter.html` — `.tab-btn-primary` styles; `#category-edit-modal`
- `static/counter.js` — `openCategoryEditModal`, `bindCategoryEditModal`

### Backend
- No API changes (`PUT`/`DELETE` `/api/categories/{id}` already in `routers/menu.py`)

### Tests
- `tests/test_category_crud.py` — **5 passed**; full suite **138 passed**

## 2026-07-06 — Strict password vs PIN login separation

### Summary
Password roles (`root`, `admin`) and PIN roles (`account`, `cashier`, `waiter`) are enforced at login endpoints with explicit **403** responses when the wrong auth method is used.

### Backend
- `routers/auth.py` — `/login` rejects PIN roles; `/login-pin` rejects password roles

### Frontend
- `static/login.js`, `static/pin-login.js` — surface 403 detail messages
- `static/auth.js` — Change Password hidden for PIN roles; export `PIN_ROLES`
- `static/counter.js` — staff form PIN field toggled by role

### Tests
- `tests/test_rbac_security_gaps.py`, `tests/test_rbac.py` — strict login rejection cases
- `tests/test_integrity.py` — fix isolated-run summary assertion
- Full suite: **138 passed** (`PYTHONPATH=. python -m pytest -q`)

## 2026-07-06 — Account role PIN-only authentication (SDD alignment)

### Summary
`account` is now a PIN-based role like `cashier`/`waiter`. Only `root` and `admin` use username + password. Change Password is forbidden for `account`.

### Spec
- `specs/feature-rbac/` — auth matrix, change-password contract, validation checklist
- `specs/feature-account-reports/` — login, provisioning, validation updated

### Backend
- `rbac.py` — `PIN_ROLES` includes `account`; `PASSWORD_ROLES` is `root`/`admin` only
- `routers/auth.py` — change-password `403` for account; login-pin accepts account
- `routers/users.py` — account requires `pin_code`; rejects `password` on staff API

### Frontend
- `static/auth.js`, `static/login.js` — Change Password / password login for `root`/`admin` only
- `static/pin-login.js` — account logs in via PIN → `/account`
- `static/counter.js`, `counter.html` — staff form uses PIN for all roles including account

### Tests
- `tests/test_rbac_security_gaps.py` — account in forbidden change-password cases
- `tests/test_rbac.py` — account PIN provisioning + session tests
- Full suite: **123 passed** (`PYTHONPATH=. python -m pytest -q`)

## 2026-07-05 — Multi-cashier real-time checkout sync

### Summary
When one cashier checks out a table or takeaway order, all other open cashier Counter sessions refresh immediately (table grid, takeaway list, and stale receipt cleared).

### Backend
- `routers/orders.py` — broadcast `order_updated` on checkout alongside `order_completed`

### Frontend
- `static/counter.js` — handle `order_completed`, `takeaways_updated`, and paid `order_updated` via shared `handleRemoteOrderClosed`

### Tests
- Full suite: **121 passed** (`PYTHONPATH=. python -m pytest -q`)

## 2026-07-05 — Cashier denied Staff Performance (SDD alignment)

### Summary
Cashiers may view **own checkout total today** only. Staff Performance APIs and Counter UI (`by-cashier`, `by-order-staff`, dashboard subtab) are **root/admin only**.

### Backend
- `routers/reports.py` — removed `cashier` from `_STAFF_REPORT_ROLES` and `_ORDER_STAFF_ROLES`
- `services/report_access.py` — `can_view_staff_breakdown` / `can_view_all_waiter_sales` → root/admin only

### Frontend
- `static/counter.js` — hide Staff Performance section and charts for cashier

### Spec / Tests
- `specs/feature-cashier-reports/` + `specs/feature-rbac/` — requirements, implementation, validation synced
- `tests/test_cashier_reports.py` — `test_cashier_cannot_view_*` (**403**)
- Full suite: **121 passed** (`pytest -q`)

## 2026-07-05 — Cashier reports & waiter incentives SDD + tests

### Summary
Formalized SDD for cashier ordering inheritance, scoped daily sales, staff breakdown, and promoted-item incentives. Added dedicated pytest modules; backend already complete on `main`.

### Spec
- `specs/feature-cashier-reports/` — requirements, plan, implementation, validation
- `specs/feature-waiter-incentives/` — requirements, plan, implementation, validation

### Tests
- `tests/test_cashier_reports.py` (5)
- `tests/test_waiter_incentives.py` (7)
- Full suite: **84 passed** (`pytest -q`, 2026-07-05)

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **84 passed**

## 2026-07-05 — Staff Performance date-range reporting (root QA gap)

### Summary
Counter Dashboard → Staff Performance now supports **daily and monthly** per-cashier and per-waiter breakdowns via a date-range picker (not single-day only).

### Frontend
- `static/counter.html` — `staff-filter-start-date` / `staff-filter-end-date`; presets **Today** and **This Month**
- `static/counter.js` — `getStaffReportDateRange()`, default month-to-date; charts call `by-cashier` / `by-order-staff` with `start_date` + `end_date`

### Spec / Tests
- `specs/feature-rbac/` — requirements (FR-D1), implementation, validation, plan, roadmap synced
- `test_per_cashier_and_waiter_reports` — monthly `by-cashier` range assertion
- `test_phase4_dashboard_ui_contract` — staff date-range UI contract

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 — Menu soft delete, category CRUD, and counter UI (`feat/ui-updates` merged)

### Menu item soft delete
- `DELETE /api/menu-items/{id}` sets `is_deleted=true`; blocks when item is on an active unpaid order (`400`).
- Waiter/counter lists use `GET /api/menu-items/` (`is_deleted=false` only).
- Tests: `tests/test_menu_item_soft_delete.py`, `tests/test_sales_integrity.py`

### Category delete fix
- Category delete counts only active menu items (`is_deleted=false`).
- Category with only soft-deleted items can be deleted.
- Tests: `tests/test_category_crud.py`

### Counter UI
- Main navigation active tab state (`setActiveMainTab` in `counter.js`).
- Docs: `specs/feature-menu-items/`, `specs/feature-category-crud/`, `specs/feature-counter-ui/`

## 2026-07-04 - feat(rbac): complete feature delivery (Phases 1–4b)

### Summary
Full RBAC & authorization feature shipped: five-role hierarchy, session/device policy, hierarchical user management, audit logs, role-scoped dashboards, promoted-item waiter incentives, CLI root bootstrap, and automated hierarchy compliance tests.

### Backend
- `rbac.py`, `services/sessions.py`, `services/audit.py`, `services/report_access.py`
- `routers/setup.py`, `routers/root_users.py`; staff API `_reject_privileged_roles_via_staff_api` (403 on admin/root via staff endpoints)
- `scripts/seed_root.py` — production-safe first-root bootstrap
- Models: `UserSession`, `AdminAuditLog`, `Order.checked_out_by_id`, `MenuItem.is_promoted`
- Role-scoped reports, account 93-day cap, checkout/waiter attribution

### Frontend (static JS — not Next.js)
- `/setup`, `/account`, `/counter` (Admin Accounts, Staff Management, Audit Logs, Dashboard, Waiter Incentives)
- `device.js`, role-aware nav (`auth.js`), promo badges (`waiter.js`)

### Spec / Tests
- `specs/feature-rbac/` — requirements, plan, implementation, validation (synced 2026-07-04)
- `tests/test_rbac.py`, `tests/test_rbac_hierarchy.py`, `tests/test_orders_rbac.py`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 - feat/rbac-hierarchy-compliance

### Summary
Automated strict role-creation hierarchy tests; handler-level 403 enforcement for privileged roles on staff API.

### Backend
- `schemas.py`: `UserCreateRequest.role` uses `StaffRole` for handler-level checks
- `routers/users.py`: `_reject_privileged_roles_via_staff_api`

### Tests
- `tests/test_rbac_hierarchy.py` — 5 scenarios (root→admin, admin blocks, floor staff CRUD, floor staff denied, root via staff API blocked)

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed**

## 2026-07-04 - feat/rbac-root-seed-cli

### Summary
Production-safe CLI to create the first `root` user when none exists.

### Backend
- `scripts/seed_root.py` — idempotent; default username `root`; password min 6 chars

### Tests
- `tests/test_rbac.py::test_seed_root_script_creates_first_root`

## 2026-07-04 - feat/rbac-phase4b-promoted-items

### Summary
Phase 4b: `MenuItem.is_promoted`, promoted-by-waiter reporting, Waiter Incentives dashboard (root/admin), promo badges on waiter menu.

### Backend
- `models.py`: `MenuItem.is_promoted`.
- `schemas.py`: `PromotedStaffSalesResponse`; `is_promoted` on menu schemas.
- `main.py`: lifespan `ALTER TABLE menu_items ADD is_promoted`.
- `routers/menu.py`: `toggle-promoted`; create respects `is_promoted`.
- `routers/reports.py`: `GET /api/reports/sales/promoted-by-waiter`.

### Frontend (static JS)
- `counter.html/js`: promoted checkbox, Promote button, Waiter Incentives tab.
- `waiter.js`: ★ Promo badge on menu cards.

### Tests
- `test_promoted_items_full_flow`, `test_phase4b_promoted_ui_contract`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **72 passed** (final suite count)

## 2026-07-04 - feat/rbac-complete

### Summary
**RBAC & Reporting feature delivered:** five-role hierarchy (Phases 1–4b), session policy, user management, role-scoped dashboards, audit logs, and promoted-item waiter incentives.

## 2026-07-04 - feat/rbac-phase4-dashboards

### Summary
Phase 4 UI (excl. 4b): account monthly/date-range reports, role-scoped counter dashboard staff charts, Take Orders nav for cashier/waiter.

### Backend
- `routers/reports.py`: account `monthly-sales` clips to 93-day window instead of rejecting current year.

### Frontend
- `static/account.html`, `account.js` — History tab, 93-day range, daily/monthly charts, cashier breakdown.
- `static/counter.html`, `counter.js` — Staff Performance subtab, `applyDashboardRoleVisibility`, cashier dashboard access.
- `static/auth.js` — **Take Orders** nav link (`/waiter`) for cashier/waiter only.

### Tests
- `test_phase4_dashboard_ui_contract`
- `test_account_monthly_sales_access`
- `test_cashier_cannot_access_monthly_store_sales`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **60 passed**

## 2026-07-04 - feat/rbac-audit-log-viewer

### Summary
Phase 3 UI: root-only Audit Logs tab on Counter screen, connected to `/api/root/audit-logs` with action/date filters.

### Backend
- `routers/root_users.py`: optional `action`, `start_date`, `end_date` query params on audit log list.

### Frontend
- `static/counter.html`: Audit Logs tab + filter bar + table.
- `static/counter.js`: `loadAuditLogs`, root-only tab visibility, forbidden handling.

### Tests
- `test_audit_logs_forbidden_for_non_root`
- `test_audit_logs_filter_by_action`
- `test_audit_logs_invalid_date_range`
- `test_counter_audit_log_ui_contract`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **57 passed**

## 2026-07-04 - rbac/open-decisions-resolved

### Summary
Resolved three RBAC open decisions per product owner approval: root admin-panel superset, cashier daily-only reports, audit PIN redaction.

### Spec
- `specs/feature-rbac/requirements.md` §12 → **Resolved Decisions** table; §3.1, §3.4, §7 FR-A2 updated.

### Backend
- `services/audit.py`: PIN snapshots use `"[REDACTED]"`; `pin_set` / `pin_changed` in `detail_json`.
- `routers/users.py`: pass `pin_set` on create, `pin_changed` on update.

### Tests
- `tests/test_rbac.py::test_audit_log_never_stores_plaintext_pin`

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **53 passed**

## 2026-07-04 - docs/sdd-audit-sync

### Summary
SDD alignment audit: synchronized feature `implementation.md` / `validation.md` files with current codebase state; recorded gaps and technical debt honestly.

### Documentation Updates
- **Created** `specs/feature-rbac/implementation.md` (module map, API inventory, known gaps).
- **Updated** `specs/feature-rbac/validation.md` — corrected test claims; added UI implemented vs pending.
- **Updated** `specs/feature-kitchen-printing/validation.md` — 52 passed; RBAC `root+admin`; manual vs automated annotations.
- **Updated** `specs/feature-kitchen-printing/implementation.md` — RBAC wording, takeaway dispatch, test count.
- **Updated** `specs/feature-table-management/validation.md` — checked automated items; documented finalized status + root RBAC.
- **Updated** `specs/roadmap.md` — Phase 0 RBAC baseline, Step 7/8/10 status, current test count.

### Audit Findings (no code changes)
- RBAC: audit log UI, account monthly UI, cashier→waiter nav link still open.
- Table mgmt: PUT validation tests + `table_grid_updated` WebSocket in counter open.
- Kitchen printing: takeaway ticket header untested; escpos missing-host path untested.
- Root has `ADMIN_PANEL_ROLES` superset (staff API) — spec ambiguity documented in `implementation.md`.

### Validation
- `PYTHONPATH=. venv/bin/python -m pytest -q` → **52 passed** (2026-07-04).

## 2026-07-03 - feat/rbac-hierarchy

### Summary
Expanded role-based access control to five roles (`root`, `admin`, `account`, `cashier`, `waiter`), added server-side session/device policy, one-time root setup, admin audit logs, and role-scoped reporting with per-cashier/per-staff breakdowns. Removed legacy `kitchen` login role.

### Backend
- New modules: `rbac.py`, `services/sessions.py`, `services/audit.py`, `services/report_access.py`.
- New routers: `routers/setup.py` (one-time root), `routers/root_users.py` (admin CRUD + audit logs).
- Models: `UserSession`, `AdminAuditLog`, `Order.checked_out_by_id`.
- JWT now includes `jti`; single-device enforcement for `account`, `cashier`, `waiter`.
- Reports: role-scoped access, account 93-day cap, `/api/reports/sales/by-cashier`, `/api/reports/sales/by-order-staff`.
- Startup: promote legacy `admin` user to `root` when no root exists; removed auto-seed default admin.

### Frontend
- `/setup` one-time root setup page.
- `/account` read-only reports page.
- `device.js` for persistent `device_id` on login.
- Cashier may use `/waiter` screen; root treated as admin panel in counter UI.

### Spec / Docs
- Added `specs/feature-rbac/` (requirements, plan, validation).

### Test Coverage Added
- `tests/test_rbac.py` — hierarchy, sessions, setup, reports, checkout attribution.
- Updated `conftest.py`, `test_orders_rbac.py`, `test_deletion_integrity.py`.
- Validation run: `PYTHONPATH=. venv/bin/python -m pytest -q` → `52 passed`.

## 2026-06-24 - feat/kitchen-print-font-fallback

### Summary
Improved image-rendered kitchen ticket output by adding Latin/digit/punctuation fallback font support for mixed Myanmar and English ticket text.

### Backend / Assets
- Added bundled Latin fallback font support using `assets/fonts/NotoSans-Regular.ttf`.
- Added upstream OFL license at `assets/fonts/OFL-NotoSans.txt`.
- Updated image renderer to choose Myanmar font for Myanmar Unicode ranges and Latin fallback font for English labels, numbers, and punctuation.

### Spec / Docs
- Updated kitchen printing requirements, plan, validation, implementation reference, tech stack, and font README for multi-font fallback behavior.

### Test Coverage Added
- Font fallback routing coverage for mixed Myanmar/English/digit/punctuation ticket text.
- Bundled font loadability coverage for Myanmar and Latin font assets.
- Validation run: `PYTHONPATH=. venv/bin/python -m pytest -q` → `44 passed`.

## 2026-06-23 - docs/kitchen-print-font-bundle

### Summary
Bundled Noto Sans Myanmar for kitchen ticket image rendering so deployments can print Myanmar text without requiring `.env` font path configuration.

### Backend / Assets
- Added `assets/fonts/NotoSansMyanmar-Regular.ttf`.
- Added upstream OFL license at `assets/fonts/OFL-NotoSansMyanmar.txt`.
- Extended image renderer font discovery to prefer bundled fonts in `assets/fonts/` and `static/fonts/`, then system fonts, then Pillow fallback.
- Kept `KITCHEN_PRINT_FONT_PATH` as an optional deployment override.

### Spec / Docs
- Updated kitchen printing requirements, plan, validation, and implementation reference with bundled font behavior and troubleshooting notes.
- Updated `specs/tech-stack.md` and `.env.example` to clarify that bundled font auto-discovery is the default path.

### Test Coverage Added
- Bundled Myanmar font auto-discovery regression coverage in `tests/test_kitchen_printing.py`.
- Validation run: `PYTHONPATH=. pytest -q` → `41 passed`.

## 2026-06-23 - feat/kitchen-image-printing

### Summary
Extended kitchen LAN printing with server-side image render mode for Myanmar text compatibility on Xprinter/ESC/POS printers that cannot render Myanmar Unicode text directly.

### Backend Changes
- Added Pillow dependency for ticket image rendering.
- Added `render_mode` and `paper_width_px` to `kitchen_printer_settings`.
- Extended printer settings API:
  - `render_mode`: `text` | `image`
  - `paper_width_px`: `384` | `576`
- Added image renderer and ESC/POS raster payload builder.
- File backend now supports PNG preview output in image mode.
- Network backend can send raster image ESC/POS payloads in image mode.
- Existing text mode remains the default compatibility path.

### Frontend Changes
- Counter → Menu → Kitchen Printer Settings now includes:
  - render mode selector
  - paper width selector for 58mm/80mm printers

### Spec / Docs
- Updated `specs/feature-kitchen-printing/requirements.md`, `plan.md`, and `validation.md`.
- Updated `specs/roadmap.md`, `specs/tech-stack.md`, and `.env.example`.

### Test Coverage Added
- Image mode file backend writes PNG output.
- ESC/POS raster payload builder returns non-empty raster bytes.
- Settings API validates render mode and paper width.
- Validation run: `PYTHONPATH=. pytest -q` → `39 passed`.

## 2026-06-02 - feat/kitchen-lan-printing

### Summary
Implemented Step 9 kitchen LAN printing with admin category-level printer routing
(`drinks` | `food`, default `food`), configurable ESC/POS network backend for
Xprinter printers, and file backend for development without physical hardware.

### Backend Changes
- Added `Category.printer_route` column and startup migration in `main.py`.
- Extended category schemas/API:
  - `CategoryCreate`, `CategoryUpdate`, `CategoryResponse` include `printer_route`
  - `PUT /api/categories/{category_id}` for admin route updates
- Added `services/printing/` module:
  - route resolver with unknown/null → `food` fallback
  - ticket builder (single-item tickets, Myanmar text, takeaway header)
  - `file` and `escpos_network` backends
- Replaced `mock_send_to_printer` in `routers/orders.py` with `dispatch_kitchen_ticket`.
- Print dispatch remains non-blocking on order submit (`return_exceptions=True`).

### Frontend Changes
- Counter menu admin:
  - category create form includes printer route selector
  - category list shows route badge + inline route update (Save)

### Configuration
- Added `.env.example` printer settings (optional env fallback):
  - `PRINTER_BACKEND`, `PRINTER_DRINKS_HOST/PORT`, `PRINTER_FOOD_HOST/PORT`
  - optional `KITCHEN_PRINT_OUTPUT_DIR`
- **Admin UI (preferred):** Counter → Menu → Kitchen Printer Settings
  - print mode (`file` / `escpos_network`)
  - Drinks + Food counter LAN IP/port saved in database

### Backend (UI settings)
- Added `kitchen_printer_settings` + `printer_route_endpoints` tables.
- Added `GET/PUT /api/admin/kitchen-printers` (admin only).
- Print service loads backend + LAN endpoints from DB, with env fallback if host missing.

### Spec / Docs
- Added `specs/feature-kitchen-printing/` (requirements, plan, validation)
- Updated `specs/roadmap.md` Step 9 and kitchen dispatch baseline notes
- Updated `specs/tech-stack.md` orders router description

### Test Coverage Added
- `tests/test_kitchen_printing.py`:
  - route resolver defaults/unknown fallback
  - category API `printer_route` contract + 422 invalid literal
  - drinks/food file routing on mixed submit
  - unknown DB route fallback to food file
  - submit success when print dispatch raises

## 2026-04-20 - feat/table-management

### Summary
Implemented Phase 1 / Step 7 table-management enhancements on branch `feat/table-management` with finalized-order deletion safety (`paid` and `cancelled` only), historical-order detachment, realtime refresh consistency, and expanded automated coverage.

### Backend Changes
- Updated `routers/tables.py` table/zone delete safety checks to use:
  - finalized statuses: `paid`, `cancelled`
  - block condition: any linked order not in finalized set
- Refined blocked-delete API messages to clearly explain eligibility:
  - table delete now states only paid/cancelled orders permit deletion.
- Kept historical integrity behavior:
  - on successful delete, linked finalized orders are preserved and detached via `table_id = NULL`.
- Marked Step 7 status as completed in `specs/roadmap.md`.

### Frontend Changes
- No frontend code changes were required in this branch.
- Existing admin table-management UX in `static/counter.js` already provided:
  - table edit controls (rename + zone reassignment)
  - explicit table delete action with confirmation
  - user feedback paths for success and error responses

### Realtime / Refresh Changes
- Ensured table-grid refresh broadcast consistency in `routers/tables.py`:
  - `update_table` now triggers table-grid refresh after successful update.
  - `delete_table` now triggers table-grid refresh after successful delete.
  - `delete_zone` now triggers table-grid refresh after successful delete.

### Test Coverage Added/Updated
- Updated `tests/test_tables_management.py` expectations for new non-finalized delete semantics.
- Added test coverage for:
  - blocked delete when status is `completed` (treated as non-finalized/unpaid),
  - successful delete when status is `cancelled`,
  - historical detachment (`table_id = NULL`) retention for finalized rows.
- Validation runs:
  - targeted suite passed (`tests/test_tables_management.py` + `tests/test_integrity.py`)
  - full suite passed (`30 passed`).
