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
| **Left — Menu & Cart** (`#waiter-pane-menu`) | Category tabs, menu grid, cart lines with inline qty `+`/`-` (FR-WB1c), price breakdown, Submit | Subtle **rose/red** tint (`bg-rose-50` / `border-rose-100`) |
| **Right — Floor** (`#waiter-pane-floor`) | Zone tabs, Walk-in Takeaway, table grid, active takeaways, selected label | Subtle **green/emerald** tint (`bg-emerald-50` / `border-emerald-100`) |

- Empty (available) table click: set dine-in cart context only — **do not** open the modal.
- Occupied table / active takeaway click: open **Active Order Modal** — **do not** clear or override `activeOrderContext` / cart contents.

## FR-TP2: Active Order Modal
- Element: `#active-order-modal` (fixed full-screen overlay, `z-50`) + `#active-order-modal-backdrop` (`z-40`).
- Opened when Waiter taps an **occupied** table or an **active** walk-in takeaway card on the **green floor pane**.
- Must include a prominent **✖ Close** / Exit control at top-right (`#active-order-modal-close`) and a footer close (`#waiter-table-details-close`).
- Backdrop click and panel-outside click dismiss the modal.
- Modal body reuses existing details rendering (`#waiter-table-details-content`): price breakdown, item rows (static qty), Cancel Item, served toggle, **Add More Items**. No cart qty `+`/`-` in this modal.
- Closing clears modal content state via existing `closeDetailsSidebar()` semantics (order-details context only); **unsubmitted New Order Cart is never cleared** by open/close (qty adjusters FR-WB1c remain intact).

## FR-TP3: Add More Items
Unchanged behavior: sets append context from the viewed order, closes the modal, focuses the cart in the left pane.

## Related
- `specs/feature-waiter-cart-breakdown/` — cart footer breakdown + Submit
- `specs/feature-walk-in-takeaway/` — takeaway list + append
- `specs/feature-order-cancellation/` — item cancel inside modal
- `specs/feature-table-all-view/` — ALL zone tab + Free/Occupied labels
