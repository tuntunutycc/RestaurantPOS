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
- Loads printer hardware endpoints from environment variables.
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

### 6.2 Admin UI
- Category create/edit form includes printer route selector:
  - options: Food (default), Drinks
  - empty selection persists as null → server uses food default
- Kitchen printer LAN settings panel (Counter → Menu):
  - print mode: `file` or `escpos_network`
  - drinks/food LAN IP + port per route
  - persisted via `GET/PUT /api/admin/kitchen-printers`

### 6.3 Environment fallback (optional)
- `.env` may still provide defaults if DB host is empty for a route.

## 7. Non-Functional Requirements
- Myanmar text on tickets should be attempted as UTF-8 in file mode.
- ESC/POS mode: document encoding limitations; do not block submit on encoding issues.
- Deterministic route resolution for same category configuration.
- Backward compatible: existing submit/WebSocket flows unchanged.

## 8. Out of Scope (v1)
- Per-menu-item printer override
- Cashier receipt ESC/POS (browser print remains)
- Bluetooth/USB printer support
- Admin UI for editing printer IP addresses (env-only in v1)
- Kitchen KDS screen
- Print retry queue / dead-letter persistence

## 9. Acceptance Criteria
- AC-1: Admin can set category `printer_route` to drinks or food.
- AC-2: Category without route prints to food route.
- AC-3: Submit with drinks-category item dispatches to drinks route target.
- AC-4: Submit with food-category item dispatches to food route target.
- AC-5: Mixed batch dispatches to both routes correctly.
- AC-6: `PRINTER_BACKEND=file` works without physical printer.
- AC-7: Simulated print failure does not fail order submit (HTTP 200).
- AC-8: Automated tests cover route resolution + non-blocking failure behavior.
