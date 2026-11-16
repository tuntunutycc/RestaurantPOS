# Validation: Printer Test Print

## Checklist
- [x] Admin/root can POST test-print; cashier gets 403
- [x] Missing printer → 404
- [x] File backend succeeds and writes ticket text
- [x] Windows cashier path uses that row’s `windows_printer_name` (mocked)
- [x] LAN kitchen path uses that row’s host (mocked)
- [x] UI: Print Test button per printers table row
- [x] `GET /api/printers/{id}/health` admin-only; file skipped / Windows queue / LAN probe
- [x] Admin aggregate health includes `named_printers`
- [x] UI: Check button + clearer Print Test errors

## Automated tests
- `tests/test_printer_test_print.py`
- `tests/test_printer_named_health.py`
