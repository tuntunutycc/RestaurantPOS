# Validation: Cashier Name on Checkout & Receipt

## Automated
- [x] Checkout with `cashier_name` persists on Order
- [x] Receipt text includes `Cashier: …` when set; omits when blank
- [x] Full pytest green

## Manual
- [ ] Set name in Cashier pane, refresh — name restored from localStorage
- [ ] Checkout prints Cashier line on receipt file/printer
