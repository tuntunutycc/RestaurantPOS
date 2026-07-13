# System Analyst QA Test Plan (E2E Manual Routine)

**Product:** Restaurant POS (Myanmar)  
**Scope:** Waiter split-pane, Cashier 3-pane, network receipt printing, tax/discount math, payment methods, predefined instructions, menu RBAC availability  
**Prerequisites:** App running locally (`uvicorn main:app --host 0.0.0.0 --port 8000 --reload`), browser Local Storage cleared of stale `pos_token` / `pos_user` after DB wipe  
**Related specs:** `feature-waiter-two-pane-layout`, `feature-cashier-three-pane`, `feature-cashier-receipt-printing`, `feature-menu-item-tax`, `feature-menu-item-discount`, `feature-payment-method-analytics`, `feature-predefined-instructions`, `feature-menu-rbac`

> **Automated baseline:** Run `PYTHONPATH=. pytest -q` before manual E2E. Suite must be fully green.

---

## 1. Preparation — Fresh database & Admin login

> There is no `reset_db.py` in this repo. Use the documented wipe + root seed (same outcome as a full DB reset).

- [ ] Stop the running server (Ctrl+C)
- [ ] Wipe SQLite DB:
  ```bash
  rm -f pos.db
  ```
- [ ] Recreate schema + seed root:
  ```bash
  PYTHONPATH=. python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
  PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'
  ```
- [ ] Start server:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
- [ ] Clear browser Local Storage (`pos_token`, `pos_user`) or use a private window
- [ ] Open `/login` and sign in as **root** (`root` / `YourSecurePass123`)
- [ ] **Expected:** Redirect to Counter (`/counter`); root can open Admin/Menu/Tables panels

### Create working staff (before Waiter/Cashier flows)

- [ ] Create an **admin** (password login) if QA prefers non-root for setup
- [ ] Create **waiter** (4-digit PIN) via Staff UI
- [ ] Create **cashier** (4-digit PIN) via Staff UI
- [ ] **Expected:** Waiter/Cashier can log in at `/pin-login` with their PINs

---

## 2. Admin Setup

### 2.1 Categories & printer routes

- [ ] Open **Menu Management** → Categories
- [ ] Create at least two categories (e.g. **Drinks**, **Food**)
- [ ] Assign printer routes: Drinks → `drinks`, Food → `food`
- [ ] **Expected:** Categories list shows names; routes save without error

### 2.2 Menu items (tax & discount variants)

Create items that exercise pricing math (tax **after** discount):

| Item | Base price | Discount | Tax | Notes |
|------|------------|----------|-----|-------|
| A — No tax | 1000 | none | none | Baseline |
| B — % tax | 1000 | none | 5% | Tax on full price |
| C — Discount + tax | 1000 | 10% | 5% | Tax on **900** (after discount) |
| D — Fixed tax | 2000 | fixed 200 | fixed 100 | Spot-check snapshots |

- [ ] Create items A–D (or equivalent) with images optional
- [ ] **Expected:** Items appear in admin list with tax/discount fields persisted after refresh

### 2.3 Zones & tables

- [ ] Open **Table Management**
- [ ] Create a zone (e.g. Main Hall)
- [ ] Add ≥3 tables; leave them available
- [ ] Open Waiter or Cashier floor later — status label for available tables is **Free** (not “Available”)
- [ ] Zone tabs include **ALL** (default shows every table)
- [ ] **Expected:** Tables visible under ALL and under their zone

### 2.4 Predefined instruction tags

- [ ] Menu Management → **Quick Instruction Tags**
- [ ] Add tags (e.g. Less Spicy, No Onion, Extra Sauce)
- [ ] **Expected:** Tags list updates; Delete removes a tag

### 2.5 Printer settings (kitchen + cashier)

- [ ] Menu Management → **Kitchen Printer Settings**
- [ ] Set **Render mode** to **Image** (recommended for Myanmar Unicode)
- [ ] Set paper width (80mm / 576px or 58mm / 384px)
- [ ] Enter LAN IPs for **Drinks**, **Food**, and **Cashier receipt** printers (or leave blank / dummy IP for offline test)
- [ ] Backend: `file` for safe QA without hardware, or `escpos_network` for real/dummy LAN IP
- [ ] Save settings
- [ ] Optionally set `SHOP_NAME` in `.env` (receipt header); default **My Restaurant**
- [ ] **Expected:** Settings reload correctly after Save / page refresh

### 2.6 Menu RBAC (Cashier availability)

- [ ] Log in as **cashier** (PIN)
- [ ] Open Menu Management — **Expected:** availability toggles only (no Add/Edit/Delete)
- [ ] Toggle one item Sold Out / In Stock
- [ ] Log in as **waiter** — **Expected:** sold-out item greyed / not addable
- [ ] Log back in as admin/root for remaining setup if needed

---

## 3. Waiter Flow (Split-Pane + Modal)

Log in as **waiter** → `/waiter`

### 3.1 Layout smoke

- [ ] Left pane: Menu + Cart (rose/red tint)
- [ ] Right pane: Zone tabs + table floor / takeaways (green/emerald tint)
- [ ] **Expected:** Both panes visible on desktop; cart does not occupy the whole screen

### 3.2 New dine-in order

- [ ] Click an empty (**Free**) table — cart context shows that table
- [ ] Add items (include item C with discount+tax if available)
- [ ] Use cart line **`+` / `-`** to change qty; confirm notes stay; totals update; `-` to 0 removes the line
- [ ] Open customize modal → click a **Predefined Instruction** chip → confirm note appears → Add to Cart
- [ ] Verify cart footer: Subtotal, Discount, Tax, Grand Total, then **Submit**
- [ ] Submit order
- [ ] **Expected:** Success; table becomes **Occupied**; kitchen ticket side-effect (file output or LAN) does not block submit

### 3.3 Occupied table → active-order modal

- [ ] Click the same occupied table
- [ ] **Expected:** Centered **active-order modal** opens (does **not** replace the new-order cart)
- [ ] Modal shows item list + price breakdown (Subtotal / Discount / Tax / Grand Total)
- [ ] Cancel one unserved line item → confirm
- [ ] **Expected:** Item cancelled; totals update; if last item cancelled, table returns to **Free** and modal closes
- [ ] (Optional) **Add More Items** → append mode → submit another batch → modal/order reflects new lines

### 3.4 Walk-in takeaway (optional but recommended)

- [ ] Click **Walk-in Takeaway** → optional customer name → start cart
- [ ] Add items → Submit
- [ ] Click takeaway card on floor → **Expected:** same active-order modal as dine-in
- [ ] **Expected:** Cashier later shows takeaway label / Served by, not “Deleted Table”

---

## 4. Cashier Flow (3-Pane)

Log in as **cashier** → Counter → **Cashier / Billing**

### 4.1 Layout smoke

- [ ] Three panes: **Tables | Takeaways | Check Out**
- [ ] Each pane scrolls independently on large screens
- [ ] **Expected:** No nested takeaway-under-tables; no modal required to select an order

### 4.2 Select order → Check Out pane

- [ ] Click **Free** table → **Expected:** empty/unavailable alert; Check Out unchanged
- [ ] Click **Occupied** table → **Expected:** right pane fills with items, Served by, totals
- [ ] Click an active **takeaway** → **Expected:** Check Out switches to that order

### 4.3 Tax / discount math (item-level)

Using an order that includes discount+tax item (e.g. item C: price 1000, 10% discount, 5% tax):

- [ ] Per line: discounted base = 900; unit tax = 45; line includes tax in subtotal
- [ ] Pane totals: Subtotal (sum of line subtotals), order-level Discount (if cashier applies one), Tax, Grand Total
- [ ] **Expected:** Tax is computed on **post-discount** unit prices (not on pre-discount base). Spot-check one line against server receipt fields after checkout

### 4.4 Payment method

- [ ] Toggle **Cash** — hidden `payment_method` = cash
- [ ] Toggle **Mobile Money** — method = mobile_money
- [ ] Enter amount tendered ≥ Grand Total; Change updates correctly
- [ ] **Expected:** Cannot confirm if tendered &lt; total

---

## 5. Network Printing (Checkout receipt)

### 5.1 Print Receipt ON (default)

- [ ] Ensure **Print Receipt** checkbox is checked (`issue_receipt=true`)
- [ ] Choose Cash or Mobile Money; Confirm Payment
- [ ] **Expected:** Success dialog; order leaves unpaid lists; table → Free
- [ ] **If printer reachable / file backend:** physical receipt or `cashier_printer_output.txt` / `.png` appears with Shop Name, Order ID, Served by, items, Subtotal, Discount, Tax, Grand Total, Payment Method
- [ ] **If printer IP offline/dummy with `escpos_network`:** checkout still succeeds; toast: *Checkout successful, but receipt printer is offline!*
- [ ] **Expected:** Browser does **not** open the system print dialog (`window.print` retired)

### 5.2 Print Receipt OFF

- [ ] Place another small order; select it in Check Out
- [ ] **Uncheck** Print Receipt → Confirm Payment
- [ ] **Expected:** Payment success; **no** new receipt print / no printer offline toast required

---

## 6. Dashboard Analytics (Cash vs Mobile Money)

Log in as **root / admin / account** (store-wide) or the **cashier** who performed checkouts (own sales only).

- [ ] Open Counter **Dashboard**
- [ ] Locate **Today** (and Month) Cash vs Mobile Money cards / breakdown
- [ ] Complete at least one **Cash** and one **Mobile Money** checkout in section 4–5
- [ ] Refresh dashboard
- [ ] **Expected:** Today’s Cash total increases only for cash checkouts; Mobile Money only for mobile_money; **Total = Cash + Mobile Money**
- [ ] **Expected:** Waiter account cannot load sales-breakdown (403) if tested

---

## 7. Regression smoke (quick)

- [ ] Waiter WebSocket: second browser/tab updates table occupancy after submit/cancel/checkout
- [ ] ALL zone tab still lists all tables after checkout frees a table
- [ ] Soft-deleted / sold-out menu items do not break historical receipt display
- [ ] Myanmar item names / notes render acceptably on image-mode kitchen or receipt preview

---

## Sign-off

| Field | Value |
|-------|-------|
| Tester name | |
| Date | |
| Build / commit | |
| Automated pytest | ☐ Pass (record count: ______ ) |
| Manual E2E | ☐ Pass / ☐ Pass with notes |
| Notes / defects | |

---

## Defect logging tips

When filing a bug, include: role, URL, order id, payment method, `issue_receipt` on/off, printer backend/render mode, screenshot of Check Out pane or Waiter modal, and whether the failure was UI-only or also visible in API (`PUT /api/orders/{id}/checkout` response `warning` field).
