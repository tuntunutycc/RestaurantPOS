# Plan: Cashier Reports & Ordering Inheritance

## Context
Requirements FR-C1–FR-C3 are **already implemented** on `main`. This plan defines verification steps and the SDD sequence for any future amendments.

## Phase 1 — Contract (this document)
| Step | Detail |
|------|--------|
| Spec | `requirements.md` — FR-C1, FR-C2, FR-C3 |
| Cross-ref | Link from `specs/feature-rbac/requirements.md` |
| Schemas | Reuse `TodaySalesSummaryResponse`, `StaffSalesPointResponse` (no new Pydantic types) |

## Phase 2 — Backend (as-built — verify only)
| Component | Location | Notes |
|-----------|----------|-------|
| Role sets | `rbac.py` | `POS_ORDER_ROLES`, `CHECKOUT_ROLES` |
| Cashier today filter | `routers/reports.py` `get_today_sales_summary` | `checked_out_by_id` filter |
| Waiter breakdown | `routers/reports.py` `get_sales_by_order_staff` | `_ORDER_STAFF_ROLES` |
| Order attribution | `routers/orders.py` `submit_order` | `created_by_id=current_user.id` |
| Checkout attribution | `routers/orders.py` checkout handlers | `checked_out_by_id` |

**Schema:** No migration required. Uses existing:
- `Order.checked_out_by_id` → cashier checkout attribution
- `OrderItem.created_by_id` → waiter/cashier order-line attribution

## Phase 3 — Frontend (as-built — verify only)
| Surface | File | Behavior |
|---------|------|----------|
| Waiter screen access | `waiter.js` | cashier in `requireRole` |
| Take Orders | `auth.js` | link for cashier/waiter |
| Cashier KPI | `counter.js` | `applyDashboardRoleVisibility` — own checkout label |
| Staff charts | `counter.js` | `loadStaffBreakdownCharts` → `by-order-staff` |

## Phase 4 — Tests & validation
| Test | File | Covers |
|------|------|--------|
| Cashier today scoped | extend or manual QA | `summary/today` |
| by-order-staff | `test_per_cashier_and_waiter_reports` | root + date range |
| Cashier submit | `test_waiter_cannot_checkout_but_can_submit` pattern | cashier submit |
| UI contract | `test_phase4_dashboard_ui_contract` | staff charts |

Create `validation.md` when merge checklist is needed.

## Phase 5 — SDD close-out
- `implementation.md` (optional) — as-built reference
- `CHANGELOG.md` entry only if behavior changes

**Exit criteria:** All FR-C1–FR-C3 automated checks pass; manual cashier QA sign-off on Dashboard + `/waiter`.
