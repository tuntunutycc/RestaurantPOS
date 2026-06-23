# Feature Plan: Kitchen LAN Printing (Phase 1 - Step 9)

## Objective
Implement category-routed kitchen ticket printing with:
- admin category → printer route (`drinks` | `food`)
- admin-managed DB settings → LAN IP:port per route, with optional env fallback
- file backend for dev/test
- ESC/POS network backend for Xprinter production
- bundled Myanmar font support for image-rendered tickets
- non-blocking print failures on order submit

## Scope
- Backend: printing service module, orders submit integration
- Backend: category `printer_route` column + schema/API updates
- Frontend: admin category form in counter menu panel
- Tests: routing, default fallback, submit non-blocking behavior
- Docs: `.env.example`, README section, CHANGELOG, roadmap Step 9
- Assets: bundled Myanmar-capable print font under `assets/fonts/`

## Out of Scope
- Menu-item-level routing
- PostgreSQL/Alembic migration tooling (use existing runtime ALTER pattern)
- Bluetooth/USB printer support
- Print retry/dead-letter persistence

## Implementation Steps

### 1) Spec + contract (this folder)
- Finalize requirements/validation checklists.
- Extend `schemas.py` category models with `printer_route`.

### 2) Database / model
- Add `Category.printer_route` (nullable String) in `models.py`.
- Add startup migration in `main.py` lifespan (`ALTER TABLE` if missing).
- Default existing categories to NULL (server resolves to food).

### 3) Category API + validation
- Update `routers/menu.py` category create/update/list to read/write `printer_route`.
- Validate allowed literals: `drinks`, `food`, or null.
- Return field in `CategoryResponse`.

### 4) Printing service module (new)
Create `services/printing/`:
- `config.py` — load env, build route registry
- `routes.py` — resolve category route → `food` default, unknown → food + warn
- `ticket.py` — build plain text + ESC/POS payload (single item)
- `backends/file.py` — append to route output files
- `backends/escpos_network.py` — TCP socket send
- `service.py` — `dispatch_kitchen_ticket(route, ticket_data)` async-safe

Replace `mock_send_to_printer` usage in `routers/orders.py`.

### 5) Order submit integration
- In `submit_order`, after DB commit + WS broadcast:
  - build per-item ticket payload from persisted line + category route
  - dispatch via `asyncio.gather(..., return_exceptions=True)`
- Remove category-slug filename logic (`_printer_name_for_category` mock naming).

### 6) Admin UI (counter)
- In `static/counter.js` / `counter.html` category create/edit:
  - add printer route dropdown: Default (Food) / Drinks / Food
- Map "Default (Food)" → null in API payload
- i18n keys in `static/i18n.js` if needed

### 7) Automated tests
Add `tests/test_kitchen_printing.py`:
- category route drinks → drinks file backend output
- null route → food backend output
- mixed items in one submit → both outputs
- invalid route in DB → food fallback
- forced backend exception → submit still 200
- category API contract includes `printer_route`

### 8) Documentation + roadmap
- Update `specs/roadmap.md`: Step 9 entry
- Update `CHANGELOG.md` after tests green
- Add `.env.example` printer vars

### 9) Image render settings contract
- Extend printer settings schemas:
  - `render_mode: Literal["text", "image"]`
  - `paper_width_px: int` (384 or 576)
- Extend `kitchen_printer_settings` model/table:
  - `render_mode`
  - `paper_width_px`
- Add startup migrations in `main.py`.

### 10) Ticket renderer abstraction
- Keep current `build_ticket_text()`.
- Add image rendering module:
  - `services/printing/image_renderer.py`
- Responsibilities:
  - render ticket text with a Myanmar-capable configured or bundled font when available
  - auto-discover bundled fonts from `assets/fonts/` / `static/fonts/`
  - output monochrome image bytes/PNG
  - use configured width
  - fall back gracefully when configured font is missing

### 11) ESC/POS raster builder
- Split payload builders into:
  - text ESC/POS payload
  - raster image ESC/POS payload
- Keep current text behavior as `text` mode.

### 12) Backend dispatch integration
- Update `dispatch_kitchen_ticket()`:
  - read `render_mode`
  - if `text`: current flow
  - if `image`: render image then send raster bytes
- File backend:
  - text mode writes `.txt`
  - image mode writes `.png`
- Network backend:
  - text mode sends text ESC/POS
  - image mode sends raster ESC/POS

### 13) Admin UI settings
- Extend Counter → Menu → Kitchen Printer Settings:
  - render mode dropdown
  - paper width selector/input
- Persist via existing `GET/PUT /api/admin/kitchen-printers`.

### 14) Tests
- Add tests for:
  - default render mode is text
  - settings API accepts image mode + 384/576
  - file backend image mode creates PNG
  - bundled Myanmar font auto-discovery
  - raster payload is non-empty
  - render failure does not fail submit

### 15) Bundled font asset
- Add `assets/fonts/NotoSansMyanmar-Regular.ttf`.
- Include the upstream OFL license as `assets/fonts/OFL-NotoSansMyanmar.txt`.
- Keep `.env` font path optional for deployments that want to override the bundled font.

## Delivery Criteria
- Admin can configure category printer route from counter UI.
- Submit prints one ticket per item to correct route.
- File backend enables dev without printer.
- ESC/POS network backend ready for Xprinter LAN IP config.
- Image render mode supports Myanmar-friendly ticket output through server-rendered raster images.
- Bundled Noto Sans Myanmar font enables image mode without `.env` font configuration.
- pytest green; validation checklist complete.

## Implementation Trace (Current Code)

### Data Model / Runtime Migration
- `models.py`
  - `Category.printer_route`
  - `KitchenPrinterSettings.backend`
  - `KitchenPrinterSettings.render_mode`
  - `KitchenPrinterSettings.paper_width_px`
  - `PrinterRouteEndpoint.route_key`, `host`, `port`
- `main.py`
  - runtime SQLite migrations add `categories.printer_route`
  - runtime SQLite migrations add printer settings columns
  - startup seeds singleton kitchen printer settings and route endpoint rows

### API Contracts
- `schemas.py`
  - `PrinterRouteLiteral = "drinks" | "food"`
  - `PrinterBackendLiteral = "file" | "escpos_network"`
  - `PrinterRenderModeLiteral = "text" | "image"`
  - `KitchenPrinterSettingsResponse/Update`
- `routers/kitchen_printers.py`
  - `GET /api/admin/kitchen-printers`
  - `PUT /api/admin/kitchen-printers`
  - admin-only via `require_roles(["admin"])`
- `routers/menu.py`
  - category create/update returns and persists `printer_route`

### Dispatch Flow
1. Waiter/cashier/admin submits `POST /api/orders/submit`.
2. `routers/orders.py` persists order/items and broadcasts `new_order_batch`.
3. For each submitted item, category `printer_route` is normalized by `resolve_printer_route()`.
4. `dispatch_kitchen_ticket()` loads printer settings from DB via `load_printer_config()`.
5. `build_ticket_text()` creates one-item ticket text.
6. Dispatch branches:
   - `backend=file`, `render_mode=text` -> route `.txt` output
   - `backend=file`, `render_mode=image` -> route `.png` preview
   - `backend=escpos_network`, `render_mode=text` -> ESC/POS text bytes over TCP
   - `backend=escpos_network`, `render_mode=image` -> ESC/POS raster bytes over TCP
7. Print exceptions stay isolated by the `asyncio.gather(..., return_exceptions=True)` call in order submit.

### Printing Modules
- `services/printing/config.py`
  - route constants and `PrinterConfig`
- `services/printing/settings.py`
  - DB-backed config loader
  - env fallback for first seed and missing route hosts
- `services/printing/routes.py`
  - `None`, empty, unknown -> `food`
- `services/printing/ticket.py`
  - ticket text builder
  - ESC/POS text payload builder
  - ESC/POS raster payload builder (`GS v 0`)
- `services/printing/image_renderer.py`
  - Pillow-based 1-bit image renderer
  - font lookup: `KITCHEN_PRINT_FONT_PATH`, bundled fonts, system fallback, Pillow default
- `services/printing/backends/file.py`
  - text `.txt` output
  - image `.png` output
- `services/printing/backends/escpos_network.py`
  - raw TCP send to configured LAN host/port

### Frontend
- `static/counter.html`
  - Kitchen Printer Settings panel
  - backend selector, render mode selector, paper width selector, route host/port inputs
  - category printer route selector
- `static/counter.js`
  - loads/saves `GET/PUT /api/admin/kitchen-printers`
  - loads/saves category route mappings

### Automated Tests
- `tests/test_kitchen_printing.py`
  - route normalization
  - category API contract and invalid route rejection
  - file backend text routing
  - unknown route fallback
  - print failure does not fail submit
  - file backend image mode writes PNG
  - bundled Myanmar font auto-discovery
  - ESC/POS raster payload is non-empty
  - settings API includes backend/render mode/paper width/route endpoints and admin RBAC

## Configuration Precedence
- Admin UI / DB settings are the normal production source of truth.
- `.env` is used for:
  - first-time seed defaults (`PRINTER_BACKEND`, `PRINTER_RENDER_MODE`, `PRINTER_PAPER_WIDTH_PX`)
  - route host fallback when DB host is empty (`PRINTER_DRINKS_HOST`, `PRINTER_FOOD_HOST`)
  - file backend output directory (`KITCHEN_PRINT_OUTPUT_DIR`)
  - optional image renderer font override (`KITCHEN_PRINT_FONT_PATH`)
- Bundled `assets/fonts/NotoSansMyanmar-Regular.ttf` is used automatically when no font override is configured.

## Debugging Notes
- If no file appears in file mode:
  - confirm `backend=file`
  - confirm category route is set or defaults to `food`
  - check `KITCHEN_PRINT_OUTPUT_DIR`; default is process working directory
- If Myanmar text prints as Chinese/garbled in text mode:
  - use `render_mode=image`
- If Myanmar image output shows square boxes:
  - confirm `assets/fonts/NotoSansMyanmar-Regular.ttf` exists
  - confirm server was restarted after adding/updating the font
  - use `KITCHEN_PRINT_FONT_PATH` only if overriding the bundled font
- If image mode prints too narrow/wide:
  - use `384` for 58mm printers
  - use `576` for 80mm printers
- If LAN printer does not print:
  - confirm `backend=escpos_network`
  - confirm route host/port in admin UI
  - confirm printer is reachable from the POS server on TCP port 9100
- If order submit succeeds but nothing prints:
  - this is expected failure isolation; inspect server logs for printing errors
