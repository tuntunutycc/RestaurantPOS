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
