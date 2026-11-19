# Requirements: Cashier Network Receipt Printing

## Purpose
Print checkout receipts on a **LAN thermal printer** from the server, reusing the kitchen image/ESC/POS pipeline (Pillow + Myanmar fonts + TCP `:9100`). Browser `window.print()` is retired for cashier receipts.

Multi-cashier terminals share one (or more) network receipt printers configured in DB — not each browser’s local printer.

## Receipt texts
The shop name, address, phone, thank-you line and footer note on the receipt are edited by an admin (`specs/feature-receipt-text/`). Nothing set = the original receipt (`SHOP_NAME`, `Thank you!`).

## Explicit non-goals
- Do **not** change tax math when skipping a print (`issue_receipt=false` only skips paper; line/order tax unchanged).
- Do **not** fail checkout if the printer is offline.
- Do **not** use kitchen category routes (`drinks` / `food`) for receipts — receipts use endpoint route **`cashier`**.

## Actors
| Role | Capability |
|------|------------|
| Admin | Configure `cashier` host/port via `GET/PUT /api/admin/kitchen-printers` (same settings singleton + `PrinterRouteEndpoint`) |
| Cashier / checkout roles | Checkout with `issue_receipt`; a failed receipt shows in **Print failed** and can be retried |
| System | After paid commit, optional in-request TCP print (short timeout) |

## FR-CR1: Cashier printers (via unified Printer table)
- Rows in **`printers`** with `role=cashier`: `id`, `name`, `host`, `port`, `is_active`
- Seeded as **Default Cashier Printer** on fresh install (with Default Kitchen)
- Admin CRUD: `POST/PUT/DELETE /api/printers` (any role including cashier)
- Shares `KitchenPrinterSettings` backend / render_mode / paper_width_px

## FR-CR1b: Terminal printer selection
- **API list:** `GET /api/printers?role=cashier` → active cashier printers for the terminal dropdown
- **Checkout:** `OrderCheckoutRequest.printer_id: int | null` (optional)
  - When `issue_receipt=true`: selected cashier printer, else first active cashier printer
  - When `issue_receipt=false` → no print
- **Frontend:** `#cashier-printer-select` + `localStorage.selectedCashierPrinterId`

## FR-CR2: Checkout request — `issue_receipt`
- `OrderCheckoutRequest.issue_receipt: bool` (default **`true`**)
- Cashier UI: **Print Receipt** checkbox (checked by default)
- When `false`: payment succeeds; **no** network/file receipt dispatch

## FR-CR3: Checkout workflow
1. Validate tender / discounts; persist `status=paid` + payment fields; free table if dine-in; WebSocket broadcasts
2. If `issue_receipt`:
   - Resolve target: `printer_id` → that cashier `Printer`, else first active `role=cashier`
   - Build receipt text … render … send (file or TCP 3s)
3. Return **`200`** without waiting for the printer (see `specs/feature-print-queue/`)
   - The receipt is stored as a `print_jobs` row and queued for its printer
   - A failed print sets `print_status='failed'` + `error_message` (real cause: unreachable host, missing Windows queue name, spooler error, …), is broadcast as `print_job_updated`, and is written to `logs/printing/print.log`
   - `warning` = `Receipt was not printed: <reason>` only when the receipt could not be queued at all

## FR-CR4: Shop name
- `SHOP_NAME` env var; fallback **`My Restaurant`**

## FR-CR5: Frontend
- Check Out pane / cashier header: printer `<select id="cashier-printer-select">` + Print Receipt checkbox
- Persist selection in `localStorage.selectedCashierPrinterId`
- Checkout body includes `printer_id` when printing
- On success + `warning`: toast shows the translated notice **plus** the server `warning` text; no browser `window.print()`
- A receipt that fails to print: toast + **Print failed (N)** button with **Retry** (`static/print-jobs.js`)

## FR-CR6: Line-level takeaway marker
- When a receipt line has `is_takeaway=true`, append ` (ပါဆယ်)` to the item name on the same line. See `specs/feature-menu-pricing/` FR-P6.
- Cashier checkout UI shows a takeaway/ပါဆယ် badge on those lines.

## FR-CR7: Receipt text file archive
- Every cashier receipt dispatch appends the plain-text receipt to `cashier_printer_output.txt` under the print output dir (`KITCHEN_PRINT_OUTPUT_DIR`, same as kitchen).
- Archive happens for **all** backends (`file`, `escpos_network`, `windows_printer`) so Windows/LAN prints still leave a readable txt copy (mirrors kitchen `food_printer_output.txt` / `drinks_printer_output.txt` when those use file).
- File backend must not double-append the same receipt text.
- **No physical printer:** backend `file` + cashier `Printer` with empty `host` must still succeed and write the txt (do not treat missing host as “printer not found”). Network backend still requires `host:port`.

## FR-CR8: Receipt money footer breakdown
- Printed receipt (and cashier checkout pane) footer must use:
  - **Subtotal** = Σ `(unit_price_at_sale + modifiers) × qty` (before item discount)
  - **Discount** = Σ `unit_discount_at_sale × qty` + checkout order-level discount
  - **Tax** = Σ `unit_tax_at_sale × qty`
  - **Grand Total** = payable charged = Σ line `subtotal` − order-level discount
- Identity: `Subtotal − Discount + Tax = Grand Total` (when order-level discount is included in Discount).
- Do **not** label tax-inclusive line totals as “Subtotal” while also listing Tax again (that made Grand look wrong).
- **Per-line amount on receipt / checkout pane** = pre-tax (`line.subtotal − unit_tax × qty`), matching review #18.
- **Line notes** (`note` / special instructions) print under the item on the receipt (review #24), same idea as kitchen `*** Note: … ***`.
- Payment / tender validation stays on tax-inclusive line subtotals (unchanged).

## Related
- `specs/feature-kitchen-printing/` — shared render/backends
- `specs/feature-payment-method-analytics/` — payment method on receipt
- `specs/feature-cashier-three-pane/` — Check Out pane checkbox placement
- `specs/feature-menu-pricing/` — `is_takeaway` pricing + visibility
