# Implementation Reference: Cashier Reports & Ordering Inheritance

**Status:** Done (as-built on `main`, verified 2026-07-05)  
**Branch:** `main`  
**Related:** `specs/feature-rbac/implementation.md` § Counter dashboard

## Role inheritance (FR-C1)

| Constant | `rbac.py` |
|----------|-----------|
| `POS_ORDER_ROLES` | `root`, `admin`, `cashier`, `waiter` |
| `CHECKOUT_ROLES` | `root`, `admin`, `cashier` (waiter excluded) |

| Surface | File | Notes |
|---------|------|-------|
| Order submit | `routers/orders.py` | `require_roles(POS_ORDER_ROLES)`; sets `OrderItem.created_by_id = current_user.id` |
| Waiter UI | `static/waiter.js` | `requireRole(['waiter','admin','root','cashier'])` |
| Take Orders nav | `static/auth.js` | Shown for `cashier` and `waiter` |

## Cashier own daily sales (FR-C2)

| Method | Path | Scoping |
|--------|------|---------|
| `GET` | `/api/reports/summary/today` | Cashier: `Order.checked_out_by_id == current_user.id` |

**Frontend:** `counter.js` → `applyDashboardRoleVisibility` — KPI label **"My Checkout Sales (Today)"** for cashier.

## Waiter / order-staff breakdown (FR-C3)

| Method | Path | Roles |
|--------|------|-------|
| `GET` | `/api/reports/sales/by-order-staff` | `root`, `admin`, `cashier` → all; `waiter` → self; `account` → `403` |

**Attribution:** `OrderItem.created_by_id`; paid/completed orders; non-cancelled lines.

**Frontend:** Counter → Dashboard → Staff Performance → `loadStaffBreakdownCharts()` → `fetchStaffSales('by-order-staff', ...)`.

| Method | Path | Cashier scoping |
|--------|------|-----------------|
| `GET` | `/api/reports/sales/by-cashier` | Cashier sees **self only** |

## Schema (no migration required)

- `Order.checked_out_by_id` → cashier checkout
- `OrderItem.created_by_id` → order-line staff (waiter or cashier)

## Tests

| File | Scenarios |
|------|-----------|
| `tests/test_cashier_reports.py` | Submit as cashier, own summary, staff breakdown, scoping |
| `tests/test_orders_rbac.py` | Cashier checkout allowed |
| `tests/test_rbac.py` | `test_per_cashier_and_waiter_reports`, `test_checkout_sets_checked_out_by_id` |

See `validation.md` for merge checklist.
