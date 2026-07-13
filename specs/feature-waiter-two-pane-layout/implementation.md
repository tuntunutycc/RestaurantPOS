# Implementation: Waiter Two-Pane Layout

## HTML (`static/waiter.html`)
- `#waiter-main-grid` — `grid md:grid-cols-2` side-by-side panes
- `#waiter-pane-menu` — menu + cart — **rose** tint (`bg-rose-50`, `border-rose-100`)
- `#waiter-pane-floor` — zone/table/takeaway — **emerald** tint (`bg-emerald-50`, `border-emerald-100`)
- `#active-order-modal` — fixed centered overlay; `#active-order-modal-close` = **✖ Close**
- Keeps `#waiter-table-details-content`, `#waiter-table-details-add-more`, `#waiter-table-details-close` for JS compatibility

## JS (`static/waiter.js`)
- `openDetailsSidebar()` / `closeDetailsSidebar()` toggle `#active-order-modal` via `hidden` only (does **not** touch `cart` Map or qty helpers)
- Occupied / takeaway → `openOrderDetails` / modal; available tables → `setActiveOrderContext` only
- Cart qty: `increaseCartItemQty` / `decreaseCartItemQty` unchanged (FR-WB1c)
