# Plan: Promoted Items & Waiter Incentives

## Context
Phase 4b delivered promoted-item tracking on `main`. This plan documents schema, API, UI, and validation — **no greenfield build** unless gaps are found in QA.

## Phase 1 — Schema & contracts
| Step | Detail |
|------|--------|
| Column | `MenuItem.is_promoted` BOOLEAN NOT NULL DEFAULT FALSE |
| Migration | `main.py` lifespan `ALTER TABLE menu_items ADD is_promoted` |
| Schemas | `MenuItemCreate/Update/Response.is_promoted`; `PromotedStaffSalesResponse` |
| Spec | `requirements.md` FR-P1–FR-P3 |

**No new tables.** Incentives derived from existing `order_items` + `menu_items` + `users`.

## Phase 2 — Backend API
| Endpoint | File | Access |
|----------|------|--------|
| `PUT /api/menu-items/{id}/toggle-promoted` | `routers/menu.py` | admin panel |
| `GET /api/reports/sales/promoted-by-waiter` | `routers/reports.py` | root, admin, waiter (self) |

Query design (see `requirements.md` FR-P2):
1. Filter orders by `created_at` range and `status`
2. Join order lines; exclude `cancelled`
3. Join menu item where `is_promoted`
4. Group by `created_by_id` user

## Phase 3 — Frontend
| Surface | File |
|---------|------|
| Menu promote toggle | `counter.html`, `counter.js` |
| Promo badge on order UI | `waiter.js` |
| Incentives dashboard | `counter.html` (`dashboard-tab-incentives`), `counter.js` (`loadPromotedIncentivesReport`) |

## Phase 4 — Tests
| Test | File |
|------|------|
| E2E promoted flow | `test_promoted_items_full_flow` in `test_rbac.py` |
| Account denied | same test (`403` for account) |
| UI contract | `test_phase4b_promoted_ui_contract` |

Add `validation.md` when formal merge checklist is required.

## Phase 5 — Optional enhancements (require spec amendment first)
- `?role=waiter` filter on promoted report (waiter-only incentive view)
- Cashier read-only incentives view
- Export CSV for payroll

**Exit criteria:** FR-P1–FR-P3 verified; `test_promoted_items_full_flow` passes.
