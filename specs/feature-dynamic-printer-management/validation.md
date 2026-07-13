# Validation: Dynamic Printer Management

## Automated
- [x] Seed creates cashier + kitchen defaults when empty
- [x] POST/PUT/DELETE `/api/printers` admin CRUD
- [x] GET `/api/printers?role=cashier` for checkout roles
- [x] drinks category → bar printer host when present, else kitchen
- [x] food category → kitchen printer
- [x] Full pytest green

## Manual
- [ ] Admin adds Cashier 2 → Cashier UI refresh shows it in dropdown
- [ ] Admin deletes unused printer
- [ ] Add bar printer + set drinks category → tickets hit bar IP
