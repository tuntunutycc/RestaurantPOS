# Plan: Printer Test Print

1. Add `PrinterTestPrintResponse` to `schemas.py`
2. Add `dispatch_printer_test` in `services/printing/service.py`
3. Add `POST /api/printers/{id}/test-print` in `routers/printers.py`
4. Wire **Print Test** on counter Printers table
5. Tests + api-reference + CHANGELOG
