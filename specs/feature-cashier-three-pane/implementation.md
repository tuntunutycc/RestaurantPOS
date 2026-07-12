# Implementation: Cashier 3-Pane Billing Layout

## HTML
- `#panel-cashier` → `#cashier-three-pane` grid with `#pane-tables`, `#pane-takeaways`, `#pane-checkout`
- Checkout markup remains static under `#receipt-container` (not destroyed on select)

## JS
- `selectOrder()` / `clearCheckoutSelection()` / payment listeners unchanged in behavior
- Table and takeaway clicks still call `selectOrder`
- Optional: `data-cashier-selected` highlight on the active card

## Out of scope
- Counter `showPanel` / primary tab switching
