# Validation: Kitchen Slip Mode

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` → **346 passed** (2026-11-16; 24 new in `tests/test_kitchen_slip_mode.py`).

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

### Existing database
- [x] Real app startup on a database without the column adds it, keeps the other settings, value `per_item`

### Test strength
Eleven deliberate breakages (mode ignored at submit, cancelled lines not filtered, all-cancelled slip retried, PUT not storing, PUT resetting when omitted, no migration, failed list not filtered, GET always `per_item`, food and drinks merged, label ignoring cancellations, unknown stored value accepted) were each caught by a test.

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
- [ ] The control on a phone-sized screen
