# Feature Plan: Kitchen LAN Printing (Phase 1 - Step 9)

## Objective
Implement category-routed kitchen ticket printing with:
- admin category → printer route (`drinks` | `food`)
- server env → LAN IP:port per route
- file backend for dev/test
- ESC/POS network backend for Xprinter production
- non-blocking print failures on order submit

## Scope
- Backend: printing service module, orders submit integration
- Backend: category `printer_route` column + schema/API updates
- Frontend: admin category form in counter menu panel
- Tests: routing, default fallback, submit non-blocking behavior
- Docs: `.env.example`, README section, CHANGELOG, roadmap Step 9

## Out of Scope
- Menu-item-level routing
- Admin printer IP management UI
- PostgreSQL/Alembic migration tooling (use existing runtime ALTER pattern)

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

## Delivery Criteria
- Admin can configure category printer route from counter UI.
- Submit prints one ticket per item to correct route.
- File backend enables dev without printer.
- ESC/POS network backend ready for Xprinter LAN IP config.
- pytest green; validation checklist complete.
