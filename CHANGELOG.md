# Changelog

## 2026-04-20 - feat/table-management

### Summary
Implemented Phase 1 / Step 7 table-management enhancements on branch `feat/table-management` with finalized-order deletion safety (`paid` and `cancelled` only), historical-order detachment, realtime refresh consistency, and expanded automated coverage.

### Backend Changes
- Updated `routers/tables.py` table/zone delete safety checks to use:
  - finalized statuses: `paid`, `cancelled`
  - block condition: any linked order not in finalized set
- Refined blocked-delete API messages to clearly explain eligibility:
  - table delete now states only paid/cancelled orders permit deletion.
- Kept historical integrity behavior:
  - on successful delete, linked finalized orders are preserved and detached via `table_id = NULL`.
- Marked Step 7 status as completed in `specs/roadmap.md`.

### Frontend Changes
- No frontend code changes were required in this branch.
- Existing admin table-management UX in `static/counter.js` already provided:
  - table edit controls (rename + zone reassignment)
  - explicit table delete action with confirmation
  - user feedback paths for success and error responses

### Realtime / Refresh Changes
- Ensured table-grid refresh broadcast consistency in `routers/tables.py`:
  - `update_table` now triggers table-grid refresh after successful update.
  - `delete_table` now triggers table-grid refresh after successful delete.
  - `delete_zone` now triggers table-grid refresh after successful delete.

### Test Coverage Added/Updated
- Updated `tests/test_tables_management.py` expectations for new non-finalized delete semantics.
- Added test coverage for:
  - blocked delete when status is `completed` (treated as non-finalized/unpaid),
  - successful delete when status is `cancelled`,
  - historical detachment (`table_id = NULL`) retention for finalized rows.
- Validation runs:
  - targeted suite passed (`tests/test_tables_management.py` + `tests/test_integrity.py`)
  - full suite passed (`30 passed`).
