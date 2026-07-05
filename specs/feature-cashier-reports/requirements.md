# Requirements: Cashier Role — Ordering Inheritance & Sales Views

## Purpose
Formalize the `cashier` role contract for POS ordering inheritance, self daily sales, and operational waiter-performance visibility. Aligns with `specs/feature-rbac/requirements.md` §3.4 and reporting matrix §8.

## Status
**As-built on `main` (2026-07-04+).** This folder documents the contract for QA and future changes. No new schema columns required for these requirements.

---

## FR-C1: Role inheritance (cashier ⊇ waiter ordering)

The `cashier` role **must inherit all waiter ordering permissions** (take orders), while retaining exclusive checkout rights on the counter screen.

| Capability | Waiter | Cashier | Enforcement |
|------------|--------|---------|-------------|
| `POST /api/orders/submit` | ✓ | ✓ | `POS_ORDER_ROLES` in `rbac.py` |
| Order item status updates | ✓ | ✓ | `require_roles(POS_ORDER_ROLES)` on order routes |
| `GET /waiter` UI | ✓ | ✓ | `waiter.js` `requireRole(['waiter','admin','root','cashier'])` |
| Take Orders nav link | — | ✓ | `auth.js` — cashier + waiter |
| Checkout / payment | ✗ | ✓ | `CHECKOUT_ROLES`; waiter → `403` |

**Attribution rule:** When a cashier submits orders via `/waiter`, `OrderItem.created_by_id` = cashier user id (same field as waiter attribution).

---

## FR-C2: Cashier own daily sales (checkout-attributed)

A cashier **must** see only **their own** total daily sales (revenue from orders they checked out).

| Item | Contract |
|------|----------|
| API | `GET /api/reports/summary/today` |
| Scoping | When `current_user.role == cashier`, filter `Order.checked_out_by_id == current_user.id` |
| Response | `total_sales`, `total_orders`, `average_order_value` for today (UTC day window) |
| UI | Counter → Dashboard → Overview KPI: label **"My Checkout Sales (Today)"** for cashier |
| Must not | Include other cashiers' totals or store-wide totals |

**Money rule:** Uses `Order.total_amount` on `paid` / `completed` orders only (same as store summary).

---

## FR-C3: Global daily waiter sales view (root, admin, cashier)

`root`, `admin`, and `cashier` **must** be able to view **daily** (and by date range) sales **grouped by order-taking staff**, primarily for waiter performance monitoring.

| Item | Contract |
|------|----------|
| API | `GET /api/reports/sales/by-order-staff?start_date=&end_date=` |
| Roles | `root`, `admin`, `cashier` → all staff rows; `waiter` → self only; `account` → `403` |
| Attribution | `OrderItem.created_by_id` on paid/completed, non-cancelled lines |
| Grouping | `GROUP BY` staff `user_id`, `username`, `role` |
| Metrics | `total_sales` (sum `OrderItem.subtotal`), `order_count` (line count) |
| UI | Counter → Dashboard → **Staff Performance** → **Sales by Waiter / Order Staff** chart |
| Date range | Same `start_date` / `end_date` as cashier breakdown (see `FR-D1` in RBAC spec) |

**Clarification:** The API returns **all order-taking staff** (waiter and cashier rows when cashiers submit orders). UI title may say "Waiter / Order Staff". Optional future filter: `role=waiter` query param (out of scope unless requested).

**Cashier restriction:** Cashier **must not** see other cashiers' checkout totals (`by-cashier` scoped to self if called as cashier).

---

## Authorization summary

| Endpoint | root | admin | cashier | waiter | account |
|----------|------|-------|---------|--------|---------|
| `summary/today` (store) | all | all | **own checkout** | — | capped |
| `sales/by-order-staff` | all staff | all staff | all staff | self | **403** |
| `sales/by-cashier` | all | all | self | **403** | capped |

---

## Out of scope
- Cashier access to **Promoted Items / Incentives** report (see `specs/feature-waiter-incentives/`)
- Monthly store-wide sales widget for cashier
- Admin panel mutations for cashier

## Related specs
- `specs/feature-rbac/requirements.md` — §3.4, §8, FR-D1
- `specs/feature-waiter-incentives/requirements.md` — promoted-item tracking
