# Plan: Cashier Network Receipt Printing

## Approach
1. Specs + contract (`issue_receipt`, `OrderCheckoutResponse.warning`, endpoint route `cashier`)
2. Extend printer endpoint registry; seed `cashier`; admin UI host/port
3. Receipt text builder + `dispatch_cashier_receipt` reusing kitchen image/ESC/POS
4. Checkout: commit first, then print attempt with 3s timeout; never roll back payment
5. Counter UI: Print Receipt checkbox; drop browser print; toast on `warning`
6. Pytest: mock TCP `ConnectionError`; assert 200 + warning; file-backend happy path
