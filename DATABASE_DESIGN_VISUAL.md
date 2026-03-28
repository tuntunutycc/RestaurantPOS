# Database Design (Visual ERD)

This diagram reflects the current SQLAlchemy models in `models.py`.

```mermaid
erDiagram
    CATEGORIES {
        INT id PK
        STRING name
    }

    MENU_ITEMS {
        INT id PK
        STRING name
        FLOAT price
        STRING description
        STRING image_url
        BOOLEAN is_available
        INT category_id FK
    }

    ZONES {
        INT id PK
        STRING name
    }

    TABLES {
        INT id PK
        STRING name_or_number
        INT zone_id FK
        STRING status "available|occupied"
    }

    ORDERS {
        INT id PK
        INT table_id FK
        INT table_number "legacy"
        STRING status
        FLOAT total_amount
        DATETIME created_at
        STRING payment_method
        FLOAT amount_tendered
        FLOAT change_amount
    }

    ORDER_ITEMS {
        INT id PK
        INT order_id FK
        INT menu_item_id FK
        INT quantity
        FLOAT subtotal
        INT batch_number
        STRING batch_status
        STRING status "pending|cooking|served"
        INT created_by_id FK
    }

    USERS {
        INT id PK
        STRING username
        STRING password_hash
        STRING role "admin|waiter|kitchen|cashier"
        STRING pin_code
    }

    CATEGORIES ||--o{ MENU_ITEMS : has
    ZONES ||--o{ TABLES : contains
    TABLES ||--o{ ORDERS : serves
    ORDERS ||--o{ ORDER_ITEMS : includes
    MENU_ITEMS ||--o{ ORDER_ITEMS : referenced_by
    USERS ||--o{ ORDER_ITEMS : created_by
```

## Notes

- `Order.table_id` is the normalized table reference.
- `Order.table_number` is kept for backward compatibility with older data.
- `OrderItem.item_status` is stored in DB column `status`.
- Menu availability is controlled by `MenuItem.is_available`.
- Menu deletion is protected when order history exists (safe-delete rule).
