# Implementation: Cashier Network Receipt Printing + Terminal Selection

## Multi-cashier architecture
- **`cashier_printers`** (`CashierPrinter`): `id`, `name`, `host`, `port`, `is_active`
- Seeded when empty from legacy `PrinterRouteEndpoint(route_key=cashier)` / `PRINTER_CASHIER_*`
- Legacy `cashier` route remains in kitchen-printer settings (fallback + admin kitchen UI)
- Kitchen `drinks`/`food` dispatch unchanged

## Config / registry
- `services/printing/config.py`: `CATEGORY_PRINTER_ROUTES` = drinks|food; `KNOWN_ENDPOINT_ROUTES` = drinks|food|cashier; `CASHIER_PRINTER_ROUTE = "cashier"`
- Env: `PRINTER_CASHIER_HOST`, `PRINTER_CASHIER_PORT`, `SHOP_NAME`
- `seed_kitchen_printer_settings` + `seed_cashier_printers`

## Print path
- `services/printing/receipt.py` — `build_receipt_text(...)`
- `services/printing/service.py` — `dispatch_cashier_receipt(..., printer_id=...)`; always archives cashier text (FR-CR7)
- Checkout passes FR-CR8 footer amounts from `_order_price_breakdown` + order-level discount
- Cashier pane `recalculateCheckoutTotals` uses the same breakdown for display; tender still on line subtotals
- `backends/escpos_network.py` — cashier TCP timeout 3s
- Reuses kitchen image/ESC/POS/file backends

## API
- `OrderCheckoutRequest.issue_receipt: bool = True`
- `OrderCheckoutRequest.printer_id: int | None = None`
- `OrderCheckoutResponse` + `warning: str | None`
- `GET /api/printers?role=cashier` — active printers for terminal dropdown (`POS_ORDER_ROLES` / checkout roles)
- `GET/PUT /api/admin/cashier-printers` — admin manage named printers
- `PUT/POST /api/orders/{id}/checkout` — when `issue_receipt`, resolve printer by `printer_id` or first active

## Frontend
- `#cashier-printer-select` + `localStorage.selectedCashierPrinterId`
- `#checkout-issue-receipt`; checkout body includes `printer_id` when printing
- Toast on `data.warning`; no `window.print()`
