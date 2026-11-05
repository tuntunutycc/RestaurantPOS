# Implementation: Windows Cashier Receipt Printing

## Delivered
- Backend `windows_printer` + `Printer.windows_printer_name`
- `services/printing/backends/escpos_windows.py` (guarded `win32print`)
- `GET /api/admin/windows-printers`
- Cashier dispatch RAW send; kitchen/drinks file fallback
- Counter Admin UI: print mode option + Windows queue dropdown
- `requirements-windows.txt`
- `tests/test_windows_cashier_printing.py`

## Deploy (Windows PC)
1. `pip install -r requirements-windows.txt`
2. Run uvicorn natively (not Docker Linux)
3. Admin → Print mode = Windows printer
4. Edit cashier printer → select `POSPrinter POS-80(300DPI)` (or installed queue)
5. Checkout with Print Receipt enabled
