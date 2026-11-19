# Validation: Safe menu price changes

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` → **610 passed** (2026-11-19; 86 in `tests/test_menu_price_safety.py`).

## Automated
- [x] FR-P3: open order keeps the price each line was sold at; an add-on after a rise uses the new price (`3500` + `4000` = `7500`); checkout of that bill
- [x] FR-P3: cancelling a line after a price change removes the price it was sold at
- [x] FR-P3: a paid order, Order History and the per-cashier report are identical after four price changes (including `0`)
- [x] FR-P3: changing tax / discount of the menu item does not touch an open order
- [x] P10: price below a fixed discount → free item, no error
- [x] FR-P1: 31 bad `PUT` bodies (`null`, `NaN`, `Infinity`, negative, above the limit, blank name, percentage > 100, null for each required field, bad modifier prices) → `422` and the stored item is unchanged
- [x] FR-P1: percentage limit judged on the values after a partial update (both directions)
- [x] FR-P1: unknown category → `404` on update, create and upload; nothing created
- [x] FR-P1: bad new items (8 bodies) → `422`; name is trimmed
- [x] FR-P1: upload form refuses `nan`, `inf`, `-inf`, `-1`, `1e12`, blank name
- [x] Still allowed: price `0`, clearing `discount_price` / `takeaway_price` / `description` / `image_url`, negative modifier option, fixed discount above the price, unsent fields untouched
- [x] Roles: admin / root `200`, cashier / waiter `403` for a price change
- [x] FR-P2: bad stored data (negative, infinite, `1e12` price, infinite tax, negative takeaway price) → ordering is `400` naming the item, **no order saved**, table stays free; dine-in still works when only the takeaway price is bad
- [x] FR-P2: percentage discount 150 % → free item (capped), no error
- [x] FR-P2: a waiter screen sending modifier price `NaN` / `Infinity` / `1e12` / text → `422`, no order saved; `-1e12` or a modifier that makes the line negative → `400`; a small negative modifier (`-200`) still works
- [x] Add-on with a bad item to an open order → `400`, the bill and its lines are unchanged
- [x] 20 deliberate code breakages: 18 caught; the other 2 are duplicate guards (the limit already stops `NaN` / `Infinity`)

## Review checklist
- Security / roles: only `root` / `admin` can edit the menu (unchanged); nothing new is exposed.
- Money: recorded lines, totals, paid orders and reports are never recomputed from the live price; refused orders write nothing.
- Edge cases: `0` price, partial updates, old bad data, takeaway vs dine-in price, add-on to an open bill, null vs not-sent fields.
- Not verified: the admin form in a real browser (its payload shape is covered by the API tests); the limit `1,000,000,000` and "tax percentage ≤ 100" are the assistant's choices and can be changed.
