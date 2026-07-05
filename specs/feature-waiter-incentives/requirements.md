# Requirements: Promoted Items & Waiter Incentives

## Purpose
Track menu items marked as **Promoted** and attribute promoted-item sales to order-taking staff so management (`root`, `admin`) can calculate waiter incentives (daily/monthly).

Aligns with `specs/feature-rbac/requirements.md` §4.2.

## Status
**As-built on `main` (Phase 4b, 2026-07-04).** Schema and APIs exist; this spec formalizes the contract.

---

## FR-P1: Mark menu item as Promoted

| Item | Contract |
|------|----------|
| Schema | `MenuItem.is_promoted` boolean, default `false`, indexed |
| Admin toggle | `PUT /api/menu-items/{id}/toggle-promoted` — `ADMIN_PANEL_ROLES` |
| Create form | `is_promoted` on `POST /api/menu-items/` body |
| List UI | Counter → Menu Management: checkbox, **Promote/Unpromote** button, **★ Promoted** badge |
| Ordering UI | `waiter.js` / menu list: **★ Promo** badge + visual highlight on promoted cards |

**Rule:** `is_promoted` affects reporting and UI only; does not change price or checkout logic.

---

## FR-P2: Waiter vs. Promoted Items Sold report

Management needs a report: **per staff member**, how many promoted items they sold and the revenue, for a **daily or monthly** date range.

| Item | Contract |
|------|----------|
| API | `GET /api/reports/sales/promoted-by-waiter?start_date=&end_date=` |
| Response model | `PromotedStaffSalesResponse`: `user_id`, `username`, `role`, `total_sales`, `quantity`, `line_count` |
| Roles | `root`, `admin` → all staff; `waiter` → self only; `cashier`, `account` → **403** |
| Order filter | `Order.status IN ('paid','completed')`; `OrderItem.item_status != 'cancelled'` |
| Promoted filter | `MenuItem.is_promoted == true` (join on current menu row; historical lines use `menu_item_id`) |
| Attribution | `OrderItem.created_by_id` → staff who submitted the order batch |
| Aggregation | `GROUP BY` user; `SUM(quantity)`, `SUM(subtotal)`, `COUNT(order_item.id)` |
| Date window | `Order.created_at` within `[start_date 00:00, end_date+1 00:00)` UTC |

**Incentive use:** `quantity` and `total_sales` per staff row are the canonical inputs for management incentive calculations (rate applied outside POS).

---

## FR-P3: Dashboard UI (Waiter Incentives)

| Item | Contract |
|------|----------|
| Location | Counter → Dashboard → **Waiter Incentives** subtab |
| Visibility | `root`, `admin` only (`data-role-section="incentives"`) |
| Controls | `incentives-start-date`, `incentives-end-date`, Load Report |
| Outputs | Bar chart (`promotedIncentivesChart`) + detail table (staff, role, qty, revenue) |
| API | `GET /api/reports/sales/promoted-by-waiter` |

---

## Data model Q&A (canonical answers)

### Do we need `is_promoted` on `MenuItem`?
**Yes — already present.** Boolean flag on `menu_items`; migrated via `main.py` lifespan (`ALTER TABLE` for SQLite).

### Does `Order` / `OrderItem` track waiter?
**No separate `waiter_id` on `Order`.** Attribution is per line:
- `OrderItem.created_by_id` → user who created the batch (waiter or cashier)
- Set at `POST /api/orders/submit` from JWT `current_user.id`
- `Order.checked_out_by_id` is for **cashier checkout**, not waiter incentives

Historical integrity: `OrderItem` snapshots (`menu_item_name_at_sale`, etc.) preserve reports if menu changes.

### How does the incentive API group data?
```text
OrderItem
  JOIN Order (paid/completed, date range)
  JOIN MenuItem (is_promoted = true)
  JOIN User ON OrderItem.created_by_id = User.id
GROUP BY User.id, User.username, User.role
→ quantity, total_sales (subtotal sum), line_count
```

Staff with `role=cashier` appear if they submitted promoted lines (same attribution field).

---

## Reporting matrix (promoted)

| Capability | root | admin | cashier | waiter | account |
|------------|------|-------|---------|--------|---------|
| Toggle `is_promoted` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `promoted-by-waiter` (all) | ✓ | ✓ | ✗ | self | ✗ |
| Incentives dashboard | ✓ | ✓ | ✗ | ✗ | ✗ |

---

## Out of scope
- Automatic incentive payout / payroll integration
- Per-item incentive rates (fixed rules in admin settings)
- PostgreSQL-specific migrations (SQLite `ALTER` acceptable per roadmap)

## Related specs
- `specs/feature-cashier-reports/requirements.md` — cashier ordering (not incentives)
- `specs/feature-rbac/requirements.md` — §4.2, report matrix §8
