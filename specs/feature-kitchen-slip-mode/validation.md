# Validation: Kitchen Slip Mode

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` → **374 passed** (2026-11-16; 52 in `tests/test_kitchen_slip_mode.py`).

## Automated

### Setting: contract and roles
- [x] Default is `per_item`
- [x] Admin switches to `combined` and back; value is returned by GET and stored
- [x] PUT without `kitchen_slip_mode` keeps the stored value
- [x] Unknown values → `422`, stored value unchanged (`"both"`, `""`, `"PER_ITEM"`, `1`, `"combined "`)
- [x] `401` anonymous; `403` waiter / cashier / account on GET and PUT; `200` admin / root
- [x] Unknown value already in the database behaves as `per_item`

### Submit
- [x] `per_item`: one job per line, each linked to its order line
- [x] `combined`: one job per route (food first, then drinks), `order_item_id` null, items in submission order with their line ids, `batch_number`
- [x] Same order in both modes: same total, same line subtotals, same response fields, no warning
- [x] Second submit to the same table prints only the new batch (`Batch: #2`)

### Slip text (real renderer)
- [x] Combined: one `=== KITCHEN TICKET ===`, `Batch: #1`, quantities, note, `(ပါဆယ်)`, one cut line, no prices, drinks not on the food slip
- [x] Per item: one `=== KITCHEN ITEM TICKET ===` per line

### Combined slip in the print queue
- [x] Failed slip is listed once with a label naming its lines; Retry prints it as one slip; total unchanged
- [x] Retry leaves out a cancelled line (label and printed slip); stored payload is not rewritten
- [x] Every line cancelled: hidden from the failed list, Retry counts it as skipped, nothing printed
- [x] Cancelled order: not printed
- [x] Line cancelled while the slip waits in the queue is left out; all cancelled → `Skipped: all items were cancelled`, no send attempt
- [x] Changing the mode does not reshape slips already recorded (both directions)
- [x] Label shows three lines then `+N more`

### Kitchen printer vs cashier printer (real TCP sockets, one listener per printer)
- [x] `per_item` and `combined`, LAN mode: every kitchen slip arrives at the kitchen printer and nowhere else; the cashier printer receives exactly one receipt and no kitchen slip
- [x] The printed receipt is identical in both modes (apart from order number, table, time)
- [x] Windows mode + `combined`: receipt goes to the Windows cashier queue only; kitchen slip goes to the kitchen LAN printer only; nothing is sent to the cashier's LAN address
- [x] Three deliberate breakages (kitchen role resolving to the cashier printer, Windows queue used for every route, receipt sent to the kitchen role) each fail these tests

### Copies of a combined slip (FR-SM7)
- [x] Default `kitchen_slip_copies` is 1; admin sets 3; PUT without the field keeps the stored value and the mode
- [x] `0`, `4`, `-1`, `2.5`, `"2"`, `"many"`, `true` → `422`, stored value unchanged
- [x] `403` waiter / cashier / account
- [x] A stored value outside 1–3 (`0`, `9`, `-2`) is returned as 1 and prints one slip
- [x] `combined` + 3 copies, food + drinks order: six jobs in the order food 1,2,3 then drinks 1,2,3, same lines on every copy, order lines and total not duplicated
- [x] 1 copy: no `copy_number` / `copy_total` in the job, no banner, slip starts with the title as before
- [x] `per_item` with copies stored as 3: one slip per line, no banner
- [x] Each copy starts with its own `COPY n / 3` banner as the first line; apart from the banner the copies are identical
- [x] Plain text (file backend): framed three-line block; the internal banner marker is never written
- [x] ESC/POS text: centre + double width/height + reversed around ` COPY n / N `, all three switched off before the rest of the slip; a slip without copies is byte-for-byte unchanged
- [x] Image mode: banner is a bar taller than two text lines, black from the left paper edge to the right, white text
- [x] Second copy fails: only that job is `failed`, it is listed as `… (copy 2/3)`, Retry prints only copy 2
- [x] Line cancelled before Retry: left out of every copy
- [x] Real TCP: kitchen printer receives copies 1, 2, 3 in order; cashier printer receives exactly one receipt without a banner

### Existing database
- [x] Real app startup on a database without the columns adds `kitchen_slip_mode` and `kitchen_slip_copies`, keeps the other settings, values `per_item` / 1

### Test strength
Eleven deliberate breakages (mode ignored at submit, cancelled lines not filtered, all-cancelled slip retried, PUT not storing, PUT resetting when omitted, no migration, failed list not filtered, GET always `per_item`, food and drinks merged, label ignoring cancellations, unknown stored value accepted) were each caught by a test.

Copies: twenty deliberate breakages (copies ignored at submit or not passed, banner missing, banner on a single copy, copy fields stored for one copy, reverse never switched off, banner not double size, marker written to the file, image banner drawn as plain text / white / normal size, API accepting 4, 0, `"2"`, stored value not clamped, PUT not storing, GET constant, no label suffix, copy number dropped before rendering, no migration) were each caught by a test. One of them (banner on a single copy) was not caught at first; `test_a_single_copy_never_gets_a_banner` was added for it.

## Manual: copies (2026-11-16, real app with its print queue on a temporary database created without the new column, fake LAN printers on real TCP sockets, desktop browser)
- [x] Startup added `kitchen_slip_copies` to the existing database, value 1
- [x] API: waiter `403`; `0`, `4`, `"2"`, `2.5` → `422`
- [x] `combined` + 3 copies, image mode, 3-line Myanmar order: kitchen printer received exactly 3 slips, cashier printer nothing; the received raster images decode to three slips with `COPY 1 / 3`, `COPY 2 / 3`, `COPY 3 / 3` bars and identical bodies; total 16500 unchanged; 3 jobs `printed` labelled `(copy 1/3)` … `(copy 3/3)`
- [x] Text mode, 2 copies: exactly 2 slips, each starting with the big reversed banner bytes
- [x] Checkout: cashier printer exactly 1 receipt without banner; kitchen printer nothing more
- [x] Kitchen printer stops answering after copy 1: jobs `printed, failed, failed`; **Print failed** lists copy 2/3 and 3/3; after the printer is back, Retry sends only those two; the kitchen ends with copies 1, 2, 3 once each
- [x] `per_item` while copies is still stored as 3: one slip per item, no banner
- [x] Browser: **Copies** shows the stored value after page load; disabled with **One slip per item**, enabled with **All items on one slip**; **Save Print Mode** stores 2, then 3; saving `per_item` keeps the stored copies value
- Note: each submit opens one empty connection to the printer before the slips (the existing offline check). It is one per submit, not one per copy, and prints nothing.

## Manual (2026-11-16, real app on a temporary database, file backend, desktop browser)
- [x] Menu Management → Kitchen Printer Settings shows **Kitchen slip** with both options
- [x] Select + **Save Print Mode** changes the server value; still selected after a server restart and page reload
- [x] Combined: order of 2 food lines + 1 drink → one food ticket with both lines, one drinks ticket
- [x] Per item: same order → two food tickets + one drinks ticket; same amount added to the order
- [x] Combined takeaway order: one ticket with the customer name
- [x] Kitchen printer unreachable (LAN mode): order saved with offline warning, one failed combined slip listed; Retry after fixing prints one combined ticket even though the mode had been switched to per item
- [x] Image mode: combined slip renders Myanmar item names, note and `(ပါဆယ်)`

## Not verified
- [ ] A real thermal printer: length and cut of a long combined slip
- [ ] A real thermal printer: the copy banner. Image mode sends the same kind of raster as the rest of the slip, so it should print as shown. Text mode relies on the printer supporting ESC/POS double size (`GS !`) and reverse (`GS B`); a model without reverse prints `COPY n / N` large but black on white
- [ ] Paper use and kitchen workflow with 3 copies of a long slip
- [ ] The control on a phone-sized screen
