# Plan: Priced Modifiers (Sub-menu toppings)

## Goal
Let any menu item (မုန့်ဟင်းခါး and others) attach optional/required priced modifier groups so waiters can add toppings with quantity, totals include topping prices, kitchen tickets show per-bowl composition (Pattern A), and cashier UI/receipts show modifiers. Keep instruction tags (e.g. နံနံပင်ရှောင်) as free-text notes — not priced.

## Scope
1. Contract: `SelectedModifier.quantity` (default 1); line pricing = `sum(price * quantity)`.
2. Admin Counter UI: edit `modifiers_config` on menu create/update (not hard-coded empty).
3. Waiter modal: optional groups use per-option qty steppers; required groups stay single-choice.
4. Kitchen ticket Pattern A: list `+ {name} x{qty}` under the parent item; notes unchanged.
5. Cashier checkout panel + printed receipt: show modifiers under each line.
6. Automated tests for pricing with qty, kitchen ticket text, menu modifiers_config round-trip.

## Out of scope
- Combinatorial pre-built combo SKUs
- Aggregated kitchen summary (Pattern B)
- Changing predefined instruction tag behavior
