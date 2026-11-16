# Validation: Windows Cashier Receipt Printing

## Checklist
- [x] `PrinterBackendLiteral` includes `windows_printer`
- [x] `Printer.windows_printer_name` persisted via CRUD
- [x] `GET /api/admin/windows-printers` admin-only; shape `{available,printers,message}`
- [x] Cashier dispatch with `windows_printer` calls RAW send with queue name + receipt totals
- [x] Kitchen route under `windows_printer` writes file (fallback)
- [x] Missing queue name / non-Windows send → controlled error; checkout soft-fails
- [x] Admin UI: backend option + Windows queue datalist (all installed queues; type-to-override) on cashier printer modal
- [x] `list_windows_printers` merges LOCAL + CONNECTIONS (+ NETWORK) across levels (not network-only)
- [x] Opening printer modal reloads print mode so Windows fields are not stuck on LAN-only
- [x] Print dispatch logs backend/render_mode/target on every job
- [x] Full pytest suite green (221+ passed)

## Automated tests
- `tests/test_windows_cashier_printing.py`
