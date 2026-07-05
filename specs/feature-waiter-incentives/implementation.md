# Implementation Reference: Promoted Items & Waiter Incentives

**Status:** Done (Phase 4b on `main`, verified 2026-07-05)  
**Branch:** `main`

## Schema

| Column | Model | Migration |
|--------|-------|-----------|
| `MenuItem.is_promoted` | `models.py` | `main.py` lifespan `ALTER TABLE menu_items ADD is_promoted` |

**No `waiter_id` on `Order`.** Incentive attribution uses `OrderItem.created_by_id`.

## API

| Method | Path | Access | Behavior |
|--------|------|--------|----------|
| `PUT` | `/api/menu-items/{id}/toggle-promoted` | `ADMIN_PANEL_ROLES` | Flip `is_promoted` |
| `POST` | `/api/menu-items/` | `ADMIN_PANEL_ROLES` | Accepts `is_promoted` in body |
| `GET` | `/api/reports/sales/promoted-by-waiter` | root, admin (all); waiter (self); cashier/account **403** | Group by `created_by_id` user |

### Promoted report query (`routers/reports.py`)

```
OrderItem
  JOIN Order (paid/completed, date range)
  JOIN MenuItem ON menu_item_id AND is_promoted = true
  JOIN User ON created_by_id
GROUP BY user_id → quantity, total_sales, line_count
```

**Response:** `PromotedStaffSalesResponse` in `schemas.py`.

## Frontend (as-built)

| Surface | File |
|---------|------|
| Promote checkbox + toggle | `counter.html`, `counter.js` |
| ★ Promo badge | `waiter.js` |
| Waiter Incentives tab | `counter.html` (`dashboard-tab-incentives`), `counter.js` (`loadPromotedIncentivesReport`) |

## Tests

| File | Scenarios |
|------|-----------|
| `tests/test_waiter_incentives.py` | Toggle, report filtering, role denial, non-promoted exclusion |
| `tests/test_rbac.py` | `test_promoted_items_full_flow`, `test_phase4b_promoted_ui_contract` |

See `validation.md`.
