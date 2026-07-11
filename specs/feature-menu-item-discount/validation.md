# Validation: Per-Item Menu Discount

## Automated (pytest)

| Test | File |
|------|------|
| 10% discount + 5% tax on discounted base | `tests/test_menu_item_discount.py::test_item_10pct_discount_5pct_tax_tax_on_discounted_price` |
| Grand total = Subtotal − Discount + Tax | same + `test_fixed_discount_and_percentage_tax` |
| Legacy `discount_price` migration | `test_legacy_discount_price_migrated_to_fixed_discount` |
| Waiter breakdown includes discount total | `tests/test_waiter_cart_breakdown.py` |

Run: `PYTHONPATH=. python -m pytest -q tests/test_menu_item_discount.py tests/test_waiter_cart_breakdown.py`

## Manual checklist

- [ ] Waiter cart: item with discount shows `Base | Disc | Tax` row
- [ ] Cart footer shows Total Discount when any line has discount
- [ ] Order details sidebar matches server `breakdown_*` fields
- [ ] Admin: legacy discount price still creates correct submit totals

## Known gaps (documented, not blocking baseline)

- Counter admin UI lacks `discount_type`/`discount_value` controls (API-only for new model)
