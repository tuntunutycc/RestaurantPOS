# Plan: Dual Pricing (Dine-in vs Takeaway)

## Phase 1 — SDD
- `requirements.md`, `implementation.md`, `validation.md`

## Phase 2 — Backend
- `models.py` — `MenuItem.takeaway_price`, `OrderItem.is_takeaway`
- `main.py` — SQLite column migrations
- `schemas.py` — menu + order line contracts
- `routers/orders.py` — `_resolve_unit_base_price()`, all OrderItem inserts
- `routers/menu.py` — pass-through on create

## Phase 3 — Frontend
- `static/counter.html`, `static/counter.js` — takeaway price field
- `static/waiter.js` — per-line takeaway checkbox + live price

## Phase 4 — Tests
- `tests/test_menu_dual_pricing.py`
