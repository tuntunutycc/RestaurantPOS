# Implementation: Priced Modifiers

## Backend
- `schemas.SelectedModifier.quantity` (default 1, ge=1)
- `routers/orders.py` — normalize modifiers; total = `sum(price * quantity)`; kitchen print jobs include `selected_modifiers`; receipt items include modifiers
- `services/printing/ticket.py` — Pattern A lines `+ name` / `+ name xN`
- `services/printing/receipt.py` — modifier lines under each item

## Frontend
- `static/counter.html` + `counter.js` — modifiers editor; payload no longer forces `[]`; checkout shows modifiers
- `static/waiter.js` — optional group qty steppers; cart key/totals include quantity

## Tests
- `tests/test_priced_modifiers.py`
