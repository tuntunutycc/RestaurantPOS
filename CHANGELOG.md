# Changelog

## 2026-06-23 - feat/kitchen-image-printing

### Summary
Extended kitchen LAN printing with server-side image render mode for Myanmar text compatibility on Xprinter/ESC/POS printers that cannot render Myanmar Unicode text directly.

### Backend Changes
- Added Pillow dependency for ticket image rendering.
- Added `render_mode` and `paper_width_px` to `kitchen_printer_settings`.
- Extended printer settings API:
  - `render_mode`: `text` | `image`
  - `paper_width_px`: `384` | `576`
- Added image renderer and ESC/POS raster payload builder.
- File backend now supports PNG preview output in image mode.
- Network backend can send raster image ESC/POS payloads in image mode.
- Existing text mode remains the default compatibility path.

### Frontend Changes
- Counter → Menu → Kitchen Printer Settings now includes:
  - render mode selector
  - paper width selector for 58mm/80mm printers

### Spec / Docs
- Updated `specs/feature-kitchen-printing/requirements.md`, `plan.md`, and `validation.md`.
- Updated `specs/roadmap.md`, `specs/tech-stack.md`, and `.env.example`.

### Test Coverage Added
- Image mode file backend writes PNG output.
- ESC/POS raster payload builder returns non-empty raster bytes.
- Settings API validates render mode and paper width.
- Validation run: `PYTHONPATH=. pytest -q` → `39 passed`.

## 2026-06-02 - feat/kitchen-lan-printing

### Summary
Implemented Step 9 kitchen LAN printing with admin category-level printer routing
(`drinks` | `food`, default `food`), configurable ESC/POS network backend for
Xprinter printers, and file backend for development without physical hardware.

### Backend Changes
- Added `Category.printer_route` column and startup migration in `main.py`.
- Extended category schemas/API:
  - `CategoryCreate`, `CategoryUpdate`, `CategoryResponse` include `printer_route`
  - `PUT /api/categories/{category_id}` for admin route updates
- Added `services/printing/` module:
  - route resolver with unknown/null → `food` fallback
  - ticket builder (single-item tickets, Myanmar text, takeaway header)
  - `file` and `escpos_network` backends
- Replaced `mock_send_to_printer` in `routers/orders.py` with `dispatch_kitchen_ticket`.
- Print dispatch remains non-blocking on order submit (`return_exceptions=True`).

### Frontend Changes
- Counter menu admin:
  - category create form includes printer route selector
  - category list shows route badge + inline route update (Save)

### Configuration
- Added `.env.example` printer settings (optional env fallback):
  - `PRINTER_BACKEND`, `PRINTER_DRINKS_HOST/PORT`, `PRINTER_FOOD_HOST/PORT`
  - optional `KITCHEN_PRINT_OUTPUT_DIR`
- **Admin UI (preferred):** Counter → Menu → Kitchen Printer Settings
  - print mode (`file` / `escpos_network`)
  - Drinks + Food counter LAN IP/port saved in database

### Backend (UI settings)
- Added `kitchen_printer_settings` + `printer_route_endpoints` tables.
- Added `GET/PUT /api/admin/kitchen-printers` (admin only).
- Print service loads backend + LAN endpoints from DB, with env fallback if host missing.

### Spec / Docs
- Added `specs/feature-kitchen-printing/` (requirements, plan, validation)
- Updated `specs/roadmap.md` Step 9 and kitchen dispatch baseline notes
- Updated `specs/tech-stack.md` orders router description

### Test Coverage Added
- `tests/test_kitchen_printing.py`:
  - route resolver defaults/unknown fallback
  - category API `printer_route` contract + 422 invalid literal
  - drinks/food file routing on mixed submit
  - unknown DB route fallback to food file
  - submit success when print dispatch raises

## 2026-04-20 - feat/table-management

### Summary
Implemented Phase 1 / Step 7 table-management enhancements on branch `feat/table-management` with finalized-order deletion safety (`paid` and `cancelled` only), historical-order detachment, realtime refresh consistency, and expanded automated coverage.

### Backend Changes
- Updated `routers/tables.py` table/zone delete safety checks to use:
  - finalized statuses: `paid`, `cancelled`
  - block condition: any linked order not in finalized set
- Refined blocked-delete API messages to clearly explain eligibility:
  - table delete now states only paid/cancelled orders permit deletion.
- Kept historical integrity behavior:
  - on successful delete, linked finalized orders are preserved and detached via `table_id = NULL`.
- Marked Step 7 status as completed in `specs/roadmap.md`.

### Frontend Changes
- No frontend code changes were required in this branch.
- Existing admin table-management UX in `static/counter.js` already provided:
  - table edit controls (rename + zone reassignment)
  - explicit table delete action with confirmation
  - user feedback paths for success and error responses

### Realtime / Refresh Changes
- Ensured table-grid refresh broadcast consistency in `routers/tables.py`:
  - `update_table` now triggers table-grid refresh after successful update.
  - `delete_table` now triggers table-grid refresh after successful delete.
  - `delete_zone` now triggers table-grid refresh after successful delete.

### Test Coverage Added/Updated
- Updated `tests/test_tables_management.py` expectations for new non-finalized delete semantics.
- Added test coverage for:
  - blocked delete when status is `completed` (treated as non-finalized/unpaid),
  - successful delete when status is `cancelled`,
  - historical detachment (`table_id = NULL`) retention for finalized rows.
- Validation runs:
  - targeted suite passed (`tests/test_tables_management.py` + `tests/test_integrity.py`)
  - full suite passed (`30 passed`).
