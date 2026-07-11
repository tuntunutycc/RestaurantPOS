# Requirements: Menu Category Navigation & Filtering

## Purpose
Speed up menu browsing in **Counter → Menu Management** and the **Waiter** ordering grid with horizontal category pills and client-side filtering.

## Data sources (no new API required)
- `GET /api/menu-items/` — each item includes `category_id`
- `GET /api/categories/` — category id + name for tab labels

Filtering is **client-side** on the fully loaded menu array (fast; menu size is bounded for typical restaurant use).

## FR-CN1: Category pills
- Horizontal, scrollable row of pills/tabs above the menu list (counter) or menu grid (waiter).
- First pill is **ALL** (default active on load).
- Additional pills: one per category that has at least one menu item in the loaded set.

## FR-CN2: Filtering behavior
| Selection | Result |
|-----------|--------|
| **ALL** | Show every menu item |
| Category pill | Show only items where `menu_item.category_id === category.id` |

Active pill: solid highlight (e.g. blue background + white text). Inactive: outlined/muted.

## FR-CN3: Counter (Menu Management)
- Pills above `#menu-items-list` in `counter.html` / `counter.js`.
- `filterMenu(categoryKey)` — `'ALL'` or numeric category id; updates active pill and visibility of list rows (`hidden` class or equivalent filtered re-render).

## FR-CN4: Waiter (ordering grid)
- Already implemented: `#category-tabs` in `waiter.html`, `renderCategoryTabs()` / `getFilteredMenuItems()` in `waiter.js`.
- Same FR-CN1–CN2 behavior; grid re-renders filtered cards.

## Authorization
- Read endpoints unchanged — authenticated roles that already load menu data.

## Related
- `specs/feature-category-crud/` — category CRUD
- `specs/feature-menu-items/` — menu item list
- `specs/feature-counter-ui/` — Menu Management panel
