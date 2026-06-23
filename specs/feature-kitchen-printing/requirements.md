# Requirements: Kitchen LAN Printing (Phase 1 - Step 9)

## 1. Purpose
Replace mock file-only kitchen printing with a configurable, category-routed
kitchen ticket dispatch system suitable for Xprinter (ESC/POS over LAN).

Admin assigns each menu category to a printer route (`drinks` or `food`).
Server resolves route → LAN IP:port and prints one ticket per submitted line item.

## 2. Actors and Permissions

### 2.1 Admin
- Can set `printer_route` on categories via menu/category admin UI.
- Allowed values (v1): `drinks`, `food`, or empty/null (defaults to `food`).

### 2.2 Waiter / Cashier
- No direct printer configuration access.
- Trigger printing indirectly via `POST /api/orders/submit`.

### 2.3 System (Server)
- Loads printer hardware endpoints from admin-managed DB settings, with environment fallback.
- Dispatches tickets after successful order persist + WebSocket broadcast.

## 3. Functional Requirements

### FR-1: Category Printer Route (Admin-configurable)
- Each `Category` may have optional `printer_route`.
- Admin can create/update category with `printer_route`.
- v1 allowed route literals: `drinks`, `food`.
- Empty/null `printer_route` resolves to `food`.

### FR-2: Order Submit Triggers Kitchen Print
- On successful `POST /api/orders/submit`, each new line item in the batch
  generates exactly one kitchen ticket.
- Ticket dispatch occurs after DB commit (order/items persisted).

### FR-3: Route Resolution
- For each submitted line item:
  1. Read item's category `printer_route` (fallback `food` if null/empty).
  2. Normalize unknown route names → `food` + log warning.
  3. Resolve route to configured printer endpoint (host + port).

### FR-4: LAN ESC/POS Printing (Production mode)
- When `PRINTER_BACKEND=escpos_network`:
  - Send ESC/POS bytes to printer via TCP (default port 9100).
  - Support at least two routes:
    - `drinks` → `PRINTER_DRINKS_HOST`:`PRINTER_DRINKS_PORT`
    - `food` → `PRINTER_FOOD_HOST`:`PRINTER_FOOD_PORT`

### FR-5: File Backend (Development / No-printer mode)
- When `PRINTER_BACKEND=file`:
  - Append ticket text to route-specific files:
    - `drinks` → `drinks_printer_output.txt`
    - `food` → `food_printer_output.txt`
  - No physical printer required for tests/dev.

### FR-6: Ticket Content (Single-item)
Each ticket must include:
- Route/printer label (for debugging in file mode)
- Dine-in: table number OR Takeaway: customer header block
- Order ID, timestamp
- Quantity × item name (Myanmar/Unicode as stored in menu)
- Note/special instructions (if present)
- Cut marker / ESC/POS cut command

### FR-7: Non-blocking Print Failures (Critical)
- Print failures must NOT fail order submit.
- Order submit API returns success if DB + business rules succeed.
- Print errors are logged; async dispatch uses exception isolation.

### FR-8: Extensible Route Registry
- Route registry must be data-driven (not hardcoded only in dispatch calls).
- v1 registers `drinks` and `food`.
- Future routes can be added via registry + env without rewriting order logic.

### FR-9: Image Rendering Mode for Myanmar Tickets
- System supports `render_mode = text | image`.
- `text` mode keeps the existing ESC/POS text behavior.
- `image` mode renders the kitchen ticket on the server as a monochrome image before printing.
- Image mode is intended for Myanmar Unicode text on printers that cannot render Myanmar code pages.
- Image mode must preserve existing one-item-one-ticket behavior.

### FR-10: Render Settings
- Admin can configure:
  - `render_mode`: `text` or `image`
  - `paper_width_px`: `384` for 58mm or `576` for 80mm
- Defaults:
  - `render_mode = text`
  - `paper_width_px = 576`

### FR-11: File Backend Image Preview
- In `file` backend + `text` mode, system writes `.txt` ticket output as today.
- In `file` backend + `image` mode, system writes PNG preview files:
  - `drinks_printer_output.png`
  - `food_printer_output.png`

### FR-12: ESC/POS Raster Image Output
- In `escpos_network` backend + `image` mode, system sends ESC/POS raster image bytes.
- Payload includes printer init, raster image command, feed, and cut command.

### FR-13: Font Handling
- Image rendering should use a configured or bundled Myanmar-capable font when available.
- Bundled font discovery must support `assets/fonts/` and `static/fonts/` so deployments can work without `.env` font paths.
- Preferred bundled filename: `NotoSansMyanmar-Regular.ttf`.
- Repository includes `assets/fonts/NotoSansMyanmar-Regular.ttf` and its OFL license for default Myanmar image rendering.
- If no configured font is available, renderer falls back to a system/default font so tests and ASCII tickets still work.
- Missing or unusable font must be logged clearly.

## 4. Business Logic Rules

### BL-1: Default Route
- `printer_route` null/empty/whitespace → `food`.

### BL-2: Unknown Route Fallback
- If category has unsupported `printer_route` value, treat as `food` and log warning.

### BL-3: Submit Integrity over Print Reliability
- Printing is a side effect; order state and totals are authoritative in DB.

### BL-4: One Item, One Ticket
- No batch-combined kitchen ticket in v1.

### BL-5: Server-side Only
- Printing is executed on POS server, not client WebView/browser.

### BL-6: Render Mode Safety
- Printing remains a side effect.
- Image render failures do not roll back orders.
- Text mode remains the compatibility fallback.

### BL-7: Paper Width
- `paper_width_px` controls rendered image width.
- Supported presets:
  - `384` for 58mm
  - `576` for 80mm

## 5. API / Contract Requirements

### 5.1 Category APIs (contract extension)
- `CategoryCreate`, `CategoryUpdate`, `CategoryResponse` include optional
  `printer_route: Literal["drinks","food"] | null`.
- Invalid `printer_route` literal → `422`.

### 5.2 Order Submit API
- No request/response shape change for `POST /api/orders/submit`.
- Printing is internal side effect only.

## 6. Configuration Requirements

### 6.1 Environment variables
- `PRINTER_BACKEND` = `file` | `escpos_network` (default: `file`)
- `PRINTER_DRINKS_HOST`, `PRINTER_DRINKS_PORT` (default port 9100)
- `PRINTER_FOOD_HOST`, `PRINTER_FOOD_PORT` (default port 9100)
- `KITCHEN_PRINT_OUTPUT_DIR` (optional; defaults to project cwd for file backend)
- `KITCHEN_PRINT_FONT_PATH` is optional; bundled `assets/fonts/NotoSansMyanmar-Regular.ttf` is preferred when present.

### 6.2 Admin UI
- Category create/edit form includes printer route selector:
  - options: Food (default), Drinks
  - empty selection persists as null → server uses food default
- Kitchen printer LAN settings panel (Counter → Menu):
  - print mode: `file` or `escpos_network`
  - render mode: `text` or `image`
  - paper width: `384` or `576`
  - drinks/food LAN IP + port per route
  - persisted via `GET/PUT /api/admin/kitchen-printers`

### 6.3 Environment fallback (optional)
- `.env` may still provide defaults if DB host is empty for a route.

## 7. Non-Functional Requirements
- Myanmar text on tickets should be attempted as UTF-8 in file mode.
- ESC/POS mode: document encoding limitations; do not block submit on encoding issues.
- Image render mode should reduce dependence on printer code pages by rendering Myanmar text server-side.
- Deterministic route resolution for same category configuration.
- Backward compatible: existing submit/WebSocket flows unchanged.

## 8. Out of Scope (v1)
- Per-menu-item printer override
- Cashier receipt ESC/POS (browser print remains)
- Bluetooth/USB printer support
- Kitchen KDS screen
- Print retry queue / dead-letter persistence
- Perfect Myanmar shaping across all operating systems/printers is not guaranteed without a suitable font and renderer support.

## 9. Acceptance Criteria
- AC-1: Admin can set category `printer_route` to drinks or food.
- AC-2: Category without route prints to food route.
- AC-3: Submit with drinks-category item dispatches to drinks route target.
- AC-4: Submit with food-category item dispatches to food route target.
- AC-5: Mixed batch dispatches to both routes correctly.
- AC-6: `PRINTER_BACKEND=file` works without physical printer.
- AC-7: Simulated print failure does not fail order submit (HTTP 200).
- AC-8: Automated tests cover route resolution + non-blocking failure behavior.
- AC-9: Admin can select text/image render mode.
- AC-10: Admin can set paper width to 384 or 576.
- AC-11: File backend image mode writes route-specific PNG output.
- AC-12: ESC/POS network image mode builds non-empty raster payload.
- AC-13: Order submit succeeds even if image rendering fails.
- AC-14: Image renderer auto-loads bundled Myanmar font without `.env` font configuration.
