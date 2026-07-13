# Feature: Cashier Name on Checkout & Receipt

## Purpose
Store a display **cashier name** at checkout (independent of login username) for physical receipt accountability.

## Data
| Field | Location | Rules |
|-------|----------|-------|
| `Order.cashier_name` | DB column `VARCHAR(128)`, nullable | Set at checkout from request body |
| `OrderCheckoutRequest.cashier_name` | optional `str \| null` | Trimmed; blank → stored as `null` |
| `OrderResponseDetail.cashier_name` | response | Echo of stored value |

**Note:** `checked_out_by_id` remains the authenticated user FK for reports. `cashier_name` is a free-text label for the receipt / terminal (e.g. shared PIN accounts).

## Checkout
`PUT` / `POST` `/api/orders/{id}/checkout` persists `cashier_name` when provided.

## Receipt
Print `Cashier: {name}` near the header (after Location / Served by, before or after Time).
If `cashier_name` is null/blank → **omit the line** (do not invent "Admin").

## Frontend (Cashier pane)
- Input near printer select: **Cashier Name**
- Persist in `localStorage` key `currentCashierName`
- Include `cashier_name` in checkout payload from that value
