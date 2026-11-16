# Requirements: Kitchen Slip Mode (per item / combined)

## Problem
Kitchen slips are printed one per order line (since 2026-11-15). Some kitchens prefer one slip that lists everything in the order batch. The restaurant must be able to choose, without a code change.

## Goal
An admin setting chooses how kitchen slips are printed when an order is submitted:

| Mode | Value | Result of one submit |
|------|-------|----------------------|
| One slip per item (default, current behaviour) | `per_item` | One slip for each submitted line |
| All items on one slip | `combined` | One slip per printer route, listing every line of that route |

## Decisions
| Topic | Decision |
|-------|----------|
| Scope of the setting | One global setting for all kitchen/bar printers |
| Default / existing installs | `per_item` (nothing changes until an admin switches) |
| Combined + two printers | Food and drinks go to different printers, so a mixed order prints one food slip and one drinks slip. They stay separate even when drinks fall back to the kitchen printer |
| When the mode is read | At submit. A slip already recorded keeps its form: **Retry** reprints it the way it was created, even if the mode changed since |
| Cancelled lines | A combined slip that is sent late or retried leaves out lines cancelled in the meantime. If every line is cancelled it is not printed |
| Receipts | Not affected |

## Functional requirements

### FR-SM1: Setting
- Column `kitchen_printer_settings.kitchen_slip_mode` `String(16) NOT NULL DEFAULT 'per_item'`; values `per_item` | `combined`.
- Existing databases get the column at startup (`ALTER TABLE … ADD COLUMN`), like earlier columns of this table.
- An unknown stored value is treated as `per_item`.

### FR-SM2: API (contract)
- `GET /api/admin/kitchen-printers` → `KitchenPrinterSettingsResponse` gains `kitchen_slip_mode`.
- `PUT /api/admin/kitchen-printers` → `KitchenPrinterSettingsUpdate` gains optional `kitchen_slip_mode`.
  - Omitted → the stored value is kept (older clients keep working).
  - Any other value → `422`.
- Roles unchanged: `ADMIN_PANEL_ROLES`.

### FR-SM3: Submit, `per_item`
- Unchanged: one `print_jobs` row per line, `order_item_id` = the line, ticket payload = one item.

### FR-SM4: Submit, `combined`
- One `print_jobs` row per printer route used by the batch (`food`, `drinks`), in order of first appearance.
- `order_item_id` is `NULL`. Ticket payload:
  `{ items: [{ order_item_id, item_name, quantity, note, selected_modifiers, is_takeaway }, …], table_number, order_id, date, batch_number }`
- Items keep submission order. Slip text is the existing combined layout (`=== KITCHEN TICKET ===`, `Batch: #N`, items separated by a rule; modifiers, notes and `(ပါဆယ်)` as on single slips; no prices).
- `OrderSubmitResponse`, order totals, batch numbering and the `new_order_batch` WebSocket event are identical in both modes.

### FR-SM5: Print queue behaviour of a combined slip
- Queued, sent, failed and retried like any other slip (`specs/feature-print-queue/`).
- At send time, lines whose order line is cancelled or gone are left out. If none remain: not sent, `failed` with `Skipped: all items were cancelled`.
- Not sent if the order is cancelled (same as single slips).
- Retry: reprints with the lines still active; counted as `skipped` when none remain.
- `GET /api/print-jobs/failed` hides a combined slip whose lines are all cancelled.
- `PrintJobResponse.item_label` for a combined slip: `"<name> x<qty>, <name> x<qty>, <name> x<qty> +N more"` (first three lines).

### FR-SM6: Admin UI
- Menu Management → Kitchen Printer Settings: **Kitchen slip** select with the two modes, saved with **Save Print Mode**.
- Applies to the next submitted order; no restart needed.

## Non-goals
- A different mode per printer.
- Letting the waiter choose per order.
- Combining food and drinks on one slip.
- Re-printing slips that were already printed when the mode changes.
