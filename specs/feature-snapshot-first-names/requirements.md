# Feature: Snapshot-first item names (Step 1 of 2)

> Status: **Implemented 2026-11-19.** Step 2 is `specs/feature-linked-addons/` and starts only after every test of this step passes.

## Purpose
Renaming a menu item must never change what an **already sold** order line says. Prices already behave this way (see `specs/feature-menu-price-safety/`). Names do not: several screens show the **live** menu name instead of the name stored when the line was sold.

## Audit result (2026-11-19, read from the code, not yet reproduced by a test)

| Place | Reads | Verdict |
|-------|-------|---------|
| `routers/orders.py` `_display_menu_item_name` -> `GET /orders/{id}/details`, `_daily_history_line` (Order History modal) | **live** `MenuItem.name` first, snapshot only if the item is deleted | **Wrong** |
| `schemas.py` `OrderResponseDetail.build_from_order` -> order list, active-by-table, create / submit / checkout responses | **live** name first | **Wrong** |
| `routers/reports.py` `_historical_item_name_expr`, `_historical_category_name_expr` | snapshot first | OK |
| `services/order_history.py` `line_item_detail_text` (Excel export / history text) | snapshot first | OK |
| Receipt (`checkout_order` payload, `PrintJob.payload`) and kitchen slip payload | snapshot written at sale time | OK |
| `OrderItem.menu_item_name_at_sale` / `category_name_at_sale` written for new lines | `create_order` (both branches) and `submit_order` | OK, unchanged |
| Legacy rows created before the snapshot columns existed | columns are `NULL`; no backfill in `main.py` | **Gap** |

Money is not affected: totals, subtotals and reports already use stored values.

## FR-N1: Display name of an order line (all API responses)
The name shown for an `OrderItem` is, in this order:
1. `menu_item_name_at_sale`, if it is not empty after trimming spaces;
2. otherwise the live `MenuItem.name`, if the menu item exists and is not soft-deleted (legacy rows only);
3. otherwise the label `[Deleted Item]`.

It applies to every place in the table above marked **Wrong**, through one shared helper so the two code paths cannot drift apart again.

Consequence (accepted by the owner): on an **open** bill, lines already ordered keep the old name after a rename, and lines ordered afterwards carry the new name - the same way an open bill already keeps old prices.

## FR-N2: Startup backfill of legacy snapshots
On application start (`main.py` lifespan, next to the other additive migrations):
- `order_items.menu_item_name_at_sale` that is `NULL` or blank <- the live `menu_items.name` of its `menu_item_id`.
- `order_items.category_name_at_sale` that is `NULL` or blank <- the live category name, **except** the system bucket `__system_archived__` (left `NULL`).
- Never overwrites a non-empty value. Idempotent: a second start changes nothing. A row whose menu item no longer exists is left alone.
- `unit_price_at_sale` is **not** backfilled: the price at the time of an old sale is unknown. Breakdown keeps falling back to the stored `subtotal`.
- Limit to state in the spec: a legacy row's name is frozen at the moment of the first start after upgrading. Renames done before that cannot be recovered.
- A backfill failure must not stop the server from starting (same try/except pattern as the neighbouring migrations).

## FR-N3: Write path unchanged
New lines still store `menu_item_name_at_sale` and `category_name_at_sale` at order time in all three places (`create_order` new-order branch, `create_order` add-to-existing branch, `submit_order`). No API shape, request body or column changes.

## Not in this step
- The "promoted sales" report filters on the **live** `MenuItem.is_promoted` flag (audit gap 8). Left as is; it is a reporting-semantics question, not a name leak.
- Reports and Order History still cut the day at UTC (known limit).
- Anything about add-ons: Step 2.

## Contract impact
- API shapes: none. Only the **value** of `menu_item_name` changes after a rename.
- Database: no schema change, one idempotent data backfill.
- Docs touched at implementation time: `specs/api-reference.md` (note under item snapshots), `specs/database-schema.md` (backfill note), `CHANGELOG.md`.
