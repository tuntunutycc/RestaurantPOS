# Feature: Dynamic Printer Management

## Purpose
Admins manage an unlimited number of named LAN printers via CRUD. Fresh installs seed only two defaults (Cashier + Kitchen). Category tickets map `food`→`kitchen` and `drinks`→`bar` (fallback `kitchen`). No fixed multi-printer topology.

## Architecture (1A / 2A / 3A)
- **Single table `printers`:** `id`, `name`, `host`, `port`, `role` (`cashier`|`kitchen`|`bar`|`other`), `is_active`
- **Global print mode** remains `KitchenPrinterSettings` (backend / render_mode / paper_width_px) via `GET/PUT /api/admin/kitchen-printers` (no fixed host cards)
- **Category `printer_route`** stays `drinks`|`food` for menu categories; dispatch maps to printer roles
- **Cashier UI** `GET /api/printers?role=cashier` refreshes dropdown on page load

## Seed (minimal)
1. Default Cashier Printer — `role=cashier`
2. Default Kitchen Printer — `role=kitchen`
- Invoked from lifespan + `scripts/seed_root.py` (idempotent when any printer exists after migration)

## Admin API
| Method | Path | Roles |
|--------|------|-------|
| GET | `/api/printers` | Admin: all; Checkout: `?role=cashier` active |
| POST | `/api/printers` | Admin |
| PUT | `/api/printers/{id}` | Admin |
| DELETE | `/api/printers/{id}` | Admin |

## UI
Menu Management (counter): dynamic printer table + Add/Edit modal + Delete; keep print-mode controls.
