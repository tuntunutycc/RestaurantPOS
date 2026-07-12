# Requirements: Waiter Two-Pane Layout & Active Order Modal

## Purpose
Improve Waiter speed and visibility with a clear **two-pane** floor workspace. Occupied-table / active-takeaway details open in a **pop-out modal** so viewing an existing order never replaces or clears the new-order cart.

## Explicit non-goals
- No changes to order submit, pricing, cancel-item API contracts, takeaway append, or WebSocket refresh logic.
- No rewrite of cart math or item-status toggle handlers — only **where** details are displayed.

## FR-TP1: Two-pane layout
On `/waiter` (`static/waiter.html`), the main workspace uses a responsive two-column grid (`md:grid-cols-2`):

| Pane | Contents | Visual cue |
|------|----------|------------|
| **Left — Menu & Cart** (`#waiter-pane-menu`) | Category tabs, menu grid, cart lines, price breakdown, Submit | Light green tint (`bg-emerald-50/60`) |
| **Right — Floor** (`#waiter-pane-floor`) | Zone tabs, Walk-in Takeaway, table grid, active takeaways, selected label | Light rose tint (`bg-rose-50/60`) |

- Empty (available) table click: set dine-in cart context only — **do not** open the modal.
- Occupied table / active takeaway click: open **Active Order Modal** — **do not** clear or override `activeOrderContext` / cart contents.

## FR-TP2: Active Order Modal
- Element: `#active-order-modal` (centered overlay) + `#active-order-modal-backdrop` (or shared backdrop).
- Opened when Waiter taps an **occupied** table or an **active** walk-in takeaway card.
- Must include a prominent **Close (✖)** control (`#active-order-modal-close` / existing close binding).
- Backdrop click dismisses the modal.
- Modal body reuses existing details rendering (`#waiter-table-details-content`): price breakdown, item rows, Cancel Item, served toggle, **Add More Items**.
- Closing clears modal content state via existing `closeDetailsSidebar()` semantics (order-details context only); cart remains untouched unless user explicitly clears / Add More Items.

## FR-TP3: Add More Items
Unchanged behavior: sets append context from the viewed order, closes the modal, focuses the cart in the left pane.

## Related
- `specs/feature-waiter-cart-breakdown/` — cart footer breakdown + Submit
- `specs/feature-walk-in-takeaway/` — takeaway list + append
- `specs/feature-order-cancellation/` — item cancel inside modal
- `specs/feature-table-all-view/` — ALL zone tab + Free/Occupied labels
