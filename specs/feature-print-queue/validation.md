# Validation: Print Queue + Retry

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` → **322 passed** (2026-11-16; 286 before this feature, 36 new in `tests/test_print_queue.py`).

## Automated (`tests/test_print_queue.py`)

### Queue mechanics
- [x] Slips for one printer are sent one at a time, with the configured pause between them
- [x] Slips keep submission order
- [x] Different printers do not wait for each other (receipt is not stuck behind kitchen backlog)
- [x] A failing slip does not stop the worker
- [x] `run()` returns the result / raises the failure; runs directly when the queue is not started
- [x] `submit()` on a stopped queue raises instead of dropping the slip
- [x] `stop()` releases callers that are still waiting
- [x] `PRINT_QUEUE_DELAY_SECONDS` parsing (unset, empty, number, 0, negative, invalid)
- [x] Queue keys identify one physical printer

### Contract and business rules (HTTP)
- [x] Submit records one job per line, linked to its order line, `printed`, `warning` null
- [x] Printer failure: submit `200`, order saved with correct total, jobs `failed` + `error_message`
- [x] Retry reprints only the failed slip with the stored content; attempts counted; second retry prints nothing; order total unchanged
- [x] Retry that fails again stays `failed` with the new reason
- [x] Retry skips cancelled lines / cancelled orders (`skipped`), and the failed list hides them
- [x] `404` for unknown order
- [x] Roles: `401` anonymous, `403` account, `200` waiter / cashier / admin / root on all three endpoints
- [x] Checkout queues the receipt; payment (`paid`, total, change) is unaffected by a failed receipt
- [x] Waiter cannot see or reprint a receipt; cashier can, with the same amounts
- [x] `issue_receipt=false` creates no job
- [x] Failed list: response fields, newest first, time window, `hours` validation (`422`)
- [x] Submit still succeeds (with `warning`) when slips cannot be queued
- [x] Result is broadcast as `print_job_updated` and is JSON-serialisable
- [x] Startup marks interrupted `pending` jobs `failed`
- [x] `print_status` accepts only `pending` / `printed` / `failed`

### Background queue against the database
- [x] Queueing returns before anything is printed; then all slips print in order, never overlapping, with the pause
- [x] A failed slip is recorded and the next slip still prints
- [x] A line cancelled while its slip waits is not printed (`Skipped: item was cancelled`)
- [x] Kitchen, bar and cashier resolve to separate queues; drinks share the kitchen queue when there is no bar printer; Windows / file backends
- [x] Print Test waits behind a live slip for the same printer

### Real app + real sockets (subprocess, temporary database)
- [x] Lifespan starts the queue with the env delay and stops it on shutdown
- [x] Job left `pending` by a previous run is `failed` after startup
- [x] Submit of 4 lines returns in under 0.8 s; 4 slips arrive at a TCP listener at least 0.28 s apart (delay 0.3 s)
- [x] Unreachable printer: submit `200` + offline `warning`, job `failed`, listed in `/api/print-jobs/failed`
- [x] After the printer address is corrected, Retry prints exactly one slip and the failed list is empty

### Updated existing tests
- [x] `test_cashier_receipt_printing.py`, `test_windows_cashier_printing.py`: a failed receipt is now asserted on the print job instead of `warning`
- [x] Patch targets moved from `routers.orders.dispatch_*` to `services.printing.print_jobs.dispatch_*`

### Test strength
Checked by breaking the code on purpose: no pause, one shared queue, failure not recorded, retry ignoring cancelled lines, waiter allowed to reprint receipts, cancelled-while-queued slip still printed. Each was caught by at least one test.

## Manual (done 2026-11-16, temporary database, simulated TCP printer, desktop browser)
- [x] Waiter screen: order submitted with the printer down → **Print failed (2)** button appears without reload
- [x] List shows order, table, both slips (Myanmar item names) and the reason
- [x] Retry with the printer back → slips arrive 1.09 s apart, list empties, button disappears
- [x] Counter screen: checkout with an unreachable receipt printer → `paid`, toast, **Print failed (1)**; the button is still there after reload
- [x] Retry that fails again → toast shown again

## Not verified
- [ ] A real thermal printer: that a 1 s pause is enough to stop dropped tickets on the actual Xprinter model (raise `PRINT_QUEUE_DELAY_SECONDS` if not)
- [ ] Windows cashier queue (`windows_printer`) through the queue on a real Windows PC
- [ ] Phone-sized screens: placement of the **Print failed** button over the waiter layout
- [ ] Myanmar-language UI strings in the browser (added to `i18n.js`, not viewed)
- [ ] Several devices connected at once
