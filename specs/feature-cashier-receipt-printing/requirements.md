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

## FR-CR1: Cashier printer endpoint
- `PrinterRouteEndpoint.route_key = cashier`
- Seeded on startup like drinks/food; env fallback:
  - `PRINTER_CASHIER_HOST` / `PRINTER_CASHIER_PORT` (default port `9100`)
- Shares `KitchenPrinterSettings.backend` / `render_mode` / `paper_width_px` with kitchen (image mode recommended for Myanmar).

## FR-CR2: Checkout request — `issue_receipt`
- `OrderCheckoutRequest.issue_receipt: bool` (default **`true`**)
- Cashier UI: **Print Receipt** checkbox (checked by default)
- When `false`: payment succeeds; **no** network/file receipt dispatch

## FR-CR3: Checkout workflow
1. Validate tender / discounts; persist `status=paid` + payment fields; free table if dine-in; WebSocket broadcasts
2. If `issue_receipt`:
   - Build receipt text (shop name, order id, served by, items, subtotal, discount, tax, grand total, payment method, tendered, change)
   - Render via existing `render_ticket_image` when `render_mode=image`, else ESC/POS text
   - Send to `cashier` route (`file` → `cashier_printer_output.txt|.png`; `escpos_network` → TCP)
   - TCP timeout **3 seconds** for cashier receipt attempts
3. Return **`200`** with checkout payload; on print failure set `warning` (e.g. `"Receipt printer offline or unreachable"`)

## FR-CR4: Shop name
- `SHOP_NAME` env var; fallback **`My Restaurant`**

## FR-CR5: Frontend
- Remove `#receipt-print` DOM and `@media print` CSS; remove `window.print()` / `renderReceiptForPrint`
- On success + `warning`: toast (non-blocking) so cashier knows paper did not print
- On success without warning: existing success feedback

## Related
- `specs/feature-kitchen-printing/` — shared render/backends
- `specs/feature-payment-method-analytics/` — payment method on receipt
- `specs/feature-cashier-three-pane/` — Check Out pane checkbox placement
