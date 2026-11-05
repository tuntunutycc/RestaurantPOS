# Plan: Windows Cashier Receipt Printing

## Approach
1. Add `windows_printer` backend + `Printer.windows_printer_name`
2. `services/printing/backends/escpos_windows.py` — list + RAW send (guarded `win32print`)
3. Dispatch cashier route via Windows; kitchen falls back to file
4. Admin API list + counter UI dropdown
5. `requirements-windows.txt` with `pywin32`; Mac tests mock the backend

## Files
- `models.py`, `schemas.py`, `main.py` ALTER
- `services/printing/config.py`, `settings.py`, `service.py`, `backends/escpos_windows.py`
- `routers/kitchen_printers.py`, `routers/printers.py`
- `static/counter.html`, `static/counter.js`
- `tests/test_windows_cashier_printing.py`
- Specs + `CHANGELOG.md` + api-reference / database-schema
