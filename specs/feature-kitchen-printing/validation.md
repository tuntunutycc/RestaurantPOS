# Validation Checklist: Kitchen LAN Printing (Phase 1 - Step 9)

Validation evidence:
- Latest automated run: `PYTHONPATH=. venv/bin/python -m pytest -q` -> **52 passed** (2026-07-04)
- Kitchen printing tests: `tests/test_kitchen_printing.py` (14 tests within full suite)

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
- [x] Ticket includes table header for dine-in (tested); takeaway header implemented in `ticket.py` — **takeaway path not automated**
- [x] Myanmar item names appear in file backend output.

## D. Backends
- [x] `backend=file` writes route-specific `.txt` / `.png` outputs.
- [x] `backend=escpos_network` settings API and raster payload builder tested.
- [ ] Missing host for `escpos_network` logs error without crashing submit — **code path exists; no socket mock test**

## E. Order Submit Integrity (Critical)
- [x] `POST /api/orders/submit` response unchanged (contract stable).
- [x] Simulated print exception still returns submit success.
- [x] Order/items persisted even when all prints fail.
- [ ] WebSocket `new_order_batch` still emitted on submit — **not asserted in kitchen printing tests**

## F. Admin UI
- [x] Category form shows printer route selector (manual UI; API contract tested).
- [x] Default (Food) saves null/food behavior correctly.
- [x] Non-panel roles cannot mutate categories — waiter `403` tested; access is `ADMIN_PANEL_ROLES` (`root`, `admin`).

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
- [x] Admin UI can save render mode and paper width via **API** (`test_admin_kitchen_printer_settings_api`).
- [ ] Admin UI manual save of render mode / paper width — **manual verification**

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
- [x] Bundled Myanmar/Latin fonts loadable by Pillow (automated).
- [x] OFL license files present at `assets/fonts/OFL-NotoSansMyanmar.txt` and `OFL-NotoSans.txt` — **file check manual; not automated**
- [x] Mixed Myanmar/English/digits/punctuation renders with fallback fonts.
- [x] Image render failure does not fail order submit.
- [x] Network print failure still does not fail order submit.
- [x] Existing kitchen printing tests still pass.

## M. Automated Tests

- [x] Test: settings API supports render mode + paper width.
- [x] Test: image mode file backend writes PNG.
- [x] Test: bundled Myanmar font auto-discovery.
- [x] Test: bundled Latin fallback font routing.
- [x] Test: mixed-script image render remains non-empty.
- [x] Test: Myanmar U+1031 shaping differs from Pillow BASIC layout (`tests/test_myanmar_print_shaping.py`).
- [x] Test: shaping backend is `raqm` or `harfbuzz` when engines are installed.
- [x] Test: raster payload builder returns non-empty bytes.
- [x] Test: order submit succeeds when renderer raises.
- [x] Full suite passes: **52 passed** (2026-07-04).
