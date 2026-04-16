# Mission

## Purpose
Build a fully functional, Myanmar-restaurant POS system that is reliable in daily use and designed so new features can be added safely over time.

## Target Audience
- `admin`: manages staff accounts, menu, categories, zones, tables, and monitors operational reports
- `waiter`: takes dine-in and takeaway orders, sends items to kitchen, updates item status as served/cooked/cancelled
- `cashier`: checks out orders with payment and discounts, and views tables and sales reports

## Core Functional Requirements
### Authentication & Roles
- Staff login via username+password and/or PIN
- Role-based access control for admin/waiter/cashier actions
- JWT-based session for API calls

### Menu Management
- CRUD for `categories` and `menu items`
- Enable/disable menu items (`is_available`)
- Support modifiers (required/optional groups and options with prices)
- Support menu item images

### Order Taking (Dine-in & Takeaway)
- Create a new order or append items to the existing open/dining order for a table
- Support `batch_number` behavior for kitchen ticketing (each submit becomes a new batch)
- Capture per-line details:
  - quantity
  - selected modifiers
  - note / special instructions
  - waiter attribution (who created the line/batch)

### Realtime Kitchen / UI Updates
- Kitchen/KDS receives new order batches in realtime
- Table grid and cashier views update in realtime (WebSocket events)

### Order Status & Cancellation
- Update item-level status (e.g., `pending`, `cooking`, `served`, `cancelled`)
- Ensure order totals reflect cancellation rules consistently (data correctness is critical)

### Checkout (Cashier)
- Finalize payment for an order:
  - `payment_method`
  - `amount_tendered`
  - optional discount (`percentage` or fixed `amount`)
  - compute `change_amount`
- Ensure checkout validates tender amount >= final total
- Mark order status as paid and return receipt details

### Reporting & Analytics
- Sales summaries (today, daily trend, monthly trend)
- Top selling items and cancellation analytics

## Success Criteria (Mission KPIs)
- Low `order error rate` (especially totals and order state)
- Fast `checkout time`
- Low `staff training/adoption time` (clear UX + predictable behavior)

