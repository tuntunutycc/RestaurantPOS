# Requirements: Counter / Admin Primary Navigation UX

## Purpose
Ensure the three highest-traffic Counter surfaces — **Dashboard**, **Cashier / Billing**, and **Menu Management** — are visually distinct from secondary admin tabs (Staff, Tables, Audit Logs, etc.) so floor and back-office users can orient quickly.

## FR-N1: Primary navigation tabs
The following main tabs MUST use enhanced styling (`tab-btn-primary` in `counter.html`):

| Tab | Panel id | Typical roles |
|-----|----------|---------------|
| Dashboard | `panel-dashboard` | root, admin, cashier (when dashboard visible) |
| Cashier / Billing | `panel-cashier` | root, admin, cashier |
| Menu Management | `panel-menu` | root, admin |

Secondary tabs (Staff Management, Admin Accounts, Audit Logs, Table Management) use base `.tab-btn` styling only.

## FR-N2: Active state
- Exactly one main tab carries `.active` at a time (`setActiveMainTab` in `counter.js`).
- Active primary tab: stronger background (`blue-100`), **bold** label (`font-weight: 700`), blue bottom border, subtle top shadow.
- Inactive primary tabs: `slate-50` background, `slate-600` text, visible bottom border on hover.
- Clicking any `.tab-btn[data-target-panel]` calls `showPanel` → updates `.active`.

## FR-N3: Default panel
- First visible panel on load follows `applyAdminOnlyTabVisibility` (Dashboard when dashboard tab shown; otherwise Cashier / Billing).

## Out of scope
- Dashboard **sub-tabs** (Overview, History, Staff) — separate `applyDashboardTabState` contract.
- Payment method breakdown — see `specs/feature-payment-method-analytics/`

## Related
- `specs/feature-menu-category-navigation/` — category pills on Menu Management menu list and waiter grid
- `specs/feature-counter-ui/implementation.md`
- `specs/feature-category-crud/` — Menu Management panel content
