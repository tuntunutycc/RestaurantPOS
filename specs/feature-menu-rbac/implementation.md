# Implementation: Menu Management RBAC

## Backend
- `rbac.MENU_AVAILABILITY_ROLES` — `[root, admin, cashier]`
- `schemas.MenuItemAvailabilityUpdate` — `{ is_available: bool }`
- `routers/menu.py`:
  - `PATCH /api/menu-items/{item_id}/availability` — `require_roles(MENU_AVAILABILITY_ROLES)`
  - Existing POST/PUT/DELETE remain `ADMIN_PANEL_ROLES`
  - Legacy `PUT …/toggle-availability` unchanged (admin only)

## Frontend (`static/counter.js`, `static/counter.html`)
- `isMenuAdminPanelRole()`, `applyMenuPanelRoleVisibility()`
- Menu tab visible for cashier; admin sections use `data-menu-admin-only`
- Cashier: toggle switch → `PATCH …/availability`
- Admin: full CRUD buttons; availability uses PATCH via `setMenuItemAvailability()`

## Waiter
- Existing sold-out styling + WebSocket handler in `waiter.js` (no change required)

## Tests
- `tests/test_menu_rbac_availability.py` — 5 scenarios
