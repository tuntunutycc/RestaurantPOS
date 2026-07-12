# Validation: Cashier Network Receipt Printing

## Automated
- [ ] Checkout with `issue_receipt=true` + file backend writes cashier output / succeeds
- [ ] Checkout with mocked printer `ConnectionError` → **200**, `warning` set, order `paid`
- [ ] Checkout with `issue_receipt=false` → **200**, no print dispatch, `warning` null
- [ ] Admin kitchen-printers GET includes `cashier` route; PUT with three routes OK
- [ ] Full `pytest` green

## Manual
- [ ] Image mode + Myanmar item names render on thermal / PNG preview
- [ ] Uncheck Print Receipt → payment OK, no paper
- [ ] Unplug printer → checkout success + toast warning
- [ ] Admin can set Cashier printer IP independently of drinks/food
