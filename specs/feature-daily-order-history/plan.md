# Plan: Daily Order History

1. Contract: `DailyOrderHistoryItem`, `DailyOrderHistoryOrder`, list + export schemas/constants in `rbac.py`.
2. Query helper + `GET /api/orders/daily-history` and `/export` (openpyxl workbook).
3. Static `order-history.html` / `order-history.js`; FastAPI routes; nav link for admin/cashier.
4. Pytest: list shape, role gate, export content-type + row presence.
5. CHANGELOG + api-reference + validation evidence.
