# Requirements: Role-Based Access Control (RBAC) & Authorization

## 1. Purpose
Define a five-role authorization model for the Myanmar restaurant POS. The system must enforce permissions **server-side**, support **single-device sessions** for floor staff, provide **hierarchical user management**, **audit visibility for root**, and **role-scoped sales dashboards** including future waiter incentive reporting on promoted items.

> **Stack context:** Current product is **FastAPI + static JavaScript** (not Next.js). This contract governs API + UI behavior regardless of future frontend migration.

## 2. Roles

| Role | Auth method | Multi-device | Primary surface |
|------|-------------|--------------|-----------------|
| `root` | username + password | **yes** | Setup, admin accounts, audit logs, full reports, admin panel |
| `admin` | username + password | **yes** | Staff CRUD (non-admin), POS admin panel, operational reports |
| `account` | PIN | **no** | Read-only financial reports (≤ 3 months) via `/account` |
| `cashier` | PIN | **no** | Counter checkout + waiter ordering fallback |
| `waiter` | PIN | **no** | Tablet ordering only |

**Auth rule (strict):** Only `root` and `admin` may use username + password. `cashier`, `waiter`, and `account` **must** authenticate via `POST /api/auth/login-pin` only. Password self-service (`POST /api/auth/change-password`) is **forbidden** for PIN roles, including `account`.

**Removed:** legacy `kitchen` login role. Kitchen printing remains automatic on order submit (see `specs/feature-kitchen-printing/`).

## 2.1 Strict creation hierarchy

Operational chain (highest → lowest):

```
ROOT  →  creates ADMIN
ADMIN →  creates CASHIER, WAITER (and ACCOUNT for finance)
```

| Actor | May create | API | Blocked roles |
|-------|------------|-----|---------------|
| **Nobody via admin UI** | `root` | — | First root is **not** created through Counter/Staff UI |
| **CLI / operator** | `root` (first only) | `scripts/seed_root.py` | See §9 bootstrap |
| **Root** | `admin` | `POST /api/root/admins` | Cannot create `root` (hardcoded `role=admin`) |
| **Admin** | `cashier`, `waiter`, `account` | `POST /api/admin/users` | `admin`, `root` → `403` / `422` |
| **Root** (staff) | `cashier`, `waiter`, `account` | `POST /api/admin/users` | `admin` via staff API → `400` (`AdminStaffRole` schema); use `/api/root/admins` for admins |

**Schema enforcement:** `UserCreateRequest.role` is `StaffRole`; privileged roles (`admin`, `root`) on `POST /api/admin/users` are rejected at the handler with **`403 Forbidden`** via `_reject_privileged_roles_via_staff_api`.

**Handler enforcement:** `routers/users.py` returns `403` if `actor.role == admin` and target role ∉ `ADMIN_MANAGEABLE_ROLES`.

`cashier` and `waiter` cannot create users. `account` is read-only.

## 3. Role Privileges

### 3.1 Root
**User management**
- **First bootstrap:** operator runs `scripts/seed_root.py` on the server (see §9). Not created via Counter staff UI.
- Change own password.
- Create, edit, soft-delete `admin` accounts.
- Reset `admin` passwords.
- View system audit logs (which admin created/edited/deleted which user, with before/after snapshots).

**Dashboard & reports**
- Store **daily total sales** (today + historical daily trend).
- **Daily and monthly sales filtered by cashier** (`Order.checked_out_by_id` attribution).
- **Daily and monthly sales filtered by waiter** (order-line attribution via `OrderItem.created_by_id`).
- Full access to existing store reports (top items, cancellations, etc.) without date cap.

**Admin panel (resolved: superset)**
- Inherits full `ADMIN_PANEL_ROLES` — same POS configuration access as `admin`: menu, tables, zones, kitchen printers, and staff CRUD via `/api/admin/users`.
- Admin-account governance remains on `/api/root/admins` only.

### 3.2 Admin
**User management**
- Multiple `admin` users may exist.
- **Must not** create, edit, or delete another `admin` or `root` (server returns `403`).
- Create, edit, soft-delete `cashier`, `waiter`, and `account` staff.
- Change own password; `root` may reset admin password.

**Dashboard & reports**
- Store daily total sales.
- **Daily sales by waiter** (all waiters; order-line attribution).
- Per-cashier breakdown (full store view).
- No account-style 3-month cap.

**Admin panel**
- Menu, categories, modifiers, tables/zones, kitchen printer settings, staff management UI.

### 3.3 Account
**Access**
- **View-only.** No order submit, checkout, menu/table mutations, or staff CRUD.

**Dashboard & reports**
- Daily sales summaries.
- Monthly sales summaries.
- Historical queries capped at **90 days** (3 calendar months) per request and as oldest viewable date.
- May view store-level and per-cashier breakdowns within the cap.
- **Must not** view per-waiter staff breakdown (incentive data restricted to operational roles).

**Dedicated SDD:** `specs/feature-account-reports/` — FR-A1–FR-A5 (role definition, permitted reports, 90-day cap, provisioning, `/account` UI).

### 3.4 Cashier
**User management:** None (created by admin/root).

**POS capabilities (see `specs/feature-cashier-reports/requirements.md` FR-C1)**
- Counter screen: checkout, billing, discounts, payment methods.
- **Includes waiter capabilities:** may use `/waiter` to take orders when counter service or waiter tablet fallback is needed.
- Order lines submitted while logged in as cashier attribute to cashier via `OrderItem.created_by_id`.
- Checkouts attribute to cashier via `Order.checked_out_by_id`.

**Dashboard & reports (see `specs/feature-cashier-reports/requirements.md` FR-C2)**
- **Own daily total sales** (checkout-attributed revenue only) via `GET /api/reports/summary/today`.
- **Must not** access Staff Performance (`by-cashier`, `by-order-staff`) or view other staff breakdowns.
- **No monthly self-view** — cashier is excluded from `GET /api/reports/monthly-sales` and counter UI must not show a monthly sales widget.

**Menu availability (resolved — see `specs/feature-menu-rbac/`)**
- Cashier may open Counter → **Menu Management** in **availability-only** mode.
- Cashier may `PATCH /api/menu-items/{id}/availability` with `{ "is_available": boolean }` only.
- Cashier **must not** create, edit (price/details), delete menu items, or mutate categories/printers/instruction tags.

**Restrictions**
- No other admin panel mutations (tables, staff, categories, full menu CRUD).
- No checkout when acting only as order-taker is not a restriction — cashier retains checkout rights on counter screen.

### 3.5 Waiter
**POS capabilities**
- `/waiter` screen: dine-in and takeaway ordering, item status updates permitted by existing order APIs.
- **No checkout.**

**Dashboard & reports**
- **Own daily order-line sales** only (self-scoped `by-order-staff`).

## 4. Waiter Tracking & Promoted Items

### 4.1 Waiter performance (this phase)
- Attribute order revenue to waiters using existing `OrderItem.created_by_id` at submit time.
- Expose **daily** and **monthly** per-waiter aggregates via reporting APIs.
- Cashier-submitted orders count toward cashier in waiter reports when `created_by_id` is the cashier user (not double-counted as waiter).

### 4.2 Promoted items (Phase 4b — complete)
- Menu items markable as `is_promoted` (admin panel toggle + form checkbox).
- `GET /api/reports/sales/promoted-by-waiter` — daily/monthly per-staff promoted qty/revenue.
- Waiter Incentives dashboard (root/admin). Waiter API scoped to self.
- Waiter/cashier menu shows **★ Promo** badge on promoted items.

**Dedicated SDD folders (2026-07-05):**
- `specs/feature-account-reports/` — FR-A1–FR-A5 (accountant role, 90-day report cap, `/account` UI)
- `specs/feature-cashier-reports/` — FR-C1–FR-C2 (ordering inheritance, cashier daily sales); FR-C3 Staff Performance root/admin only
- `specs/feature-waiter-incentives/` — FR-P1–FR-P3 (promoted flag + incentive report)

## 5. Session & Device Management

### FR-S1: Device identifier
- Client generates persistent `device_id` (UUID in `localStorage`) and sends on every login.

### FR-S2: JWT session binding
- Each login issues JWT containing `jti` mapped to a `user_sessions` row.
- `get_current_user` rejects tokens whose `jti` is missing, unknown, or revoked.

### FR-S3: Single-device roles (`account`, `cashier`, `waiter`)
- New login **revokes** all prior active sessions for that user.
- Revoked device receives `401` on next API call and must re-login.

### FR-S4: Multi-device roles (`root`, `admin`)
- Parallel sessions on multiple devices are allowed.
- Logout (if implemented) revokes only the current session's `jti`.

### FR-S5: Session metadata
- Store `device_id`, `created_at`, `revoked_at` per session for audit/debug (root may view via future session admin UI — optional).

## 6. User Management APIs

### FR-U1: Root admin API (`/api/root/admins`)
| Action | Rule |
|--------|------|
| List/create/update/delete | `admin` role targets only |
| Reset password | `admin` targets only |
| Audit | All mutations logged |

### FR-U2: Admin staff API (`/api/admin/users`)
| Action | Rule |
|--------|------|
| List/create/update/delete | `cashier`, `waiter`, `account` only |
| Create/edit `admin` or `root` | `403 Forbidden` |
| Soft delete | Preserve historical orders; `ON DELETE SET NULL` on attribution FKs |

### FR-U3: Password change
- `POST /api/auth/change-password` for **`root` and `admin` only** → `403` for `account`, `cashier`, and `waiter`.
- PIN roles (`account`, `cashier`, `waiter`) change PIN via staff update endpoints (admin/root only); no self-service password change UI or API.

## 7. Audit Logs

### FR-A1: Events to log (minimum)
- Admin creates/updates/deletes staff (`cashier`, `waiter`, `account`).
- Root creates/updates/deletes/resets-password for `admin`.

### FR-A2: Log fields
- `actor_user_id`, `action` (stable string), `target_user_id` (nullable), `detail_json` (before/after snapshot), `created_at`.
- **PIN policy (resolved):** `detail_json` never stores plaintext PINs. When a user has a PIN, snapshots show `"pin_code": "[REDACTED]"`. Staff create sets `"pin_set": true` when a PIN was assigned; staff update sets `"pin_changed": true` when the PIN value changed.

### FR-A3: Access
- `GET /api/root/audit-logs` — **root only**.
- Root UI must provide a readable audit log viewer (paginated, filterable by action/date).

## 8. Reporting Contract (role matrix)

| Report / capability | root | admin | account | cashier | waiter |
|---------------------|------|-------|---------|---------|--------|
| Store daily total | yes | yes | yes (≤90d) | own checkout daily | no |
| Store monthly trend | yes | yes | yes (≤90d) | no | no |
| Sales by cashier (daily/monthly) | all | all | all (≤90d) | **no** | no |
| Sales by waiter / order staff (daily/monthly) | all | all | no | **no** | self only |
| Promoted items by waiter | all | all | no | no | self only (future) |
| Top items / cancellations | yes | yes | yes (≤90d) | no | no |

### FR-D1: Counter Staff Performance UI (Dashboard → Staff Performance)
- **Date range:** `From` / `To` inputs (`staff-filter-start-date`, `staff-filter-end-date`).
- **Presets:** **Today** (single day) and **This Month** (1st of month through today).
- **Default on first load:** current calendar month to date (month start → today).
- **Charts:** Sales by Cashier (`GET /api/reports/sales/by-cashier`) and Sales by Waiter (`GET /api/reports/sales/by-order-staff`) both use the same `start_date` / `end_date` query params.
- **Roles:** root and admin only — Staff Performance tab and both charts; cashier sees overview (own today total) only.
- **Validation:** client rejects `start_date > end_date` before fetch.

**Money rule:** Report totals must use the same rounding and tax-after-discount rules as checkout (backend source of truth).

## 9. Bootstrap & Migration

### FR-M1: Fresh install (first root)
- No default admin seed on application boot.
- **Canonical production path:** operator creates the first `root` via CLI:
  ```bash
  PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'
  ```
  Script is idempotent: if a non-deleted `root` already exists, it exits without changes.
- **Dev / test fallback:** `POST /api/setup/root` and `/setup` UI remain for automated tests and local dev when no root exists. **Do not rely on the public setup UI in production** — it is unauthenticated while `needs_setup` is true.
- After root exists, `/login` no longer redirects to `/setup` (`GET /api/setup/status` → `needs_setup: false`).

### FR-M2: Existing deployments
- If no `root` and legacy `username=admin` exists, promote to `role=root` on startup (one-time).
- Block login for users with `role=kitchen`.

## 10. Non-Functional Requirements

- **Server enforcement:** UI role guards are convenience only; every mutation and report endpoint validates role.
- **Data integrity:** User soft-delete must not break historical reports; use fallback labels for deleted users.
- **Security:** Password hashes never returned in API responses. Admin staff CRUD (`UserAdminResponse`) returns plaintext `pin_code` for operational PIN management; audit `detail_json` must not leak credentials in plain text (mask PIN snapshots as `[REDACTED]`).
- **Test gate:** Automated tests for role matrix, session revoke, account date cap, checkout/waiter attribution.

## 11. Explicit Out of Scope (follow-on / future)
- PostgreSQL migration / Alembic (SQLite runtime ALTER acceptable for dev).
- Next.js frontend rewrite.
- Per-user session admin UI for root (optional future).

**Delivered in Phase 4b (2026-07-04):** promoted-item menu flag and waiter incentive reports — see `validation.md` Phase 4b checklist.

## 12. Resolved Decisions (2026-07-04)

| # | Topic | Decision |
|---|-------|----------|
| 1 | Root admin-panel superset | **Yes** — `root` has full `ADMIN_PANEL_ROLES` plus `/api/root/admins` governance |
| 2 | Cashier monthly view | **No** — daily own-checkout total only; no monthly dashboard for cashier |
| 3 | Audit log PIN snapshots | **Redacted** — `"[REDACTED]"` in snapshots; `pin_set` / `pin_changed` flags in `detail_json` |
| 4 | Staff monthly per-cashier UI | **Yes** — Counter Staff Performance (root/admin only) uses date range + **This Month** preset (FR-D1) |
