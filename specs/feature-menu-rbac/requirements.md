# Requirements: Menu Management RBAC (Admin vs Cashier)

## Purpose
Enforce strict role boundaries for menu mutations. **Admins (`root`, `admin`)** manage full menu CRUD. **Cashiers** may only toggle item availability (Sold Out / In Stock) during service — no create, price edit, or delete.

> **API paths:** This codebase uses `/api/menu-items/` (not `/api/menu/`). Contract aliases in docs refer to the same resources.

## Roles

| Capability | root | admin | cashier | waiter | account |
|------------|------|-------|---------|--------|---------|
| List menu items (`GET /api/menu-items/`) | yes | yes | yes | yes | yes* |
| Create menu item | yes | yes | **no** | no | no |
| Full update (price, name, tax, etc.) | yes | yes | **no** | no | no |
| Delete (soft) menu item | yes | yes | **no** | no | no |
| Set availability (`PATCH …/availability`) | yes | yes | **yes** | no | no |
| Category / printer / tag admin | yes | yes | no | no | no |

\* `account` has no POS ordering surface; list access follows authenticated API policy.

## FR-MR1: Admin-only mutations
These endpoints require `ADMIN_PANEL_ROLES` (`root`, `admin`):
- `POST /api/menu-items/`
- `POST /api/menu-items/upload`
- `PUT /api/menu-items/{item_id}` — full partial update including price
- `DELETE /api/menu-items/{item_id}`
- `PUT /api/menu-items/{item_id}/toggle-promoted` (admin panel only)

Non-admin callers receive **`403 Forbidden`**.

## FR-MR2: Availability patch (admin + cashier)
- **Endpoint:** `PATCH /api/menu-items/{item_id}/availability`
- **Body:** `{ "is_available": boolean }` (required)
- **Roles:** `root`, `admin`, `cashier`
- **Response:** `MenuItemResponse`
- **Realtime:** broadcast `menu_item_availability_toggled` with full item payload (same as legacy toggle)

Cashier must **not** change availability via `PUT /api/menu-items/{id}` (full update remains admin-only).

## FR-MR3: Model
`MenuItem.is_available` — boolean, default `true`, indexed. Soft delete sets `is_available=false`.

## FR-MR4: Counter UI
- **Admin panel roles:** full Menu Management tab (add/edit/delete, categories, printers, tags).
- **Cashier:** Menu Management tab visible with **availability-only** view:
  - Hide Add Menu, Edit, Delete, Promote, category forms, printer settings, instruction tags.
  - Show toggle switch per item calling `PATCH …/availability`.
- Role detection via JWT / `GET /api/auth/me` (`window.auth.getUser()`).

## FR-MR5: Waiter reactivity
When `is_available` is `false`:
- Waiter menu card: greyed out, Sold Out badge, add disabled.
- WebSocket `menu_item_availability_toggled` updates in-memory menu cache.

## Legacy endpoint
`PUT /api/menu-items/{item_id}/toggle-availability` remains **admin-only** (boolean flip, no body). New clients should prefer `PATCH …/availability`.
