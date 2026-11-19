# Validation: Editable receipt text

## Automated (`tests/test_receipt_settings.py`)
- [x] FR-R5: with no row / all blank, `build_receipt_text` output equals the previous output byte for byte (golden string incl. `SHOP_NAME` fallback and `Thank you!`).
- [x] FR-R2 contract: `GET` / `PUT` shapes; omitted field keeps its value; `PUT` then `GET` round-trips Myanmar text.
- [x] FR-R2 validation: 33-character line, 4 address lines, line break inside `shop_name` -> `422`; exactly 32 characters / 3 lines accepted.
- [x] D7: control characters removed, blank lines and outer blanks trimmed.
- [x] Roles: admin and root `200`; cashier and waiter `403`; no token `401`.
- [x] FR-R3: shop name, address, phone appear between the top rules in that order; thank-you and footer lines appear before the cut line; blank fields leave no empty line.
- [x] A receipt for a checkout made after a change uses the new text; a re-print of an old order also uses the new text (owner decision).
- [x] Test-print slip shows the configured shop name.
- [x] Money, voucher, items and payment lines are identical with and without custom text.
- [x] Mutation check: ignoring the setting, or dropping the fallback, makes at least one test fail.
- [x] Full suite passes.

## Manual (browser / printer)
- [x] Counter shows the Receipt Text block, counters work, an over-long line is blocked with a message, Save persists the values (checked in a real browser on a throw-away database).
- [x] A line over 32 characters is blocked on the screen (red counter + message); the server also answers 422.
- [x] Image mode output (PNG of the receipt) shows the Myanmar shop name, address and thank-you correctly; the Text-mode hint is visible. - [ ] Not tried on a real printer.
- [ ] A 32-character line fits on 80 mm paper; check 58 mm.

## Review checklist
- [ ] Security: text is printed as plain text, never rendered as HTML in the UI (use `escapeHtml` / `textContent`); control characters stripped.
- [ ] Roles: only admin / root can change; everybody who can check out can still print.
- [ ] Edge cases: blank, 32 / 33 characters, Myanmar combining marks, many blank lines, missing row, DB error while loading (receipt must still print with defaults).
