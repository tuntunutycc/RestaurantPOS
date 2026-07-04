"""Role constants and permission sets for RBAC."""

ROLE_ROOT = "root"
ROLE_ADMIN = "admin"
ROLE_ACCOUNT = "account"
ROLE_CASHIER = "cashier"
ROLE_WAITER = "waiter"

ALL_ROLES = frozenset({ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT, ROLE_CASHIER, ROLE_WAITER})
PASSWORD_ROLES = frozenset({ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT})
PIN_ROLES = frozenset({ROLE_CASHIER, ROLE_WAITER})
SINGLE_DEVICE_ROLES = frozenset({ROLE_ACCOUNT, ROLE_CASHIER, ROLE_WAITER})
MULTI_DEVICE_ROLES = frozenset({ROLE_ROOT, ROLE_ADMIN})

# Admin panel: menu, tables, printers, staff (with restrictions inside handlers)
ADMIN_PANEL_ROLES = [ROLE_ROOT, ROLE_ADMIN]

# POS order read/write (not checkout)
POS_ORDER_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_CASHIER, ROLE_WAITER]

# Checkout / payment
CHECKOUT_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_CASHIER]

# Full store reports
FULL_REPORT_ROLES = [ROLE_ROOT, ROLE_ADMIN, ROLE_ACCOUNT]

# Roles an admin may create/edit/delete
ADMIN_MANAGEABLE_ROLES = frozenset({ROLE_CASHIER, ROLE_WAITER, ROLE_ACCOUNT})

# Roles root may create/edit/delete via root admin API
ROOT_MANAGEABLE_ROLES = frozenset({ROLE_ADMIN})

# Max report lookback for account role (days)
ACCOUNT_MAX_REPORT_DAYS = 93
