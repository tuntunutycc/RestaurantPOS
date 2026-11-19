# Feature: Safe menu price changes

## Purpose
The owner will raise (or lower) selling prices from time to time, so the same dish costs one amount this month and another next month. A price change must **never produce a system error** and must **never change money that was already recorded**.

## How price changes already behave (checked 2026-11-19, kept as is)
- Every order line stores a **snapshot** when it is sold: `unit_price_at_sale`, `unit_discount_at_sale`, `unit_tax_at_sale`, the line `subtotal`, `menu_item_name_at_sale`, `category_name_at_sale`.
- Totals, checkout, cancellation, receipts, Order History and every report use the stored line `subtotal`s, never the live menu price.
- Therefore:
  - A bill that is **already open** keeps the price each line was sold at. Items added later (a new batch) are sold at the **new** price. One bill can show the same dish at two prices; each line is correct for when it was ordered.
  - **Paid** orders and past reports never change.
  - Soft-deleting a menu item keeps its history.
- Waiter screens receive the new price through the `menu_item_updated` WebSocket event; the server always prices a line from the **current** menu (the waiter's screen is only a preview).

## Problems found (reproduced with tests)
Editing the menu could cause a `500` or store a value that breaks orders later:

| # | What the admin sends | What happened |
|---|----------------------|---------------|
| P1 | `price`, `name`, `category_id`, `discount_type`, `discount_value`, `tax_type`, `tax_value`, `is_available`, `is_promoted` or `modifiers_config` as `null` in `PUT /menu-items/{id}` | `500` (NOT NULL constraint) |
| P2 | `price` / `discount_value` = `NaN` | `500` |
| P3 | `price` = `Infinity` (also a modifier option price) | value **saved**, then the answer failed with `500`; every later order for the item breaks |
| P4 | negative `price`, `takeaway_price` or `discount_value` | saved; ordering that item then fails with `500` (line subtotal below 0) |
| P5 | `discount_type = percentage` with `discount_value` 150 | saved; ordering then `500` (negative price) |
| P6 | `price` 1e308 | saved; totals overflow in reports |
| P7 | empty / blank `name` | saved |
| P8 | `category_id` that does not exist | saved; item disappears from the menu |
| P9 | order line with a modifier price `NaN` / `Infinity` / hugely negative (sent by the waiter's device) | `500`; with `Infinity` an order was **created** with an infinite total |
| P10 | `price` below a fixed discount | already safe (discount is capped at the price) |

## FR-P1: Menu item input (`MenuItemCreate`, `MenuItemUpdate`, upload form)
- `price`, `discount_price`, `takeaway_price`, `discount_value`, `tax_value`: finite numbers, `0 ≤ value ≤ 1,000,000,000`. Anything else → `422`.
- `name`: text without surrounding spaces, 1–255 characters, not blank → `422`.
- `discount_type = percentage` → `discount_value ≤ 100`; `tax_type = percentage` → `tax_value ≤ 100` → `422`. (For a partial update the server checks the values the item **will have**, e.g. sending only `discount_value: 150` for an item that is already a percentage discount is refused.)
- Modifier option `price`: finite, `-1,000,000,000 … 1,000,000,000` (a negative option, such as "no meat −500", stays allowed).
- In `PUT /menu-items/{id}` an explicit `null` for a field the database cannot leave empty (P1 list) → `422`. Fields that may be cleared (`discount_price`, `takeaway_price`, `description`, `image_url`) still accept `null`. A field that is not sent is left alone, as before.
- `category_id` must exist → `404` (`Category id N not found`).
- **Price `0` stays allowed** (the admin form already allows "0 or greater"; for example complimentary items).

## FR-P2: Ordering with the current menu
- A percentage item discount is capped at the price, like a fixed one already is (an item never goes below 0 because of a discount).
- A line whose total would be below 0, or not a finite number, is refused with `400` (`Price of '<item>' is not valid …`) **before anything is saved**. This protects against bad data that is already in an existing database.
- `SelectedModifier.price` from a client: finite, `-1,000,000,000 … 1,000,000,000` → otherwise `422`.

## FR-P3: No change to recorded money
- Changing a menu price, discount, tax or modifier never changes an existing order line, an open order total, a paid order or a report. (Locked in by tests.)

## Out of scope / not changed
- A waiter's modifier prices are still taken from the waiter's screen (kept up to date by `menu_item_updated`); the server does not re-check them against the menu. If the owner wants the server to price modifiers from the menu itself, that is a separate change.
- Quantity limits, price history log (who changed which price when), scheduled future prices.
