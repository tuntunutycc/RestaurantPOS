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
- No usable target on that row → **502** with a clear message, never another printer:
  - `escpos_network` and no `host`
  - `windows_printer` and a non-cashier row with no `host` (kitchen/bar/other have no Windows queue)
  - `windows_printer` and a cashier row with no `windows_printer_name`

## FR-TP4: UI
- Menu Management → Printers table → each row **Print Test** next to Edit/Delete
- Confirm optional; show success/error dialog with `message` / `target`
- Failures show actionable `detail` (+ hint to `logs/printing/print.log`)

## FR-TP5: Per-printer Check (online)
- `GET /api/printers/{id}/health` (admin/root) — no print job
- Cashier + `windows_printer` → open Windows queue / spooler status
  - Offline when `Status` has error/offline/not-available/paper-out/paper-jam/door-open **or** `Attributes` has work-offline (`0x400`; unplugged USB printers keep `Status=0`)
  - Message includes the port (`pPortName`) and the number of waiting jobs (`cJobs`) so a stuck queue is visible
  - "online" means the spooler would accept a job; it cannot prove paper came out
- Else if host set → TCP probe
- `file` backend → `skipped` with explanatory message
- Printers table **Check** button; Admin **Check now** also lists `named_printers`
- `named_printers` (aggregate) covers **active** printers only; an inactive row can still be probed by id

## Non-goals
- Does not block orders
- Kitchen route probe `/api/printers/health` remains for waiter badge
