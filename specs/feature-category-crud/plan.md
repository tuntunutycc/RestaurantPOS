# Plan: Category Edit & Delete

## Phase 1 — Contract & backend
| Step | Detail |
|------|--------|
| Spec | `requirements.md` deletion rule (active items block) |
| API | Reuse `PUT /api/categories/{id}` for name; add `DELETE /api/categories/{id}` |
| Guard | Count **active only** (`is_deleted=false`); ignore soft-deleted items in block query |
| FK cleanup | Purge soft-deleted rows without order history; reassign others to `__system_archived__` |
| Tests | `tests/test_category_crud.py` |

## Phase 2 — Frontend
| Step | Detail |
|------|--------|
| UI | `renderCategories` in `counter.js` — Edit / Delete buttons |
| Edit | `prompt` + `PUT { name }` |
| Delete | `dialogConfirm` + `DELETE`; show `detail` on `400` |

## Phase 3 — SDD close-out
- `implementation.md`, `CHANGELOG.md`, run `pytest -q`
