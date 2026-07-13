# Validation: Split Payment

## Automated
- [x] Checkout 150: mobile 50 + cash 100 → 200, amounts stored, method `split`
- [x] Sum < total → 400
- [x] Excess cash → change correct
- [x] Legacy full cash / mobile still works
- [x] Analytics includes split amounts in both buckets
- [x] Full pytest green

## Manual
- [ ] Split auto-fill when editing one field
- [ ] Confirm disabled until sum ≥ total
- [ ] Receipt shows payment / change
