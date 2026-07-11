# Validation: Predefined Instruction Tags

## Automated (pytest)

| Scenario | File |
|----------|------|
| GET list (waiter) | `tests/test_predefined_instructions.py` |
| POST create (admin) | same |
| DELETE (admin) | same |
| Waiter cannot POST/DELETE | same |
| Default seed on empty DB | same |

Run: `PYTHONPATH=. python -m pytest -q tests/test_predefined_instructions.py`

## Manual checklist

- [ ] Waiter modal shows chips above special-instructions textarea
- [ ] Clicking chip appends with comma when text already present
- [ ] Admin can add/delete tags in Menu Management tab
- [ ] Submitted order line includes appended instruction text
