# Plan: Cashier Network Receipt Printing + Terminal Printer Selection

## Approach
1. Specs + contract (`issue_receipt`, `printer_id`, `OrderCheckoutResponse.warning`, multi-cashier printers)
2. `cashier_printers` table (named LAN endpoints) + seed from legacy `cashier` route / env
3. Receipt text builder + `dispatch_cashier_receipt` with optional host override; kitchen routes untouched
4. Checkout: commit first, then print to selected/`printer_id` or first active cashier printer; never roll back payment
5. Counter UI: printer `<select>` + `localStorage`; Print Receipt checkbox; toast on `warning`
6. Pytest: optional `printer_id`, list printers API, mock TCP; full suite green
