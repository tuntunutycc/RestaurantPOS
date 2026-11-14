# Validation: Priced Modifiers

## Review checklist
- [x] Security: no new public endpoints; reuses menu/order auth
- [x] Roles: admin configures modifiers; waiter/cashier consume existing order contracts
- [x] Money: `price * quantity` included in line subtotal server-side
- [x] Edge: missing `quantity` treated as 1; qty < 1 rejected/normalized to ≥ 1
- [x] Edge: empty modifiers_config still orders as plain item
- [x] Kitchen Pattern A only (no aggregate B)
- [x] Instruction tags remain note-only

## Automated tests (`tests/test_priced_modifiers.py` — 13 passed)
- [x] `SelectedModifier.quantity` contract + pricing helper (`price × qty`)
- [x] quantity &lt; 1 normalized / schema rejects 0
- [x] Kitchen ticket Pattern A (+ toppings under parent; note retained)
- [x] Plain ticket without modifiers stays clean
- [x] Menu item create/update persists `modifiers_config`
- [x] Order submit subtotal includes modifier qty
- [x] Note-only (`နံနံပင်ရှောင်`) does **not** change price
- [x] Two bowls different toppings → cashier `/details` composition + total 5200
- [x] Kitchen dispatch payload includes `selected_modifiers`
- [x] Checkout file receipt prints modifier lines
- [x] Non-mohinga item can use same modifier pattern

## Manual (shop)
- [ ] Admin: add `အကြော်` group on မုန့်ဟင်းခါး with ပဲကြော် / အိုးဘဲဥ prices
- [ ] Waiter: one bowl + ပဲကြော်×2, one bowl + အိုးဘဲဥ×1 + note နံနံပင်ရှောင်
- [ ] Kitchen paper shows Pattern A composition
- [ ] Cashier total matches waiter cart; modifiers visible
