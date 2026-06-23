# Validation Checklist: Kitchen LAN Printing (Phase 1 - Step 9)

Validation evidence:
- Latest automated run: `PYTHONPATH=. pytest -q` -> `41 passed`
- Primary test file: `tests/test_kitchen_printing.py`

## A. Category Route Configuration
- [x] `CategoryResponse` includes `printer_route`.
- [x] Admin can set `printer_route` to `drinks` via API/UI.
- [x] Admin can set `printer_route` to `food` via API/UI.
- [x] Empty/null `printer_route` is accepted and means default food.
- [x] Invalid `printer_route` literal returns `422`.

## B. Route Resolution
- [x] Drinks-category item resolves to `drinks` route.
- [x] Null/empty category route resolves to `food`.
- [x] Unknown route value falls back to `food` with warning log.

## C. Ticket Dispatch
- [x] One submitted line item produces exactly one ticket.
- [x] Mixed batch sends to both drinks and food targets.
- [x] Ticket includes table OR takeaway header, order id, time, qty×name, note.
- [x] Myanmar item names appear in file backend output.

## D. Backends
- [x] `backend=file` writes to `drinks_printer_output.txt` and `food_printer_output.txt`.
- [x] `backend=escpos_network` uses configured host/port per route.
- [x] Missing host for route logs error; does not crash submit.

## E. Order Submit Integrity (Critical)
- [x] `POST /api/orders/submit` response unchanged (contract stable).
- [x] Simulated print exception still returns submit success.
- [x] Order/items persisted even when all prints fail.
- [x] WebSocket `new_order_batch` still emitted on submit.

## F. Admin UI
- [x] Category form shows printer route selector.
- [x] Default (Food) saves null/food behavior correctly.
- [x] Non-admin cannot mutate categories (existing RBAC unchanged).

## G. Automated Tests (Required)
- [x] Test: drinks route dispatch
- [x] Test: default food route dispatch
- [x] Test: mixed batch dual dispatch
- [x] Test: invalid route fallback to food
- [x] Test: print failure non-blocking submit
- [x] Test: category API `printer_route` contract

## H. Definition of Done
- [x] All required checks A–G pass.
- [x] Full pytest suite green.
- [x] `CHANGELOG.md` updated.
- [x] `specs/roadmap.md` Step 9 marked with evidence.

## I. Image Render Mode

- [x] Printer settings API returns `render_mode`.
- [x] Printer settings API returns `paper_width_px`.
- [x] Admin UI can save `text` mode.
- [x] Admin UI can save `image` mode.
- [x] Admin UI can save paper width `384`.
- [x] Admin UI can save paper width `576`.

## J. File Backend Image Preview

- [x] File backend + text mode writes `.txt`.
- [x] File backend + image mode writes `.png`.
- [x] PNG output is non-empty.
- [x] PNG output dimensions match configured paper width.

## K. ESC/POS Raster Payload

- [x] Text mode still builds ESC/POS text payload.
- [x] Image mode builds ESC/POS raster payload.
- [x] Raster payload includes init/feed/cut bytes.
- [x] Payload is non-empty for Myanmar item names.

## L. Failure Safety

- [x] Missing configured font logs clear warning and falls back.
- [x] Bundled Myanmar font discovery works without `.env` font path.
- [x] Bundled `assets/fonts/NotoSansMyanmar-Regular.ttf` is loadable by Pillow.
- [x] Bundled Noto Sans Myanmar OFL license is included.
- [x] Image render failure does not fail order submit.
- [x] Network print failure still does not fail order submit.
- [x] Existing kitchen printing tests still pass.

## M. Automated Tests

- [x] Test: settings API supports render mode + paper width.
- [x] Test: image mode file backend writes PNG.
- [x] Test: bundled Myanmar font auto-discovery.
- [x] Test: raster payload builder returns non-empty bytes.
- [x] Test: order submit succeeds when renderer raises.
- [x] Full suite passes: `PYTHONPATH=. pytest -q`.
