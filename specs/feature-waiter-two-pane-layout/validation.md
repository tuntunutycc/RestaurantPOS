# Validation: Waiter Two-Pane Layout

```bash
PYTHONPATH=. pytest -q
```

## Manual
- [ ] Desktop: left Menu+Cart (**rose/red** tint), right Tables/Takeaways (**green/emerald** tint)
- [ ] Available table → selects cart context; no modal
- [ ] Occupied table on green pane → fixed pop-out modal with items, breakdown, Cancel Item
- [ ] Active takeaway card → same modal
- [ ] ✖ Close (header + footer) and backdrop dismiss modal; **cart qty / unsubmitted lines unchanged**
- [ ] Cancel Item in modal still calls `PUT /api/orders/{id}/items/{item_id}/status`
- [ ] Add More Items closes modal and enables append cart context
- [ ] Cart `+`/`-` (`increaseCartItemQty` / `decreaseCartItemQty`) still work after opening/closing modal

## Evidence

| Date | Suite | Result |
|------|-------|--------|
| 2026-07-13 | Full `pytest -q` + `node --check static/waiter.js` | **184 passed** |
| 2026-07-12 | Full `pytest -q` | **181 passed** |
