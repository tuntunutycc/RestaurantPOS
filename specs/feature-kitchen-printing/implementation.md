# Implementation Reference: Kitchen LAN Printing

This document records how the kitchen printing feature is wired in code so future maintainers can debug or extend it without re-discovering the flow.

## 1. Current Capability

- Category-level kitchen routing:
  - `drinks`
  - `food`
  - null/empty/unknown falls back to `food`
- Backends:
  - `file`
  - `escpos_network`
- Render modes:
  - `text`
  - `image`
- Bundled print font:
  - `assets/fonts/NotoSansMyanmar-Regular.ttf`
  - `assets/fonts/OFL-NotoSansMyanmar.txt`
  - `assets/fonts/NotoSans-Regular.ttf`
  - `assets/fonts/OFL-NotoSans.txt`
- Route settings:
  - Admin UI / DB is the source of truth
  - `.env` can seed defaults and provide fallback host values
- Print failures do not fail order submit.

## 2. Data Model

### `Category`

Field:
- `printer_route`

Purpose:
- Determines which kitchen printer route receives submitted item tickets.

Rules:
- `drinks` -> drinks printer route
- `food` -> food printer route
- `null`, empty, or unsupported value -> food route

### `KitchenPrinterSettings`

Singleton row: `id = 1`

Fields:
- `backend`
  - `file`
  - `escpos_network`
- `render_mode`
  - `text`
  - `image`
- `paper_width_px`
  - `384` for 58mm printers
  - `576` for 80mm printers

### `PrinterRouteEndpoint`

Fields:
- `route_key`
- `host`
- `port`

Purpose:
- Stores LAN endpoint per route.

Example:
- `drinks` -> `192.168.1.101:9100`
- `food` -> `192.168.1.102:9100`

## 3. API Contract

### Category Contract

Files:
- `schemas.py`
- `routers/menu.py`

Contracts:
- `CategoryCreate.printer_route`
- `CategoryUpdate.printer_route`
- `CategoryResponse.printer_route`

Endpoints:
- `POST /api/categories/`
- `GET /api/categories/`
- `PUT /api/categories/{category_id}`

### Printer Settings Contract

Files:
- `schemas.py`
- `routers/kitchen_printers.py`

Endpoints:
- `GET /api/admin/kitchen-printers`
- `PUT /api/admin/kitchen-printers`

RBAC:
- admin only

Payload shape:

```json
{
  "backend": "file",
  "render_mode": "image",
  "paper_width_px": 576,
  "routes": [
    {"route_key": "drinks", "host": "192.168.1.101", "port": 9100},
    {"route_key": "food", "host": "192.168.1.102", "port": 9100}
  ]
}
```

## 4. Order Submit Flow

File:
- `routers/orders.py`

Flow:
1. `POST /api/orders/submit`
2. Validate table/order/items.
3. Create or append order batch.
4. Snapshot item name/price/category at sale time.
5. Commit order and order items.
6. Broadcast `new_order_batch`.
7. Build one print job per submitted line item.
8. Resolve route from item category using `resolve_printer_route()`.
9. Dispatch each ticket with `dispatch_kitchen_ticket()`.
10. Return `OrderSubmitResponse`.

Important invariant:
- Print happens after DB commit and is isolated with `asyncio.gather(..., return_exceptions=True)`.
- If printing fails, the order remains successfully submitted.

## 5. Printing Module Map

### `services/printing/config.py`

Contains:
- route constants
- dataclasses:
  - `PrinterConfig`
  - `PrinterEndpoint`
- output filename helpers

Use when:
- Adding a route constant
- Adding shared config fields

### `services/printing/settings.py`

Contains:
- DB settings seeding
- DB-backed printer config loader
- env fallback behavior

Use when:
- Debugging why a host/port/backend/render mode was chosen
- Changing config precedence

Config precedence:
1. Existing DB values
2. Env fallback for missing route host
3. Env values only for first-time seed defaults

Relevant env vars:
- `PRINTER_BACKEND`
- `PRINTER_RENDER_MODE`
- `PRINTER_PAPER_WIDTH_PX`
- `PRINTER_DRINKS_HOST`
- `PRINTER_DRINKS_PORT`
- `PRINTER_FOOD_HOST`
- `PRINTER_FOOD_PORT`
- `KITCHEN_PRINT_OUTPUT_DIR`
- `KITCHEN_PRINT_FONT_PATH`

Note:
- `KITCHEN_PRINT_FONT_PATH` is optional because the repository bundles `assets/fonts/NotoSansMyanmar-Regular.ttf`.

### `services/printing/routes.py`

Contains:
- `resolve_printer_route()`

Rules:
- `None` -> `food`
- empty string -> `food`
- known value -> itself
- unknown value -> warning log + `food`

### `services/printing/ticket.py`

Contains:
- `build_ticket_text()`
- `build_escpos_text_payload()`
- `build_escpos_raster_payload()`

Text mode:
- Sends UTF-8 text bytes to ESC/POS.
- Some printers may render Myanmar incorrectly in this mode.

Image mode:
- Converts rendered 1-bit image into ESC/POS `GS v 0` raster payload.

### `services/printing/image_renderer.py`

Contains:
- `render_ticket_image()`

Purpose:
- Render ticket text server-side using Pillow.
- Convert ticket to 1-bit image for thermal printing.

Font lookup:
1. `KITCHEN_PRINT_FONT_PATH`
2. preferred bundled filenames in `assets/fonts/`
3. preferred bundled filenames in `static/fonts/`
4. any bundled `*Myanmar*.ttf`, `*Myanmar*.otf`, `*Pyidaungsu*.ttf`, or `*Pyidaungsu*.otf`
5. bundled Latin/symbol fallback fonts such as `NotoSans-Regular.ttf`
6. common system fallback paths
7. Pillow default font

Recommendation:
- Bundle `assets/fonts/NotoSansMyanmar-Regular.ttf` for consistent Myanmar output without `.env` font configuration.
- Bundle `assets/fonts/NotoSans-Regular.ttf` to reduce square boxes for English labels, digits, and punctuation.
- `KITCHEN_PRINT_FONT_PATH` remains available when a deployment wants to use an external system font.

### `services/printing/backends/file.py`

Text mode output:
- `drinks_printer_output.txt`
- `food_printer_output.txt`

Image mode output:
- `drinks_printer_output.png`
- `food_printer_output.png`

Use when:
- Developing without physical printers
- Verifying image render width and layout

### `services/printing/backends/escpos_network.py`

Contains:
- raw TCP send to configured printer LAN endpoint

Assumptions:
- Xprinter/ESC/POS compatible device
- port commonly `9100`
- POS server can reach printer IP

## 6. Frontend Map

Files:
- `static/counter.html`
- `static/counter.js`

Counter -> Menu contains:
- Kitchen Printer Settings
  - backend
  - render mode
  - paper width
  - drinks host/port
  - food host/port
- Category printer route controls

If settings do not appear:
- confirm logged-in user is admin
- confirm counter JS loaded without console errors
- confirm `/api/admin/kitchen-printers` returns `200`

## 7. Testing Map

Primary tests:
- `tests/test_kitchen_printing.py`

Coverage:
- route resolver defaults/unknown fallback
- category API contract
- invalid category route -> `422`
- text file backend output
- image file backend PNG output
- raster payload byte structure
- bundled Myanmar font auto-discovery
- bundled Latin fallback routing
- print failure does not fail order submit
- printer settings API and RBAC

Validation command:

```bash
PYTHONPATH=. venv/bin/python -m pytest -q
```

Latest known result:
- `44 passed`

## 8. Debugging Playbook

### Problem: Myanmar prints as Chinese/garbled

Likely cause:
- Printer is interpreting UTF-8 text bytes as another code page.

Fix:
- Set render mode to `image`.
- Confirm bundled `assets/fonts/NotoSansMyanmar-Regular.ttf` exists.
- Restart the server after adding/updating bundled fonts.
- Use `KITCHEN_PRINT_FONT_PATH` only when overriding the bundled font.

### Problem: Myanmar image output shows square boxes

Likely cause:
- Image mode is active, but the renderer used a font without Myanmar glyphs.

Fix:
- Confirm `assets/fonts/NotoSansMyanmar-Regular.ttf` exists and is a valid TrueType font.
- Confirm `assets/fonts/NotoSans-Regular.ttf` exists and is a valid TrueType font.
- Restart the server so Pillow reloads the bundled font.
- Check logs for `Loaded kitchen print font`.
- If using a custom font, set `KITCHEN_PRINT_FONT_PATH` to its absolute path.

### Problem: English labels, numbers, or punctuation show as square boxes

Likely cause:
- Myanmar font is active, but no Latin/symbol fallback font is available.

Fix:
- Confirm `assets/fonts/NotoSans-Regular.ttf` exists.
- Restart the server after adding the fallback font.
- Keep render mode as `image`.

### Problem: PNG output not created in file mode

Check:
- backend is `file`
- render mode is `image`
- category route exists or defaults to food
- process working directory or `KITCHEN_PRINT_OUTPUT_DIR`

### Problem: LAN printer does not print

Check:
- backend is `escpos_network`
- correct route host/port in admin UI
- printer static IP did not change
- server can reach printer IP on port 9100
- route selected on category matches item category

### Problem: Order submits but no print

This can be expected by design:
- printing is non-blocking
- inspect server logs for route/host/font/socket errors

### Problem: Image too wide or clipped

Check:
- `384` for 58mm printer
- `576` for 80mm printer

## 9. Extension Notes

To add a new route, such as `bar`:
1. Extend `KNOWN_PRINTER_ROUTES`.
2. Extend `PrinterRouteLiteral`.
3. Add UI options where needed.
4. Update validation tests.
5. Update this document and specs.

To add per-item overrides:
1. Add `MenuItem.printer_route` or a dedicated override field.
2. Define precedence: item override -> category route -> default food.
3. Extend schemas/API/UI/tests.
4. Keep historical sale snapshots stable.

To improve Myanmar rendering:
1. Replace or add fonts under `assets/fonts/`.
2. Prefer `NotoSansMyanmar-Regular.ttf` for default auto-discovery.
3. Prefer `NotoSans-Regular.ttf` for Latin/digit/symbol fallback.
4. Use `KITCHEN_PRINT_FONT_PATH` only for deployment-specific overrides.
5. If shaping is still wrong, consider a renderer with stronger complex-script support.
