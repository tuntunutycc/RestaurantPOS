# Implementation: Waiter Two-Pane Layout

## HTML (`static/waiter.html`)
- `#waiter-main-grid` — two panes
- `#waiter-pane-menu` — menu + cart
- `#waiter-pane-floor` — zone/table/takeaway
- `#active-order-modal` — centered overlay replacing slide-out sidebar
- Keeps `#waiter-table-details-content`, `#waiter-table-details-add-more`, `#waiter-table-details-close` for JS compatibility

## JS (`static/waiter.js`)
- `openDetailsSidebar()` / `closeDetailsSidebar()` toggle `#active-order-modal` via `hidden` (no slide transform)
- Occupied / takeaway still call `openOrderDetails` / `openTableDetailsSidebar`
- Available tables still call `setActiveOrderContext` only
