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
