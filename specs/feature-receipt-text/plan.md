# Plan: Editable receipt text

Status: implemented. Extra file: `services/receipt_text.py` (pure cleaning / limits, shared by the schema and the receipt).

1. **Contract** - `schemas.py`: `ReceiptSettingsResponse`, `ReceiptSettingsUpdate` (line / length validators).
2. **Model** - `models.py`: `ReceiptSettings` single-row table (new table only; `create_all` creates it).
3. **Access** - `services/printing/settings.py`: `load_receipt_settings(db)` (creates the row, never raises, falls back to blank), `normalize_receipt_text(...)`.
4. **API** - new `routers/receipt_settings.py` (`/api/admin/receipt-settings`, `ADMIN_PANEL_ROLES`), registered in `main.py`.
5. **Receipt** - `services/printing/receipt.py`: `build_receipt_text(...)` takes optional `header_lines` / `footer_lines`; defaults reproduce today's text byte for byte. `services/printing/service.py` loads the settings (own DB session) when it builds a receipt and for the test-print slip.
6. **UI** - `static/counter.html`, `static/counter.js`, `static/i18n.js`: Receipt Text block.
7. **Tests** - `tests/test_receipt_settings.py`.
8. **Docs** - `api-reference.md`, `database-schema.md`, `specs/feature-cashier-receipt-printing`, `CHANGELOG.md`.

| File | Change |
|------|--------|
| `schemas.py` | 2 new models |
| `models.py` | `ReceiptSettings` |
| `services/printing/settings.py` | load + normalize |
| `routers/receipt_settings.py`, `main.py` | new endpoint |
| `services/printing/receipt.py`, `service.py` | header / footer from settings |
| `static/counter.html`, `counter.js`, `i18n.js` | UI |
| `tests/test_receipt_settings.py` | new |

Risk: the receipt is money-adjacent output. Mitigation: FR-R5 (identical output when unset) is a test; no money line is touched.
