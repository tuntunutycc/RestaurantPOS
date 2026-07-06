# Implementation Reference: Counter / Admin UI

Frontend-only surface: `static/counter.html`, `static/counter.js`.  
Stack: static HTML + Tailwind CDN + vanilla JavaScript (no Next.js).

## Main navigation tabs

Primary tabs on `/counter`: Dashboard, Cashier / Billing, Menu Management, Staff Management, Admin Accounts, Audit Logs, Table Management (visibility role-gated in `applyAdminOnlyTabVisibility`).

### Active tab state (2026-07-04)

**Goal:** Clear visual feedback for the selected main navigation tab.

| Piece | Location | Behavior |
|-------|----------|----------|
| CSS | `counter.html` `<style>` | `.tab-btn.active` — blue bottom border, blue-50 background, semibold blue-700 text |
| JS | `counter.js` | `setActiveMainTab(panel)` removes `.active` from all `.tab-btn[data-target-panel]`, adds to the tab whose `data-target-panel` matches the visible panel `id` |
| Default | `counter.js` | `applyAdminOnlyTabVisibility` calls `showPanel` on first load: **Dashboard** for admin/root/cashier (when dashboard visible); **Cashier / Billing** when dashboard hidden |
| Fallback HTML | `counter.html` | `tab-cashier` ships with `active` until JS runs (cashier-only no-dashboard case) |

**Click handling:** Direct listeners on tab buttons + delegated `document` click on `.tab-btn[data-target-panel]` both call `showPanel(targetPanel)`.

Dashboard **sub-tabs** (Overview, History, Staff, etc.) continue to use `applyDashboardTabState` with Tailwind class toggles — separate from main nav `.active`.

## Related docs

- Role-gated tab visibility: `specs/feature-rbac/implementation.md` §5 Counter tabs by role
- Table management panel: `specs/feature-table-management/`
