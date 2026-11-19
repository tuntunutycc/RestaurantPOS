# Feature: Linked add-ons (Step 2 of 2)

> Status: **Implemented 2026-11-19** (after Step 1, `specs/feature-snapshot-first-names/`, was committed with a green suite). Browser behaviour of the admin form and waiter screen is not auto-verified - see `validation.md`.

## Purpose
An add-on such as "extra fried egg" is usually also a normal menu item with its own price. Today the add-on price is typed by hand, so when the owner raises the price of the main item the add-on keeps the old price. This feature lets an add-on **optionally** point at a main menu item so its price follows that item. Add-ons that are not linked behave exactly as today.

## Vocabulary
There is **no separate add-on table**. An add-on is one *option* inside `MenuItem.modifiers_config` (JSON column):
`[{group, is_required, options:[{name, price}]}]`. A picked add-on is stored on the order line in `OrderItem.selected_modifiers` (JSON): `[{name, price, group, quantity}]`. "Holder" = the menu item that owns the option. "Target" = the main menu item the option links to.

## Owner decisions (2026-11-19)
1. The option keeps its **own name**; only the **price** follows the target. In the admin form, when a target is chosen and the option name is empty, the target's name is filled in automatically and stays editable.
2. A linked price is the target's `price` only (not the discount price, takeaway price or tax).
3. Deleting a menu item that is still linked is refused with `400`, and the answer lists which menu items link to it.
4. Snapshot-first names come first (Step 1, separate commit/phase).
5. No `option_id` in this step. Options are matched by `name` + `group`.
6. A picked linked add-on stores `linked_menu_item_id` in the order-line snapshot (for future reports). Unlinked add-ons store nothing extra.
7. Saving a linked option stores the target's current price in `option.price` as a fallback, so the fallback is never accidentally `0`.

## Data contract (additive; old data and old clients keep working)

`ModifierOption` (inside `modifiers_config`):

| Field | Type | Meaning |
|-------|------|---------|
| `name` | text | own name (unchanged) |
| `price` | number | **stored price**: the option's own price when unlinked; when linked, the last synchronised effective price (see FR-L3). Same range as today |
| `linked_menu_item_id` | int or `null`, default `null` | target menu item. Missing key = `null` = not linked |
| `price_override` | number `0 ... 1,000,000,000` or `null`, default `null` | price used instead of the target's price. `0` is a real value (free add-on); `null` means "follow the target" |

`SelectedModifier` (request and response) gains `linked_menu_item_id: int | null = null`.
Order-line snapshot (`OrderItem.selected_modifiers` JSON): the key `linked_menu_item_id` is present **only** when the option was linked at sale time; unlinked add-ons are stored exactly as today.

No database column, no table, no SQLite migration. Existing rows have no new keys, which reads as "not linked".

## Effective price (one rule, one place)
For an option with a target:
1. `price_override` if it is not `null`;
2. else the target's **current** `price`, if the target exists and is not soft-deleted;
3. else the stored `option.price` (fallback).

Options without a target: `option.price`, as today.

## FR-L1: Saving a menu item (`POST /menu-items/`, `PUT /menu-items/{id}`; `POST /menu-items/upload` takes no modifiers)
For every option with `linked_menu_item_id`:
- the target must exist and not be soft-deleted -> otherwise `404` (`Menu item id N not found`);
- the target must not be the holder itself -> `422`;
- a blank `name` is filled with the target's name (so API clients get the same convenience as the form);
- `option.price` is **overwritten by the server** with the effective price (override, else target price). Whatever the client sent is ignored. This is the fallback of decision 7;
- `price_override` without `linked_menu_item_id` -> `422`.

For every item with at least one linked option, `(group, name)` pairs (trimmed, exact case) must be unique among its options -> otherwise `422` (needed because matching is by name + group).

Options without a link are validated and stored exactly as today.

## FR-L2: Deleting a menu item (`DELETE /menu-items/{id}`)
After the existing checks (404, "on an active order" 400), if any **other, non-deleted** menu item has an option whose `linked_menu_item_id` equals this id -> `400`, with a `detail` text that names the holders, for example:
`Cannot delete 'Fried Egg' because it is linked as an add-on by: Noodle Soup (id 12), Fried Rice (id 15). Remove the link first.`
Up to 20 holders are listed, then `and N more`. Nothing is deleted or changed. Soft-deleted holders do not block. After the links are removed the delete works as before. Category delete is unaffected (it already refuses categories with active items).

## FR-L3: Keeping the stored price in sync
When `PUT /menu-items/{id}` changes `price` of an item, then **in the same database transaction** every non-deleted holder's options that link to it **and have no `price_override`** get `option.price = new price`. After the commit, `menu_item_updated` is broadcast for the changed item **and for each changed holder** (so waiter screens refresh). Nothing else about the holders changes. If the update fails, neither the target nor the holders change.
This is a small extension of decision 7 so the fallback does not go stale; the order-time rule (FR-L4) never trusts it while the target is alive.

## FR-L4: Ordering (`create_order` both branches, `submit_order`)
For each selected add-on of a line, the server looks for an option of that menu item with the same `name` and `group` (a missing group means `""`) that has a `linked_menu_item_id`:
- **Found:** the line uses the effective price computed **now**; the price and `linked_menu_item_id` sent by the client are ignored; the snapshot stores `{name, price, group, quantity, linked_menu_item_id}`.
- **Not found, or the option is not linked:** unchanged from today - the client's price is used and nothing extra is stored. A `linked_menu_item_id` sent by a client for such a modifier is dropped.
- The computed price goes through the same limits as today (`ModifierMoney`, line total not negative / finite -> `400` before anything is saved).
- The line `subtotal` formula is unchanged: `(discounted_base + unit_tax + sum(price * quantity)) * qty`.
- A sold-out (`is_available = false`) target does not affect the add-on.

## FR-L5: Money history is untouched
Changing the target's price changes **future** orders only. Existing order lines (open or paid), totals, receipts, kitchen payloads, Order History and reports are never recomputed (they read `subtotal` and the `selected_modifiers` snapshot). Locked in by tests.

## FR-L6: Admin form (`static/counter.js`, `static/counter.html`)
Each option row: `name` | **Link to menu item** (select: "None" + all non-deleted menu items except the one being edited; each shown as "name - price") | price | remove.
- Choosing a target when `name` is empty fills `name` with the target's name; if the name is not empty it is left alone; the field is always editable.
- Linked row, no override: the price field shows the target's price, read-only, with a "Custom price" action that opens an override field. Linked row with override: the override is editable, with a "Follow main item price" action that clears it.
- Choosing "None" turns the row back into a normal option (keeps the shown price as its own price, clears `price_override`).
- Save sends `name`, `price` (target price, or the override), `linked_menu_item_id`, `price_override`. The server recalculates `price` anyway (FR-L1).
- `flattenModifierOptions`, `wrapModifierOptions`, `collectModifiersEditorState` must carry the two new keys, otherwise saving would silently drop the link.
- Server errors (`404` / `422`) are shown to the admin with the server's text.
- Delete: the `400` text with the holder list is shown as it is.

## FR-L7: Waiter screen (`static/waiter.js`)
- Option prices come from `modifiers_config[].options[].price` (kept in sync by FR-L3), so the picker needs no new field.
- On `menu_item_updated` for an item, cart lines of that item re-read their linked options' prices from the new `modifiers_config` (matching name + group) and recompute the line preview. The server stays authoritative (FR-L4).
- `selected_modifiers` sent in an order may include `linked_menu_item_id`; the server ignores it.

## Defaults chosen by the assistant (please confirm or change)
| # | Default | Why |
|---|---------|-----|
| D1 | An option cannot link to its own holder (`422`) | avoids a self-blocking delete and confusion; can be relaxed later |
| D2 | `price_override` range `0 ... 1,000,000,000`; negative overrides not allowed | a linked add-on is a priced item; negative stays possible for unlinked options as today |
| D3 | Server fills a blank name of a linked option from the target | API clients get the same behaviour as the form |
| D4 | Duplicate `(group, name)` is refused only for items that have a linked option | existing menus with duplicate names keep working |
| D5 | Stale cart with a renamed linked option: no match -> treated as unlinked, client price used | no ids in this step (decision 5); the waiter preview is refreshed by FR-L7 so this is rare |
| D6 | Soft-deleted holders and the holder itself never block a delete | they cannot be ordered |
| D7 | Cycles (A links B, B links A) are allowed | only the target's `price` is read, never its add-ons, so there is no recursion |
| D8 | FR-L3 also syncs `option.price` when the target's price changes (not only on save) | otherwise the fallback goes stale |
| D9 | A target with price `0` gives a `0` add-on (no error) | price `0` is allowed in the menu today |
| D10 | `POST /menu-items/upload` has no modifiers input at all (checked in the code), so there is nothing to validate there | the rules live in one function used by create and update |

## Out of scope
- Option ids; add-on sales report by `linked_menu_item_id` (the snapshot only prepares for it); linking to the target's discount/takeaway/tax; scheduled prices; price history.
- Server-side re-checking of **unlinked** add-on prices against the menu (still taken from the client, as today).

## Contract impact
- `schemas.py` first: `ModifierOption`, `SelectedModifier`, validators; then router and UI.
- Docs at implementation time: `specs/api-reference.md`, `specs/database-schema.md` (JSON shape of `modifiers_config` and `selected_modifiers`), `specs/feature-priced-modifiers/requirements.md` (pointer), `CHANGELOG.md`.
