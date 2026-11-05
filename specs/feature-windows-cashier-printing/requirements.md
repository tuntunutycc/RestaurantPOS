# Requirements: Windows Cashier Receipt Printing

## Purpose
On Windows 11 deployment PCs, print checkout receipts to a **USB / Bluetooth Windows printer queue** (e.g. `POSPrinter POS-80(300DPI)`) selected in Admin UI — without requiring a LAN IP.

## Scope (v1)
- **In:** cashier receipts only (`dispatch_cashier_receipt`)
- **In:** Admin list of installed Windows printers + store queue name on `Printer`
- **Out:** kitchen / drinks tickets over Windows USB
- **Keep:** `file` and `escpos_network` backends

## Actors
| Role | Capability |
|------|------------|
| Admin / root | Set global backend `windows_printer`; pick Windows queue on cashier `Printer` rows |
| Cashier | Terminal dropdown still selects cashier `Printer` by id; checkout prints if `issue_receipt` |
| System | After paid commit, RAW ESC/POS to Windows spooler; soft-fail on print error |

## FR-W1: Backend mode
- `KitchenPrinterSettings.backend` accepts `file` | `escpos_network` | **`windows_printer`**
- When `windows_printer` + route `cashier` → Windows RAW send
- When `windows_printer` + kitchen/drinks routes → **LAN if host configured**, else **file fallback** + warning log

## FR-W2: Printer queue name
- `Printer.windows_printer_name` (nullable VARCHAR 256)
- Cashier printers used under `windows_printer` must have a non-empty queue name
- Resolve: `printer_id` → that row; else first active `role=cashier` with a queue name (else first active cashier)

## FR-W3: Admin Windows printer list
- `GET /api/admin/windows-printers` (admin/root)
- Response: `{ available, printers: [{ name }], message }`
- On non-Windows / missing `pywin32`: `available=false`, empty list, explanatory message

## FR-W4: Soft-fail
- Checkout stays `200` if Windows print fails; `warning` like existing LAN path

## Non-goals
- Docker Linux USB access
- Kitchen Windows printing in v1
