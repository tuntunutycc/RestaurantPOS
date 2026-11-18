# POS Final Review (2026 Nov 9 → 14 Nov 2026)

Source: client review sheet `POS final review (2026 NOV 9)` (Google Sheets → PDF).  
This document is a cleaned Markdown transcription of that review list for tracking in the repo.

**Legend (from sheet / notes)**

| Mark | Meaning |
|------|---------|
| `***` | High priority |
| `**` | Medium |
| `*` | Lower / nice-to-have |
| **Prioritized** | Explicitly marked as current priority on the sheet |
| **Solved** | Marked solved on the sheet |
| **Testing** | Marked testing on the sheet |

**Code verified** (2026-11-15): current repo status vs sheet — `DONE` / `PARTIAL` / `NOT_DONE`.

---

## 2026-11-15 polish batch (no DB)

Implemented without schema changes:

| # | Change | Status |
|---|--------|--------|
| **29** | Waiter order-details modal: takeaway badge + modifiers + note | **DONE** |
| **24** | Printed receipt + cashier checkout pane show line notes | **DONE** |
| **23 / 30** | Cashier checkout groups items by `batch_number` with dashed separators | **DONE** |
| **18** | Receipt / checkout line amount = pre-tax; Tax stays in footer | **DONE** |
| **27** | Selecting available table no longer scrolls/jumps to cart | **DONE** |

Tests: `tests/test_cashier_receipt_printing.py` (pre-tax line + note on checkout receipt + unit `build_receipt_text`). Related suites still green.

---

## Sheet “Solved” — ဟုတ်/မဟုတ်

| # | Sheet | Code verified | Verdict |
|---|-------|---------------|---------|
| **8** | Solved | **DONE** (image-mode + Pyidaungsu; text-mode thermal မှာ Myanmar မှားနိုင်သေး) | Sheet **မှန်** — production မှာ `render_mode=image` သုံးမှ အပြည့် |
| **12** | Solved | **DONE** (Admin/Waiter UI စာဘဲ; `image_url` column API ကျန်) | Sheet **မှန်** |
| **22** | Solved | **DONE** (kitchen = one slip per line, mods under parent, **price မပါ**; 2026-11-15 per-line restore) | Sheet **မှန်** |

---

## Prioritized / Testing — တကယ် ပြီးပြီလား

| # | Sheet | Code verified | Note |
|---|-------|---------------|------|
| **3** | Prioritized | **DONE** (အဓိက) | `/order-history` + Excel ရှိပြီး။ Gap: voucher# = `order.id`; Excel မှာ payment/tax/cashier columns မပြည့်; နေ့ခွဲ = UTC `created_at` |
| **16** | Prioritized | **PARTIAL** | Cashier-by-cashier **total** ရှိ။ **Cash/Kpay/MMQR ခွဲမရှိ** (mobile တစ်ပုံးပဲ) |
| **20** | Prioritized | **DONE** (print/receipt) | Kitchen + cashier receipt မှာ `(ပါဆယ်)` |
| **26** | Prioritized | **DONE** | Takeaway → invoice + kitchen ပါဆယ် |
| **29** | Prioritized | **DONE** | Waiter modal + cashier + print — ပါဆယ်/mods/note ပြပြီ (2026-11-15) |
| **19** | Testing | **DONE** (အဓိက) | Modifiers စျေးပေါင်း + kitchen Pattern A + tests |

---

## Prioritized (sheet highlight)

| # | Request | Priority | Sheet status | Code |
|---|---------|----------|--------------|------|
| **3** | Admin နှင့် cashier တို့ **နေ့စဉ် ရောင်းထားသော ဘောက်ချာ** ကို တခုချင်းစီ ပြန်ကြည့်နိုင်အောင် လုပ်ပေးရန်။ **Excel** မှာ record ထုတ်ပေးရန်။ | `***` | **Prioritized** | **DONE** (minor gaps) |
| **16** | Admin က cashier **တယောက်ချင်းစီ** ရဲ့ **Cash / Kpay / MMQR** ရောင်းရငွေ ကို သိနိုင်အောင် လုပ်ချင်။ | — | **Prioritized** | **PARTIAL** |
| **20** | တူညီသော အော်ဒါထဲမှာ ထိုင်စား + ပါဆယ် ရောရှိရင် — ဘောက်ချာနှင့် kitchen slip မှာ `takeaway` / `ပါဆယ်`။ | — | **Prioritized** | **DONE** |
| **26** | Take away နှိပ်ရင် invoice နှင့် kitchen order မှာ **ပါဆယ်** ပေါ်စေချင်။ | — | **Prioritized** | **DONE** |
| **29** | Waiter / cashier view အားလုံးမှာ ပါဆယ် စာသားပေါ်ရမယ်။ Takeaway price ≠ instruction tag `ပါဆယ်`။ | — | **Prioritized** | **DONE** |

---

## Full review list

### Data / admin ops

| # | Request | Priority | Sheet | Code |
|---|---------|----------|-------|------|
| 1 | Menu export / import backup | `***` | Open | **NOT_DONE** |
| 2 | Data reset (menu / transactions) | `**` | Open | **NOT_DONE** |
| 4 | Daily voucher number reset to 1 | `**` | Open | **NOT_DONE** |
| 6 | Admin delete/edit wrong paid voucher | `**` | Open | **NOT_DONE** |
| 7 | Manual data backup how-to | `***` | Open | **NOT_DONE** |

### Reporting / payments

| # | Request | Priority | Sheet | Code |
|---|---------|----------|-------|------|
| 5 | Per food-item sales reporting | `***` | Open | **PARTIAL** (top-items / history lines; full item×day report မရှိ) |
| 9 | Cash / Kpay / MMQR (+ split သုံးခု) | `**` | Open | **DONE** 2026-11-18 (`cash` / `kpay` / `mmqr` / `split`; `specs/feature-payment-kpay-mmqr/`) |
| 16 | Per-cashier Cash/Kpay/MMQR | — | Prioritized | **DONE** 2026-11-18 (Dashboard → Staff Performance; cashier = login account) |
| 3 | Daily vouchers + Excel | `***` | Prioritized | **DONE** |

### Printing / voucher layout

| # | Request | Priority | Sheet | Code |
|---|---------|----------|-------|------|
| 8 | Myanmar font on voucher | `***` | **Solved** | **DONE** ✓ |
| 13 | PDF print preview | `*` | Open | **NOT_DONE** |
| 15 | Printer down → block order + UI alert | — | Open | **PARTIAL** (health + warning; **submit မပိတ်**) |
| 17 | Paper-out warning / block submit | — | Open | **NOT_DONE** |
| 18 | Item price without tax; then Subtotal + Tax = Grand | — | Open | **DONE** ✓ (2026-11-15) |
| 22 | Kitchen = invoice layout without price | — | **Solved** | **DONE** ✓ |
| 23 | Same table second order → batch / dotted line | — | Open | **DONE** ✓ (cashier batch separators; kitchen already had Batch #) |
| 24 | Preconfig text on invoice **and** kitchen | — | Open | **DONE** ✓ (receipt + checkout note; kitchen already had note) |
| 30 | Cashier view batch grouping | — | Open | **DONE** ✓ (with #23) |

### Menu / ordering / takeaway

| # | Request | Priority | Sheet | Code |
|---|---------|----------|-------|------|
| 12 | Menu text only (no photos) | `*` | **Solved** | **DONE** ✓ |
| 19 | Submenu add-ons + kitchen + money | — | **Testing** | **DONE** (promote → Solved သင့်) |
| 20 | Line takeaway on voucher + kitchen | — | Prioritized | **DONE** |
| 21 | Round: ≤50 drop / ≥51 → 100 | — | Open | **NOT_DONE** |
| 26 | Takeaway → ပါဆယ် on invoice + kitchen | — | Prioritized | **DONE** |
| 28 | Table dine-in + line takeaway → show Table N (not guest) | — | Open | **DONE** |
| 29 | ပါဆယ် visible all views | — | Prioritized | **DONE** ✓ |
| 27 | GUI table select scrolls away | — | Open | **DONE** ✓ (2026-11-15) |

### Install / multi-device / UX

| # | Request | Priority | Sheet | Code |
|---|---------|----------|-------|------|
| 10 | exe / batch install | `*` | Open | **NOT_DONE** |
| 11 | Start / Stop exe or batch | `*` | Open | **NOT_DONE** |
| 14 | 2 cashiers: server + browser client | — | Note | **DONE** (architecture အရ သုံးနိုင်; dedicated setup doc မရှိ) |
| 25 | 2 waiters concurrent submit | — | Open | **PARTIAL** (table unique index; UX/error မပြည့်) |

---

## Still open (backlog — မှတ်ထား)

Ordered suggestion for later work (do **not** start without a short spec + confirmation):

### A. Money / payments (DB)
| # | Topic | Why next / risk |
|---|--------|-----------------|
| **9 → 16** | Cash / Kpay / MMQR (+ per-cashier report) | Client prioritized; needs payment columns |
| **21** | Nearest-100 rounding (≤50 drop / ≥51→100) | See **Rounding design** below — do **not** mutate line snapshots |
| **4** | Daily voucher number from 1 | Needs sequence + business date |
| **6** | Admin void/edit paid voucher | Soft-void + audit; high money risk |

### B. Ops / reports (little or no DB)
| # | Topic |
|---|--------|
| **5** | Per-item (× day) sales report |
| **15** | Printer offline: warn vs **block submit** (policy decision) |
| **17** | Paper-out detect (hardware-limited) |
| **1 / 7 / 2** | Menu export-import / backup guide / data reset |
| **25** | Concurrent waiter error UX |
| **10 / 11 / 13** | exe-batch start-stop / PDF preview |

### C. Already DONE in code (sheet may still say Prioritized/Testing)
`#3`, `#8`, `#12`, `#18`, `#19`, `#20`, `#22`, `#23`, `#24`, `#26`, `#27`, `#28`, `#29`, `#30`

---

## Rounding design (#21) — DB မရှုပ်အောင်

**မလုပ်သင့်:** line တိုင်းရဲ့ `unit_price_at_sale` / `subtotal` / `unit_tax_at_sale` ကို round ပြီး overwrite — report, modifier, tax ပြန်တွက်ရင် ကွဲမယ်။

**လုပ်သင့် (order-level only at checkout):**

1. Line math အရင်အတိုင်း တိတိကျကျ ထား (`order_items` မပြောင်း)  
2. Checkout မှာ exact payable = Σ active line `subtotal` − order discount  
3. Round rule: nearest **100** MMK — remainder ≤50 → down, ≥51 → up  
4. `orders` မှာ **၃ ခု** သိမ်း (သို့ ၂ ခု + derived):

| Column | Meaning |
|--------|---------|
| `total_before_rounding` | Exact payable before round |
| `rounding_adjustment` | `final − before` (e.g. `+40`, `-30`, or `0`) |
| `total_amount` | **Charged** amount after round (tender/change ဒီပေါ်မူ) |

Identity: `total_before_rounding + rounding_adjustment = total_amount`

5. Receipt footer ဥပမာ:
   - Subtotal / Discount / Tax (ရှိပြီးသား breakdown)
   - Amount due (exact)  
   - Rounding  
   - **Grand Total** (rounded)  
6. Reports: revenue = `total_amount` (ငွေရ); optional column `rounding_adjustment` sum for audit  
7. Open/dining orders: round **မလုပ်** until checkout (cart shows exact)

ဒါဆို DB က “မူရင်းလိုင်း” နဲ့ “ပေးချေရမည့် rounded total” ခွဲရှင်းတယ် — ရှုပ်မသွားဘူး။

---

## Notes

- Item numbers follow the client sheet (some numbers skipped on the original sheet).  
- **Sheet status** = client spreadsheet as of 9–14 Nov 2026.  
- **Code** = repo verification; polish batch updated 2026-11-15.  
- Related: `CHANGELOG.md`, `specs/feature-*/`.
