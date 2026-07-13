# Requirements: Cashier Network Receipt Printing

## Purpose
Print checkout receipts on a **LAN thermal printer** from the server, reusing the kitchen image/ESC/POS pipeline (Pillow + Myanmar fonts + TCP `:9100`). Browser `window.print()` is retired for cashier receipts.

Multi-cashier terminals share one (or more) network receipt printers configured in DB — not each browser’s local printer.

## Explicit non-goals
- Do **not** change tax math when skipping a print (`issue_receipt=false` only skips paper; line/order tax unchanged).
- Do **not** fail checkout if the printer is offline.
- Do **not** use kitchen category routes (`drinks` / `food`) for receipts — receipts use endpoint route **`cashier`**.

## Actors
| Role | Capability |
|------|------------|
| Admin | Configure `cashier` host/port via `GET/PUT /api/admin/kitchen-printers` (same settings singleton + `PrinterRouteEndpoint`) |
| Cashier / checkout roles | Checkout with `issue_receipt`; see API `warning` if print fails |
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
3. Return **`200`**; print failure → `warning` only

## FR-CR4: Shop name
- `SHOP_NAME` env var; fallback **`My Restaurant`**

## FR-CR5: Frontend
- Check Out pane / cashier header: printer `<select id="cashier-printer-select">` + Print Receipt checkbox
- Persist selection in `localStorage.selectedCashierPrinterId`
- Checkout body includes `printer_id` when printing
- On success + `warning`: toast; no browser `window.print()`

## Related
- `specs/feature-kitchen-printing/` — shared render/backends
- `specs/feature-payment-method-analytics/` — payment method on receipt
- `specs/feature-cashier-three-pane/` — Check Out pane checkbox placement
