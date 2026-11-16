# Plan: Print Queue + Retry

Order follows the SDD sequence: spec → contract → backend → tests → UI → docs.

1. **Spec** — this folder.
2. **Contract**
   - `models.py`: `PrintJob`, `Order.print_jobs` relationship (cascade delete).
   - `schemas.py`: `PrintJobResponse`, `PrintRetryResponse`.
   - WebSocket: new event `print_job_updated`.
3. **Queue** — `services/printing/print_queue.py`
   - `PrintQueue`: per-target `asyncio.Queue` + worker, delay from `PRINT_QUEUE_DELAY_SECONDS`.
   - `run(key, work)` waits for the result (Print Test); `submit(key, work)` does not.
   - Target key helpers shared by jobs and Print Test.
4. **Jobs** — `services/printing/print_jobs.py`
   - create kitchen / receipt jobs, queue them, execute one job, requeue failed, mark interrupted, list failed.
   - Executes through the existing `dispatch_kitchen_ticket` / `dispatch_cashier_receipt` (no change to rendering or backends).
5. **Routers**
   - `routers/orders.py`: submit + checkout create and queue jobs; new `retry-print`, `print-jobs`, `print-jobs/failed`.
   - `services/printing/service.py`: `dispatch_printer_test` sends through the queue.
6. **Lifespan** — `main.py`: mark interrupted jobs failed, set the WebSocket notifier, start the queue; stop it on shutdown. The `print_jobs` table is created by `Base.metadata.create_all` (no `ALTER TABLE`).
7. **Tests** — `tests/test_print_queue.py` plus updates to tests that relied on send failures appearing in `warning`.
8. **UI** — `static/print-jobs.js` (shared), included by `waiter.html` and `counter.html`; WebSocket hook in `waiter.js` / `counter.js`; `i18n.js` strings.
9. **Docs** — `specs/api-reference.md`, `specs/database-schema.md`, `specs/tech-stack.md`, `.env.example`, `CHANGELOG.md`.

## Files
| File | Change |
|---|---|
| `models.py` | add `PrintJob`, `Order.print_jobs` |
| `schemas.py` | add `PrintJobResponse`, `PrintRetryResponse` |
| `services/printing/print_queue.py` | new |
| `services/printing/print_jobs.py` | new |
| `services/printing/service.py` | Print Test through the queue |
| `routers/orders.py` | queue instead of direct send; 3 endpoints |
| `main.py` | lifespan start/stop |
| `static/print-jobs.js` | new |
| `static/waiter.html`, `static/counter.html`, `static/waiter.js`, `static/counter.js`, `static/i18n.js` | include + WebSocket hook + strings |
| `.env.example` | `PRINT_QUEUE_DELAY_SECONDS` |
