# Implementation Reference: Menu Category Navigation

## Backend (unchanged)
- `GET /api/categories/` — `CategoryResponse` list
- `GET /api/menu-items/` — `MenuItemResponse` with `category_id`

## Counter (`counter.html`, `counter.js`)
| Element / function | Role |
|--------------------|------|
| `#menu-category-tabs` | Pill container |
| `activeMenuCategoryId` | `null` = ALL |
| `categoriesCache` | From `fetchCategories()` |
| `renderMenuCategoryTabs()` | Build ALL + category pills |
| `filterMenu(categoryKey)` | Set filter + update list |
| `applyMenuCategoryFilter()` | Toggle `hidden` on `[data-menu-category-id]` rows |

## Waiter (`waiter.html`, `waiter.js`)
| Element / function | Role |
|--------------------|------|
| `#category-tabs` | Sticky pill bar |
| `activeCategoryId` | `null` = ALL |
| `renderCategoryTabs()` / `getFilteredMenuItems()` / `renderMenu()` | Existing filter + grid |

## Tests
- `tests/test_category_crud.py` — categories list
- `tests/test_menu_category_navigation.py` — menu items expose `category_id`
