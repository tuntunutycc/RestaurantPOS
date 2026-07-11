# Implementation Reference: Predefined Instruction Tags

## Backend
- `models.PredefinedInstruction`
- `services/predefined_instructions.seed_predefined_instructions()`
- `routers/predefined_instructions.py` — CRUD under `/api/predefined-instructions`
- Seed invoked from app lifespan and on list GET

## Frontend
| File | Change |
|------|--------|
| `waiter.html` | `#predefined-instruction-chips` container above textarea |
| `waiter.js` | fetch, render chips, `appendInstructionTag()` |
| `counter.html` | Quick Instruction Tags admin section |
| `counter.js` | list, add, delete wiring |

## Tests
- `tests/test_predefined_instructions.py`
