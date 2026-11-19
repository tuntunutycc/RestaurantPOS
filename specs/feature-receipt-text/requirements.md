# Requirements: Editable receipt text (shop name, address, thank-you, footer)

Status: **Implemented (owner approved D1-D7 on 2026-11-19).** Deviations from the draft: the row is created by the first `PUT` (not on first read); no audit-log entry (printer settings do not write one either); address / phone / footer lines print flush left (only the shop name keeps its 2-space indent) so a 32-character line fits the 33-character rule.

## Problem
The text printed on the cashier receipt is fixed:
- the shop name comes from the `SHOP_NAME` environment variable (edit `.env`, restart the server);
- the closing line `Thank you!` is hard-coded.
An admin cannot change them, cannot add an address or phone number, and cannot add a closing note.

## Goal
An admin edits these texts on the Counter screen. The next receipt printed uses them. No restart, no file edit.

## Decisions (owner, 2026-11-19)
| Topic | Decision |
|-------|----------|
| Fields | Shop name, address, phone, thank-you line, extra footer note |
| Who can edit | `admin` and `root` (`ADMIN_PANEL_ROLES`) |
| Old orders | A receipt printed or re-printed later always uses the **current** texts. The text is not frozen per order |

## Defaults I chose (please confirm or change)
| # | Default |
|---|---------|
| D1 | One global setting (one shop). Stored in a new single-row table `receipt_settings`. No change to existing tables, no migration of existing columns |
| D2 | A blank field prints nothing, except two fallbacks: blank shop name -> `SHOP_NAME` from `.env`, then `My Restaurant`; blank thank-you -> `Thank you!`. So an install that never opens the new screen prints exactly what it prints today |
| D3 | Limits: every printed line is at most **32 characters** (Unicode characters, not bytes). Shop name 1 line, phone 1 line, thank-you 1 line, address up to **3 lines**, footer note up to **3 lines**. Longer -> `422` with a clear message. The printer does not wrap, so a longer line would be cut off on paper |
| D4 | Plain text only. No HTML, no logo, no QR code |
| D5 | Only the cashier receipt changes. Kitchen / bar slips are not affected. The "Test Print" slip shows the configured shop name |
| D6 | Myanmar text prints correctly only in **Image mode**. In Text mode (ESC/POS text) Myanmar letters do not print. The screen shows this hint next to the fields. Nothing blocks saving |
| D7 | Control characters (anything below space except the line break between lines) are removed on save. Leading / trailing blanks of each line are trimmed |

## Functional requirements

### FR-R1: Setting
- New table `receipt_settings` (single row `id = 1`): `shop_name`, `address`, `phone`, `thank_you`, `footer_note`, all `String`, `NOT NULL DEFAULT ''`. `address` and `footer_note` hold lines separated by `\n`.
- Created at start-up (`create_all`); the row is created by the first `PUT`. No row = all blank. Nothing changes for existing data.

### FR-R2: API (contract first, `schemas.py`)
- `GET /api/admin/receipt-settings` -> `ReceiptSettingsResponse { shop_name, address, phone, thank_you, footer_note }` (strings).
- `PUT /api/admin/receipt-settings` -> body `ReceiptSettingsUpdate` (same five fields, each optional; an omitted field keeps its stored value) -> returns `ReceiptSettingsResponse`.
- Validation (`422`): a line longer than 32 characters; more than 3 lines in `address` / `footer_note`; any line break in `shop_name`, `phone`, `thank_you`.
- Roles: `admin`, `root`. `waiter` / `cashier` -> `403`; no token -> `401`.
- No audit-log entry (kitchen / printer settings do not write one either).

### FR-R3: Receipt layout
```
=================================
  <shop name>
  <address line 1..3>
  <phone>
=================================
Voucher: ...            (unchanged from here)
...
---------------------------------
<thank-you line>
<footer note line 1..3>
[ --- CUT RECEIPT --- ]
```
- Blank fields leave no empty line.
- Everything else on the receipt (voucher, location, served by, items, money lines, payment) is unchanged.
- Text is read when the receipt is built for printing (so a re-print and a queued retry use the current text).

### FR-R4: Admin UI
- Counter -> Menu Management -> new block **Receipt Text** (next to Kitchen Printer Settings): inputs for the five fields, a character counter per line, **Save**, a hint about Image mode (D6).
- Labels in `i18n.js` (en / my).

### FR-R5: No regression
- With the table empty or all fields blank, the printed receipt is byte-identical to today's (D2).
- Money, totals, vouchers, orders and the print queue are untouched.

## Out of scope
Logo / QR code, per-printer or per-language texts, per-order frozen text, automatic line wrapping, a "print a sample receipt" button.

## Open questions
None blocking; D1-D7 are defaults to confirm.
