# Plan: Menu Item Soft Delete

## Phase 1 — Backend (complete)
| Step | Detail |
|------|--------|
| Schema | Use existing `is_deleted`, `deleted_at` on `MenuItem` |
| DELETE handler | Soft delete only (`routers/menu.py`) |
| Active order check | `_menu_item_in_active_order()` before delete |
| List API | Filter `is_deleted=false` on `GET /api/menu-items/` |

## Phase 2 — Frontend (complete)
| Step | Detail |
|------|--------|
| Waiter / counter lists | Use `GET /api/menu-items/` (server-filtered) |
| Counter delete | `deleteMenuItem()` + `window.alert` on `400` |
| WebSocket | Broadcast `menu_item_deleted` on success |

## Phase 3 — Tests & validation
| Step | Detail |
|------|--------|
| Tests | `tests/test_menu_item_soft_delete.py` |
| Regression | `tests/test_deletion_integrity.py` (history preserved) |
| Docs | `validation.md`, `implementation.md`, `CHANGELOG.md` |
