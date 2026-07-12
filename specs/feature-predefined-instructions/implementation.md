# Implementation Reference: Predefined Instruction Tags

## Backend
- `models.PredefinedInstruction`
- `services/predefined_instructions.seed_predefined_instructions()`
- `routers/predefined_instructions.py` — CRUD under `/api/predefined-instructions`
- Seed invoked from app lifespan and on list GET

## Frontend
| File | Change |
|------|--------|
| `waiter.html` | `#predefined-instruction-chips` container above textarea; `#modifier-modal-qty-*` quantity row (FR-Q3b) |
| `waiter.js` | fetch, render chips, `appendInstructionTag()`; `modifierModalQty` + `addToCart(..., quantity)` |
| `counter.html` | Quick Instruction Tags admin section |
| `counter.js` | list, add, delete wiring |

## Tests
- `tests/test_predefined_instructions.py`
