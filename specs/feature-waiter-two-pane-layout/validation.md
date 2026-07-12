# Validation: Waiter Two-Pane Layout

```bash
PYTHONPATH=. pytest -q
```

## Manual
- [ ] Desktop: left Menu+Cart (green tint), right Tables/Takeaways (rose tint)
- [ ] Available table → selects cart context; no modal
- [ ] Occupied table → centered modal with items, breakdown, Cancel Item
- [ ] Active takeaway card → same modal
- [ ] Close (✖) and backdrop dismiss modal; cart unchanged
- [ ] Cancel Item in modal still calls `PUT /api/orders/{id}/items/{item_id}/status`
- [ ] Add More Items closes modal and enables append cart context

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-12 | Full `pytest -q` | **181 passed** |
