# Requirements: Category Edit & Delete (Menu Management)

## Purpose
Allow admin-panel users to rename and remove menu categories from Counter → Menu Management, with safe deletion rules that protect menu data integrity.

## Scope
- **In scope:** `PUT /api/categories/{id}` (name), `DELETE /api/categories/{id}`, Counter UI Edit/Delete controls.
- **Out of scope:** Bulk category operations, merging categories, reassigning items on delete.

## Functional requirements

### FR-1: Edit category name
- Admin/root may update a category name via `PUT /api/categories/{category_id}` with `{ "name": "..." }`.
- Name must be non-empty after trim (`400` if empty).
- `404` if category does not exist.

### FR-2: Delete category (strict rules — resolved)

**Active items block:** A category MUST NOT be deleted while any **active** (non–soft-deleted) menu item references it.

- Count query: `menu_items WHERE category_id = ? AND is_deleted = false` only.
- Soft-deleted menu items (`is_deleted = true`) **must NOT** count toward this block.
- If active count > 0 → **`400`** with:
  > Cannot delete category. Please delete all menu items under this category first.

**When only soft-deleted items remain** (user deleted all visible menu items via menu-item soft delete):

- Category delete **must succeed**.
- Soft-deleted rows with **no** order history → purged (hard-deleted) server-side.
- Soft-deleted rows **with** order history → moved to hidden system category `__system_archived__` (preserves `OrderItem` FK + snapshots).
- `GET /api/categories/` excludes `__system_archived__` from the admin list.

**Dependency:** Menu items use soft delete (`specs/feature-menu-items/`) — users soft-delete items first, then delete the empty category.

### FR-3: Counter UI
- Each category row shows **Edit** and **Delete** actions beside printer route controls.
- **Edit:** `prompt()` for new name → `PUT` → refresh list.
- **Delete:** `dialogConfirm` → `DELETE` → on `400` show API `detail` in `dialogAlert`; on success refresh list.

## Authorization
- `ADMIN_PANEL_ROLES` (`root`, `admin`) — same as category create and menu item CRUD.

## Non-functional
- API errors must surface exact server `detail` string to the user on delete failure (`window.alert` + `dialogAlert`).
- Category delete must interoperate with menu-item soft delete (see `specs/feature-menu-items/requirements.md` FR-1–FR-2).
