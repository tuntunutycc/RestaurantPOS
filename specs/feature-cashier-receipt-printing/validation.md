# Validation: Cashier Network Receipt Printing + Terminal Selection

## Automated
- [x] Checkout with `issue_receipt=true` + file backend writes cashier output / succeeds
- [x] Checkout with mocked printer `ConnectionError` → **200**, `warning` set, order `paid`
- [x] Checkout with `issue_receipt=false` → **200**, no print dispatch, `warning` null
- [x] Checkout with `printer_id` targets that cashier printer (network mock / host override)
- [x] Checkout without `printer_id` falls back to first active cashier printer / legacy route
- [x] `GET /api/printers?role=cashier` returns active cashier printers
- [x] Admin kitchen-printers GET includes `cashier` route; PUT with three routes OK
- [x] Full `pytest` green

## Manual
- [ ] Image mode + Myanmar item names render on thermal / PNG preview
- [ ] Uncheck Print Receipt → payment OK, no paper
- [ ] Two cashier browsers select different printers; each prints to its own IP
- [ ] Reload page → dropdown restores `localStorage.selectedCashierPrinterId`
- [ ] Unplug printer → checkout success + toast warning
- [ ] Admin can manage multiple cashier printers independently of drinks/food
