# Implementation: Dynamic Printer Management

- `models.Printer` (`printers` table) with `role`
- `services/printing/settings.py` — `seed_default_printers`, `resolve_printer_endpoint_for_role`
- `services/printing/routes.py` — category drinks|food unchanged; role map helpers
- `routers/printers.py` — full CRUD
- `routers/kitchen_printers.py` — backend/render/paper only (`routes` empty/compat)
- `scripts/seed_root.py` — seeds default printers after root
- `static/counter.html` / `counter.js` — printer table CRUD; cashier dropdown unchanged path
