# Feature: Printer Test Print

## Purpose
Admins verify that a configured printer actually prints (USB Windows queue or LAN), beyond the LAN reachability **Check now** probe.

## Actors
| Role | Capability |
|------|------------|
| Admin / root | `POST /api/printers/{id}/test-print` from Printers table **Print Test** |
| Cashier / waiter | No access |

## FR-TP1: Endpoint
- `POST /api/printers/{printer_id}/test-print`
- Roles: `ADMIN_PANEL_ROLES` only
- 404 if printer id missing
- On dispatch failure: `502` with actionable `detail`
- On success: `PrinterTestPrintResponse` (`ok`, `printer_id`, `printer_name`, `role`, `backend`, `target`, `message`)

## FR-TP2: Payload
Short slip (text or image per global render mode):
- `TEST PRINT`
- Shop name (`SHOP_NAME`)
- Printer display name + role
- UTC timestamp

## FR-TP3: Targeting
- Uses **that** `Printer` row (not role default fallback)
- Cashier + `windows_printer` → that row’s `windows_printer_name`
- Otherwise when `host` set → LAN `host:port` for that row
- `file` backend → file output (still success for local/dev)

## FR-TP4: UI
- Menu Management → Printers table → each row **Print Test** next to Edit/Delete
- Confirm optional; show success/error dialog with `message` / `target`

## Non-goals
- Does not block orders
- Does not replace `/api/printers/health`
