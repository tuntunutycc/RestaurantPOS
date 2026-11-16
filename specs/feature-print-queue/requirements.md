# Feature: Print Queue + Retry

## Problem
- `POST /api/orders/submit` sent every kitchen slip of a batch at the same time (`asyncio.gather`), so one order with five lines opened five simultaneous TCP connections to the same thermal printer. LAN ESC/POS printers (Xprinter) drop or merge tickets when their buffer is flooded.
- Two waiters submitting at once had the same effect.
- A failed print left no record: the reason existed only in that one HTTP response, and nothing could be reprinted.

## Goal
Every slip is recorded, sent to its printer one at a time with a pause between slips, and can be reprinted if it failed.

## Decisions (approved 2026-11-16)
| Question | Decision |
|---|---|
| Where is print status stored? | New `print_jobs` table, one row per slip. A column on `orders` cannot say which slip failed when the bar printed and the kitchen did not. |
| One queue or many? | One queue + worker **per physical printer**. A receipt must not wait behind kitchen tickets. |
| Do submit / checkout wait for the printer? | No. They return as soon as the slips are queued. |
| Pending slips after a server restart? | Marked `failed`; staff decide whether to retry. Never printed automatically. |
| Automatic retry? | No. Manual retry only (automatic retries risk duplicate kitchen tickets). |

## FR-PQ1: `print_jobs` table
One row per slip.

| Column | Notes |
|---|---|
| `id` | PK |
| `order_id` | FK `orders.id`, required |
| `order_item_id` | FK `order_items.id`; set for kitchen slips, null for receipts |
| `kind` | `kitchen` \| `receipt` |
| `route` | `food` \| `drinks` \| `cashier` |
| `printer_id` | cashier printer chosen at checkout (nullable, no FK: the printer row may be deleted later) |
| `payload` | JSON: everything needed to render the slip again |
| `print_status` | `pending` \| `printed` \| `failed` (check constraint) |
| `error_message` | reason for the last failure; null unless `failed` |
| `attempts` | number of send attempts |
| `created_at`, `updated_at`, `printed_at` | UTC |

- The printer target (IP / Windows queue) is **not** stored. It is resolved when the slip is sent, so a retry uses the printer settings as they are then (an admin may have fixed the IP).

## FR-PQ2: Queue and worker
- `asyncio.Queue` + one worker task per printer target (`lan:host:port`, `windows:queue`, `file:route`), created on first use.
- A worker sends one slip at a time and then waits `PRINT_QUEUE_DELAY_SECONDS` (default `1.0`, `0` disables the pause) before the next slip for that printer.
- Different printers work in parallel.
- Started in the FastAPI lifespan, stopped on shutdown.
- Each worker run uses its own DB session.

## FR-PQ3: Order submit
- After the order is committed: create one `pending` job per submitted line, commit, queue them. Then return.
- `OrderSubmitResponse` is unchanged. `warning` keeps the existing pre-check ("Kitchen printer offline: …") and no longer contains per-slip send failures; those arrive through FR-PQ5.
- If the jobs cannot be created or queued, the order is still saved and `warning` says the slips were not queued.

## FR-PQ4: Checkout receipt
- With `issue_receipt=true`: create one `pending` receipt job after the payment is committed, queue it, return.
- `OrderCheckoutResponse` is unchanged. `warning` is set only when the receipt could not be queued. A receipt that fails to print is reported through FR-PQ5.
- Payment is never rolled back because of printing.

## FR-PQ5: Failure handling
- Any exception while sending sets `print_status='failed'` and `error_message` (max 1000 chars). The worker keeps running.
- Success sets `print_status='printed'`, clears `error_message`, sets `printed_at`.
- A kitchen slip whose order line (or whole order) was cancelled while it waited is not printed: `failed` with `error_message` starting `Skipped:`.
- After each job the server broadcasts WebSocket event `print_job_updated` with the `PrintJobResponse` payload.
- Failures are written to `logs/printing/print.log`.

## FR-PQ6: Retry
`POST /api/orders/{order_id}/retry-print`
- Roles: `root`, `admin`, `cashier`, `waiter`.
- Re-queues every `failed` job of that order (`failed` → `pending`, `error_message` cleared) and returns immediately.
- Not re-queued (counted in `skipped`):
  - kitchen slips whose order line or order is cancelled
  - receipt jobs when the caller is a `waiter` (receipts belong to checkout roles)
- Only `failed` jobs are touched, so a double click cannot print a slip twice.
- `404` when the order does not exist. `200` with `requeued=0` when there is nothing to retry.

## FR-PQ7: Reading jobs
- `GET /api/orders/{order_id}/print-jobs` → all jobs of the order.
- `GET /api/print-jobs/failed?hours=12` → failed jobs created in the last `hours` (1–168), newest first, max 200. Skipped (cancelled) slips are excluded. A `waiter` sees kitchen jobs only.
- Roles: `root`, `admin`, `cashier`, `waiter`.

## FR-PQ8: Server restart
- The queue is in memory. On startup every job still `pending` becomes `failed` with `error_message = "Server restarted before this slip was printed"`.

## FR-PQ9: Print Test
- `POST /api/printers/{id}/test-print` goes through the same per-printer queue so it cannot collide with live slips. It still waits for the result and returns it. Test slips are not stored in `print_jobs`.

## FR-PQ10: Worker not running
- If the queue has not been started, slips are sent one after another inside the request instead of being dropped. Contract and stored statuses are the same.

## FR-PQ11: UI (waiter + counter)
- A red **Print failed (N)** button appears while failed slips exist (hidden when N = 0).
- It opens a list grouped by order: location, slip, reason, and a **Retry** button per order.
- The list loads on page load, refreshes on `print_job_updated`, and is re-read every 60 s in case the WebSocket dropped. One toast per burst of failures, not one per slip.
- A slip that fails again after **Retry** is announced again.

## Non-goals
- Automatic retry / backoff.
- Dismissing or deleting failed jobs; pruning old `print_jobs` rows.
- Detecting that paper physically came out (`printed` means the printer or spooler accepted the data).
- Kitchen "item cancelled" slips.
- More than one server process. The queue lives in one process; running several workers (`uvicorn --workers N`) would give each its own queue for the same printer.
