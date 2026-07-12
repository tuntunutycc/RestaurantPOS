# Requirements: Predefined Instruction Tags (Quick Tags)

## Purpose
Speed up waiter order entry by offering one-click **predefined special instruction** chips in the modifier/special-instructions modal, while still allowing free-text entry.

## Data model — `PredefinedInstruction`

| Field | Type | Notes |
|-------|------|-------|
| `id` | Integer PK | |
| `text` | String(255) | Unique, non-empty instruction label |

Stored in table `predefined_instructions`. Not tied to menu items — store-wide tags.

## FR-Q1: Default seed
On first run (empty table), seed:
- `အချိုမှုန့်ရှောင်`
- `အစပ်လျှော့`
- `နံနံပင်ရှောင်`

## FR-Q2: API

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| GET | `/api/predefined-instructions` | `POS_ORDER_ROLES` | List all tags (sorted by id) |
| POST | `/api/predefined-instructions` | `ADMIN_PANEL_ROLES` | Create `{ "text": "..." }` |
| DELETE | `/api/predefined-instructions/{id}` | `ADMIN_PANEL_ROLES` | Remove tag |

Validation: trim whitespace; reject empty; max 255 chars; duplicate text → `400`.

## FR-Q3: Waiter UI
In the **Special Instructions** area of the modifier modal (`waiter.html` / `waiter.js`):
- Fetch tags on waiter screen load (refresh when modal opens).
- Render clickable chips **above** the textarea.
- **Append behavior:** clicking a chip appends its text to the textarea:
  - If empty → set to chip text
  - If non-empty → append `, {chip text}` (comma + space)
- Manual typing remains unchanged.

## FR-Q3b: Quantity in modifier modal
In the same customize / Add to Cart modal:
- Show inline **`-` / qty / `+`** controls (default qty `1`, minimum `1` while modal is open — cannot go to 0 in the modal)
- **Add to Cart** button label shows **unit line price × qty** (base + selected modifiers, before cart tax/discount breakdown)
- On confirm, add **that quantity** as one cart line (same notes/modifiers applied to the whole line)
- Cart-side `+`/`-` (FR-WB1c) remains the way to adjust qty after the line is in the cart

Does not affect the Active Order pop-out modal.

## FR-Q4: Admin UI
Counter **Menu Management** tab (`counter.html` / `counter.js`):
- List existing tags with delete control
- Form to add a new tag
- Uses admin API (root/admin only)

## Authorization
- Read — `POS_ORDER_ROLES` (waiter, cashier, admin, root)
- Write — `ADMIN_PANEL_ROLES` (admin, root)

## Related
- Order line `note` / `special_instructions` — unchanged; chips only populate the input before submit
- `specs/database-schema.md`, `specs/api-reference.md`
