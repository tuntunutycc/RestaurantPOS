# Validation: Linked add-ons (Step 2 of 2)

Run: `PYTHONPATH=.:.pip_pkgs python -m pytest -q` -> **664 passed** (2026-11-19; 37 in `tests/test_linked_addons.py`). Before the implementation 24 of those failed for the expected reasons.

## Automated - `tests/test_linked_addons.py`
Contract
- [x] Menu list/create/update responses show `linked_menu_item_id` and `price_override` per option (`null` when not linked); old rows without the keys read as `null` (no `500`).
- [x] An existing unlinked menu (saved before the feature) gives the **same** response and the same order result as before (regression).

FR-L1 saving
- [x] Link to a missing id -> `404`; to a soft-deleted item -> `404`; to itself -> `422`; `price_override` without link -> `422`; override `-1`, `NaN`, `Infinity`, `1e12` -> `422`. Nothing is saved in any of these.
- [x] Linked option sent with a wrong `price` (e.g. `1`) -> stored `price` equals the target's price; with override `300` -> stored `price` is `300`; override `0` -> `0` (not "follow").
- [x] Linked option with blank name -> filled with the target's name; non-blank name is kept.
- [x] Duplicate `(group, name)` with a linked option -> `422`; duplicates among purely unlinked options still accepted (as today).
- [x] Create and update follow the same rules (upload has no modifiers input, so nothing to validate).

FR-L2 delete
- [x] Target linked by two items -> `400`, `detail` names both items and ids, target still not deleted, holders unchanged.
- [x] More than 20 holders -> list is cut with `and N more`.
- [x] Holder soft-deleted, or the link removed -> delete succeeds. Deleting a holder (which owns links) works.
- [x] Existing rule still holds: target on an active order -> `400` with the old message.

FR-L3 sync
- [x] Target price change updates stored `option.price` of every holder option **without** override; options with override and unlinked options are untouched; soft-deleted holders do not matter.
- [x] One `menu_item_updated` event for the target and one for each changed holder (WebSocket test client).
- [x] A failing update (e.g. `422`) changes neither target nor holders.

FR-L4 ordering (three paths: new order, add to order, `submit_order`)
- [x] Waiter sends a stale/wrong price for a linked add-on -> the line uses the live target price; `subtotal` equals `(base + tax + effective * qty_mod) * qty`.
- [x] Override option -> override price. Target price changed to `0` -> add-on `0`, no error.
- [x] Target soft-deleted after linking is impossible by FR-L2; if the data is forced that way (test sets it directly), the stored `option.price` fallback is used, no `500`.
- [x] Snapshot: linked add-on stores `linked_menu_item_id`; unlinked add-on stores exactly `{name, price, group, quantity}` (no extra key); a client-sent `linked_menu_item_id` on an unlinked modifier is dropped.
- [x] Modifier name that matches no option -> client price used (documented D5).
- [x] Bad computed price (over the limit / makes the line negative) -> `400` before anything is saved.

FR-L5 history
- [x] Order with a linked add-on, then target price rise: open order total, paid order, Order History, receipt payload, kitchen payload and reports are identical before and after; a new order uses the new price.
- [x] Cancelling a line after the rise removes the amount it was sold at.

FR-L6 / FR-L7 (frontend)
- [x] API-level test of the payload the form sends (link, auto-filled name, override, back to "None"); `flattenModifierOptions` / `wrapModifierOptions` round trip and `refreshLinkedModifierPrices` checked with Node.
- [ ] Manual browser check by the owner (**not auto-verified**): link, auto-fill, read-only price, custom price, unlink, save, reload keeps the link; delete refusal text; waiter cart refresh after a price change.

Roles
- [x] admin / root can save links and delete; cashier / waiter `403` on menu writes (unchanged).

Whole suite
- [x] `PYTHONPATH=.:.pip_pkgs python -m pytest -q` green (baseline = Step 1 result).
- [x] Mutation check: 22 deliberate breakages (override order, target price ignored, no price overwrite, missing target allowed, self link, blank name, duplicate check, override without link, sync overwrites overrides, sync not called, delete guard off, list cut, deleted holders block, snapshot key dropped, unlinked matched, group ignored, each of the 3 order paths unresolved, `None` keys stored, holders not broadcast, range check off, fallback 0) - all caught; files restored. One extra breakage (the fallback constructor in `_daily_history_line`) survives because valid data never reaches it.

## Review checklist
- Security / roles: only `root` / `admin` can change links; the server never trusts a client price or `linked_menu_item_id` for a linked option; no new endpoint.
- Money: recorded lines and reports are never recomputed; computed price passes the existing limits; a refused order writes nothing; target price `0` and override `0` are legal.
- Data consistency: sync and target price change share one transaction; stored `option.price` is only a fallback; delete refuses while links exist, so no dangling link in normal use.
- Edge cases: self-link, cycle A<->B, duplicate names, blank name, renamed option vs stale cart, soft-deleted holder, many holders, old rows without keys, upload endpoint, partial `PUT` that does not send `modifiers_config` (links must survive).
- Backward compatibility: no schema change; old clients ignore the new keys; unlinked add-ons behave exactly as before.
- Known limits: unlinked add-on prices are still client-trusted; no option ids; reports by `linked_menu_item_id` not built yet.
