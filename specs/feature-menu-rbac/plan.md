# Plan: Menu Management RBAC

## Phase 1 — Spec & contract
1. Add `specs/feature-menu-rbac/` (this folder).
2. Update `specs/feature-rbac/requirements.md` §3.4 cashier restrictions.
3. Update `specs/api-reference.md` menu endpoint matrix.

## Phase 2 — Backend
1. `rbac.py`: `MENU_AVAILABILITY_ROLES = [root, admin, cashier]`.
2. `schemas.py`: `MenuItemAvailabilityUpdate { is_available: bool }`.
3. `routers/menu.py`: `PATCH /api/menu-items/{item_id}/availability` with role check + WebSocket broadcast.

## Phase 3 — Frontend
1. `counter.html`: `data-menu-admin-only` on admin sections; `id="menu-items-section"`.
2. `counter.js`: show Menu tab for cashier; `applyMenuPanelRoleVisibility()`; availability toggle switch for cashier; PATCH API helper.

## Phase 4 — Tests
1. `tests/test_menu_rbac_availability.py`: cashier POST → 403; cashier PATCH → 200; admin PATCH → 200; cashier PUT full update → 403.

## Validation
```bash
PYTHONPATH=. pytest tests/test_menu_rbac_availability.py -v
PYTHONPATH=. pytest -q
```
