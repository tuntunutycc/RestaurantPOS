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
- [ ] Modal **Quantity** `+`/`-` (min 1) scales Add to Cart total; submitted cart line uses that qty
- [ ] Clicking chip appends with comma when text already present
- [ ] Admin can add/delete tags in Menu Management tab
- [ ] Submitted order line includes appended instruction text
