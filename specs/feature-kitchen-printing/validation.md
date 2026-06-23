# Validation Checklist: Kitchen LAN Printing (Phase 1 - Step 9)

## A. Category Route Configuration
- [ ] `CategoryResponse` includes `printer_route`.
- [ ] Admin can set `printer_route` to `drinks` via API/UI.
- [ ] Admin can set `printer_route` to `food` via API/UI.
- [ ] Empty/null `printer_route` is accepted and means default food.
- [ ] Invalid `printer_route` literal returns `422`.

## B. Route Resolution
- [ ] Drinks-category item resolves to `drinks` route.
- [ ] Null/empty category route resolves to `food`.
- [ ] Unknown route value falls back to `food` with warning log.

## C. Ticket Dispatch
- [ ] One submitted line item produces exactly one ticket.
- [ ] Mixed batch sends to both drinks and food targets.
- [ ] Ticket includes table OR takeaway header, order id, time, qty×name, note.
- [ ] Myanmar item names appear in file backend output.

## D. Backends
- [ ] `PRINTER_BACKEND=file` writes to `drinks_printer_output.txt` and `food_printer_output.txt`.
- [ ] `PRINTER_BACKEND=escpos_network` uses configured host/port per route.
- [ ] Missing host for route logs error; does not crash submit.

## E. Order Submit Integrity (Critical)
- [ ] `POST /api/orders/submit` response unchanged (contract stable).
- [ ] Simulated print exception still returns submit success.
- [ ] Order/items persisted even when all prints fail.
- [ ] WebSocket `new_order_batch` still emitted on submit.

## F. Admin UI
- [ ] Category form shows printer route selector.
- [ ] Default (Food) saves null/food behavior correctly.
- [ ] Non-admin cannot mutate categories (existing RBAC unchanged).

## G. Automated Tests (Required)
- [ ] Test: drinks route dispatch
- [ ] Test: default food route dispatch
- [ ] Test: mixed batch dual dispatch
- [ ] Test: invalid route fallback to food
- [ ] Test: print failure non-blocking submit
- [ ] Test: category API `printer_route` contract

## H. Definition of Done
- [ ] All required checks A–G pass.
- [ ] Full pytest suite green.
- [ ] `CHANGELOG.md` updated.
- [ ] `specs/roadmap.md` Step 9 marked with evidence.

## I. Image Render Mode

- [ ] Printer settings API returns `render_mode`.
- [ ] Printer settings API returns `paper_width_px`.
- [ ] Admin UI can save `text` mode.
- [ ] Admin UI can save `image` mode.
- [ ] Admin UI can save paper width `384`.
- [ ] Admin UI can save paper width `576`.

## J. File Backend Image Preview

- [ ] File backend + text mode writes `.txt`.
- [ ] File backend + image mode writes `.png`.
- [ ] PNG output is non-empty.
- [ ] PNG output dimensions match configured paper width.

## K. ESC/POS Raster Payload

- [ ] Text mode still builds ESC/POS text payload.
- [ ] Image mode builds ESC/POS raster payload.
- [ ] Raster payload includes init/feed/cut bytes.
- [ ] Payload is non-empty for Myanmar item names.

## L. Failure Safety

- [ ] Missing configured font logs clear warning and falls back.
- [ ] Image render failure does not fail order submit.
- [ ] Network print failure still does not fail order submit.
- [ ] Existing kitchen printing tests still pass.

## M. Automated Tests

- [ ] Test: settings API supports render mode + paper width.
- [ ] Test: image mode file backend writes PNG.
- [ ] Test: raster payload builder returns non-empty bytes.
- [ ] Test: order submit succeeds when renderer raises.
- [ ] Full suite passes: `PYTHONPATH=. pytest -q`.
