# Requirements: Cashier 3-Pane Billing Layout

## Purpose
Give cashiers a single-page billing workspace with maximum visibility: **Tables | Takeaways | Check Out** — no nested takeaways under the table grid and no modal for order selection.

## Explicit non-goals
- Do **not** remove Counter primary navigation (`Dashboard` / `Cashier` / `Menu` / …).
- Do **not** change checkout API contracts, money math, payment-method persistence, Served-by display, or print receipt flow.
- Do **not** recreate the checkout form DOM on each selection (would break bound listeners).

## FR-C3P1: Three-pane grid
Inside `#panel-cashier` (`static/counter.html`):

| Pane | Element | Contents |
|------|---------|----------|
| Left | `#pane-tables` | Zone tabs + table floor grid (Free / Occupied labels) |
| Middle | `#pane-takeaways` | Active walk-in takeaway list |
| Right | `#pane-checkout` | Checkout form + empty-state placeholder |

Layout: `grid grid-cols-1 lg:grid-cols-3 gap-4` with each pane `overflow-y-auto` and a bounded height on large screens so the page shell stays stable while lists scroll independently.

## FR-C3P2: Selection → Check Out pane
- Available table → alert empty (unchanged); do not load checkout.
- Occupied table → `fetchActiveOrderByTable` → `selectOrder(order)` fills `#receipt-container` in `#pane-checkout`.
- Takeaway card → `selectOrder(order)` overrides the Check Out pane with that order.
- Empty state (`#receipt-placeholder`): “Select a table or takeaway order to process payment.”

## FR-C3P3: Checkout controls (preserve)
Right pane must keep existing controls (IDs unchanged):

- Item list (`#receipt-content`), Served by (`#receipt-served-by`)
- Subtotal / Discount / Tax / Grand Total
- Discount type/value, Cash / Mobile Money toggle, amount tendered, change
- Confirm Payment (`#btn-process-payment`) + browser print receipt after success

## Related
- `specs/feature-payment-method-analytics/` — payment method toggle
- `specs/feature-walk-in-takeaway/` — takeaway display + Served by
- `specs/feature-table-all-view/` — Free status labels
- `specs/feature-counter-ui/` — primary nav tabs (unchanged)
