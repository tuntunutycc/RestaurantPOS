# Implementation Reference: Counter / Admin UI

Frontend-only surface: `static/counter.html`, `static/counter.js`.  
Stack: static HTML + Tailwind CDN + vanilla JavaScript (no Next.js).

## Main navigation tabs

Primary tabs on `/counter`: Dashboard, Cashier / Billing, Menu Management, Staff Management, Admin Accounts, Audit Logs, Table Management (visibility role-gated in `applyAdminOnlyTabVisibility`).

**Requirements:** `specs/feature-counter-ui/requirements.md` (FR-N1–FR-N3).

### Primary vs secondary styling (2026-07-06)

| Class | Applied to | Visual |
|-------|------------|--------|
| `tab-btn tab-btn-primary` | Dashboard, Cashier / Billing, Menu Management | Larger padding, rounded top, slate-50 idle / blue-100 active, bold active label, shadow when active |
| `tab-btn` only | Staff, Admin Accounts, Audit Logs, Tables | Standard underline active state (blue-50 / blue-700) |

### Active tab state

| Piece | Location | Behavior |
|-------|----------|----------|
| CSS | `counter.html` `<style>` | `.tab-btn.active` — all tabs; `.tab-btn-primary.active` — enhanced primary trio |
| JS | `counter.js` | `setActiveMainTab(panel)` removes `.active` from all `.tab-btn[data-target-panel]`, adds to matching tab |
| Default | `counter.js` | `applyAdminOnlyTabVisibility` → `showPanel` on first load |
| Fallback HTML | `counter.html` | `tab-cashier` ships with `active` until JS runs (cashier-only no-dashboard case) |

**Click handling:** Direct listeners on tab buttons + delegated `document` click on `.tab-btn[data-target-panel]` both call `showPanel(targetPanel)`.

Dashboard **sub-tabs** (Overview, History, Staff, etc.) use `applyDashboardTabState` — separate from main nav `.active`.

## Related docs

- Role-gated tab visibility: `specs/feature-rbac/implementation.md` §5 Counter tabs by role
- Category CRUD in Menu Management panel: `specs/feature-category-crud/`
- Table management panel: `specs/feature-table-management/`
