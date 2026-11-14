# Requirements: Priced Modifiers (Sub-menu toppings)

## Purpose
Support priced add-ons (အကြော် / ထည့်စရာ) on any menu item without exploding SKUs. Instruction-only tags remain separate (no price impact).

## Actors
- Admin: configure modifier groups per menu item
- Waiter: select toppings + qty when ordering
- Kitchen: see per-item composition on tickets
- Cashier: see priced line totals and modifier breakdown

## Data contract

### `ModifierOption` / `ModifierGroup` (menu `modifiers_config`)
Unchanged shape: `{ group, is_required, options: [{ name, price }] }`.
Applies to **any** menu item (not mohinga-only).

### `SelectedModifier` (order line)
| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Required |
| `price` | float | Unit price of one topping unit |
| `group` | string \| null | Optional group label |
| `quantity` | int ≥ 1 | Default `1` when omitted (backward compatible) |

Line modifier money: `sum(price * quantity)` over selected modifiers.
Order line subtotal (existing formula): `(discounted_base + unit_tax + modifiers_total) * line_qty`.

## Functional requirements

### FR-1 Admin configuration
- Menu create/update payload must persist admin-edited `modifiers_config` (must not force `[]`).
- Counter UI is **option-only**: add/edit/remove toppings as `{ name, price }` (no group name field in the UI).
- Saved shape remains one optional API group: `[{ group: "", is_required: false, options: [...] }]` for contract compatibility.
- Empty config remains valid (item has no sub-menu).

### FR-2 Waiter selection + qty
- Optional group: each option has qty stepper; qty `0` = not selected; qty ≥ 1 selects that option.
- Required group: waiter must pick one option (radio); quantity defaults to 1.
- Special instruction chips/tags stay note-only and do not change price.
- Cart line key includes modifier name + quantity so different topping mixes do not merge incorrectly.
- Cart / modal totals use `price * quantity`.

### FR-3 Kitchen ticket (Pattern A)
Per printed item ticket:
```
{line_qty}x {item_name}
   + {modifier_name} x{modifier_qty}
   *** Note: {note} ***   # only if note present
```
One ticket remains one order line (per-bowl composition). No batch-only aggregate summary in v1.

### FR-4 Cashier / receipt
- Checkout item list shows modifiers under the item name (name × qty).
- Line `subtotal` already includes modifier money when modifiers were submitted.
- Printed cashier receipt lists the same modifier lines under each item.

## Non-goals
- Replacing tags with modifiers for non-priced instructions
- Auto-seeding မုန့်ဟင်းခါး modifiers (admin configures per shop)

## Acceptance criteria
- AC-1: Saving menu item with a modifier group round-trips via API/UI.
- AC-2: Order line with `ပဲကြော်` qty 2 at unit 500 adds 1000 to that line’s modifier total.
- AC-3: Kitchen ticket text includes `+ ပဲကြော် x2` under the parent item.
- AC-4: Cashier checkout HTML and receipt text show selected modifiers.
- AC-5: Note-only tags still do not change price.
