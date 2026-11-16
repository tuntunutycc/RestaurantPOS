# Plan: Kitchen Slip Mode

1. **Contract** — `schemas.py`: `KitchenSlipModeLiteral`; field on `KitchenPrinterSettingsResponse` and (optional) `KitchenPrinterSettingsUpdate`.
2. **Model + migration** — `models.py` column; `main.py` startup `ALTER TABLE`.
3. **Setting access** — `services/printing/settings.py`: `load_kitchen_slip_mode(db)`.
4. **API** — `routers/kitchen_printers.py`: return and store the mode.
5. **Submit** — `routers/orders.py`: build one job per line or one per route.
6. **Print jobs** — `services/printing/print_jobs.py`: combined label, drop cancelled lines at send time, skip when none remain, hide from the failed list.
7. **UI** — `static/counter.html`, `static/counter.js`: **Kitchen slip** select.
8. **Tests** — `tests/test_kitchen_slip_mode.py`.
9. **Docs** — kitchen-printing spec, `api-reference.md`, `database-schema.md`, `CHANGELOG.md`.

| File | Change |
|------|--------|
| `schemas.py` | New literal + fields |
| `models.py` | `KitchenPrinterSettings.kitchen_slip_mode` |
| `main.py` | Add-column migration |
| `services/printing/settings.py` | `load_kitchen_slip_mode` |
| `routers/kitchen_printers.py` | GET/PUT |
| `routers/orders.py` | Job creation by mode |
| `services/printing/print_jobs.py` | Combined slip handling |
| `static/counter.html`, `static/counter.js` | Setting control |
| `tests/test_kitchen_slip_mode.py` | New |
