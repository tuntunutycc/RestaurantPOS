# Validation: Cashier 3-Pane Billing Layout

```bash
PYTHONPATH=. pytest -q
```

## Manual
- [ ] `lg+` screens: three columns Tables | Takeaways | Check Out
- [ ] Each pane scrolls independently
- [ ] Occupied table loads checkout in right pane
- [ ] Takeaway click replaces right-pane order
- [ ] Available table still shows empty alert
- [ ] Confirm Payment clears selection and refreshes grids
- [ ] Cash / Mobile Money + Served by still work

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-12 | Full `pytest -q` | **181 passed** |
