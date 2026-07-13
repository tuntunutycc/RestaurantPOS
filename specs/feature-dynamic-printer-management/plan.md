# Plan: Dynamic Printer Management

1. Specs + contracts (`Printer` CRUD, role mapping, seed 2)
2. Model unify `CashierPrinter` → `Printer`; migrate legacy rows
3. Seed + routing: food→kitchen, drinks→bar→kitchen fallback
4. Admin CRUD API `/api/printers`; simplify kitchen-printers to mode-only
5. Replace fixed host cards in `counter.html` with table/modal
6. Pytest: CRUD + routing + full suite green
