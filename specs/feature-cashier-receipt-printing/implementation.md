# Implementation: Cashier Network Receipt Printing

## Config / registry
- `services/printing/config.py`: `CATEGORY_PRINTER_ROUTES` = drinks|food; `KNOWN_ENDPOINT_ROUTES` = drinks|food|cashier; `CASHIER_PRINTER_ROUTE = "cashier"`
- Env: `PRINTER_CASHIER_HOST`, `PRINTER_CASHIER_PORT`, `SHOP_NAME`
- Seed via `seed_kitchen_printer_settings` for all endpoint routes

## Print path
- `services/printing/receipt.py` — `build_receipt_text(...)`
- `services/printing/service.py` — `dispatch_cashier_receipt(...)`
- `backends/escpos_network.py` — `print_image_to_network` / timeout override (cashier 3s)
- Reuses `render_ticket_image`, `build_escpos_raster_payload`, file backends

## API
- `OrderCheckoutRequest.issue_receipt: bool = True`
- `OrderCheckoutResponse` extends order detail + `warning: str | None`
- `PUT/POST /api/orders/{id}/checkout` → `OrderCheckoutResponse`
- Admin kitchen-printers PUT must include drinks, food, **and** cashier routes

## Frontend
- `#checkout-issue-receipt` checkbox; payload `issue_receipt`
- Toast on `data.warning`; no `window.print()`
