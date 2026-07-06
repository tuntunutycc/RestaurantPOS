# Implementation Reference: Walk-in Takeaway

## Backend
| Piece | Location |
|-------|----------|
| Nullable `table_id` | `models.Order`, `schemas.OrderCreate` |
| Submit / append | `routers/orders.py` `submit_order` — `order_id` for takeaway add-on |
| Staff attribution | `OrderItem.created_by_id = current_user.id` on every line |
| Kitchen ticket label | `services/printing/ticket.py` — `Takeaway #<order_id>` |
| Order details | `GET /api/orders/{order_id}/details` — `table_id` may be null |

### Append (`submit_order`)
When `order_type=takeaway` and `body.order_id` is set:
```python
order = db.query(Order).filter(
    Order.id == body.order_id,
    Order.order_type == "takeaway",
    Order.table_id.is_(None),
    Order.status.in_(OPEN_ORDER_STATUSES),
).first()
```

## Frontend
| Surface | File | Notes |
|---------|------|-------|
| Walk-in button | `waiter.html` `#btn-walk-in-takeaway` | Near table grid |
| Walk-in context | `waiter.js` `startWalkInTakeaway()` | `table_id: null`, `walk_in: true` |
| Append context | `waiter.js` `activateContextFromOrderDetails()` | **Add More Items** from order details sidebar |
| View active takeaway | `waiter.js` `openOrderDetails()` | Click takeaway card → same sidebar as occupied table |
| Submit append | `waiter.js` `bindSubmitOrder()` | sends `order_id` when `append_mode` |
| Cart default pricing | `waiter.js` `defaultCartLineTakeaway()` | true when walk-in / append / takeaway |
| Cashier list | `counter.js` | `🛍️ Takeaway #id` |
| Kitchen board | `table-dashboard.html/js` | Active takeaway cards |

## Tests
`tests/test_walk_in_takeaway.py`
