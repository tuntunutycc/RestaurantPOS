# Create Menu Item with Image Upload & Real-Time Updates

This document describes the **Create Menu Item** feature: local image upload, storage under `static/images/menu/`, and real-time broadcasting to Waiter and Kitchen via WebSockets.

---

## 1. Backend & Storage (Local)

### API endpoint (form data)

- **POST `/api/menu-items/upload`**  
  Accepts **multipart form data**:
  - `name` (required)
  - `price` (required)
  - `category_id` (required)
  - `description` (optional)
  - `image` (optional file: jpg, jpeg, png, gif, webp)

**Behavior:**

1. Validates and reads form fields.
2. If `image` is present: saves the file under **`static/images/menu/`** with a UUID filename (e.g. `a1b2c3d4.jpg`).
3. Stores in the DB the **relative URL** only, e.g. **`/images/menu/a1b2c3d4.jpg`**.
4. Creates the menu item row (including `description` and `image_url`).
5. Broadcasts a **WebSocket** event `menu_item_added` with the full new menu item (so Waiter/Kitchen can update without refresh).
6. Returns the created menu item as JSON.

**Static serving:**  
The app already mounts `static/` at `/`. So `static/images/menu/xxx.png` is served at **`/images/menu/xxx.png`**. No extra static config is needed.

**Error handling:**  
- Invalid image type → **400** with message.  
- Missing/invalid required fields → **422** (FastAPI validation).  
- DB or file I/O errors → **500**; frontend shows a generic error message.

---

## 2. Real-Time Broadcasting (WebSockets)

### WebSocket setup

- **Module:** `websocket_manager.py`  
  - `ConnectionManager`: keeps a set of active WebSocket connections, and has:
    - `connect(websocket)` / `disconnect(websocket)`
    - `broadcast(event, data)` — sends `{"event": "<event>", "data": <data>}` to all connections.

- **Endpoint:** **`/ws`** (in `main.py`)  
  - Accepts WebSocket connections.  
  - Registers each connection with `app.state.ws_manager`.  
  - Keeps the connection open (reads messages to keep alive; content ignored).  
  - On disconnect, unregisters the connection.

### When is `menu_item_added` emitted?

- After **successfully** creating a menu item in:
  - **POST `/api/menu-items/upload`** (form + image), or  
  - **POST `/api/menu-items/`** (JSON body).
- Payload: **full menu item** (id, name, price, category_id, description, image_url) so clients can append it to the UI.

---

## 3. Frontend Implementation

### Admin (Counter / Menu Management)

- **Form fields:**  
  Item name, price, **description** (optional textarea), category (dropdown), and **image** (optional): either a text URL or a **file input** (upload).

- **Submit logic:**  
  - If the user selected an **image file**:  
    - Build **FormData** with `name`, `price`, `category_id`, optional `description`, and `image` (file).  
    - **POST** to **`/api/menu-items/upload`** (no `Content-Type` header; browser sets multipart).  
  - If **no file**:  
    - Send **JSON** to **POST `/api/menu-items/`** with `name`, `price`, `category_id`, optional `description` and `image_url`.

- **Error handling:**  
  - On non-2xx: read `response.json()`, show `detail` (or validation errors) in an alert; keep form filled so the user can fix and retry.  
  - On network/exception: show a generic “Failed to create menu item” (or “Upload failed”) message.

- **Success:**  
  Clear form (including description and image file), then refresh the menu list (e.g. refetch and re-render).  
  Other clients (Waiter, Kitchen) update via WebSocket; Admin sees the new item in the refreshed list.

### Waiter

- **WebSocket client:**  
  - On load, open **`ws://<host>/ws`** (or `wss://` if HTTPS).  
  - On **message**: parse JSON; if `event === "menu_item_added"`, take `data` (menu item).  
  - If the item is not already in the local menu list (e.g. by `id`), **append** it and **re-render** the menu grid (name, price, image if present).  
  - On **close** / **error**: reconnect after a short delay (e.g. 3 s).

- **Result:**  
  When Admin (or anyone) creates a menu item, the Waiter view updates **without refresh** and the new item (with image) appears in the grid.

### Kitchen

- **WebSocket client:**  
  - Same as Waiter: connect to **`/ws`**, listen for **`menu_item_added`**.  
  - Keep a list of “menu items” (or “new items”) and append the new one if not already present; **re-render** the “Menu (live)” section (e.g. list of names + thumbnails).

- **Result:**  
  New menu items (with image) appear in the Kitchen “Menu (live)” list in **real time** without refresh.

---

## 4. Step-by-Step Usage

1. **Start the server**  
   `uvicorn main:app --reload`

2. **Admin: Create a menu item with image**  
   - Open **Counter** → **Menu Management** (or home **/**).  
   - Fill name, price, optional description, category.  
   - Click **Upload** and choose an image (or enter an image URL).  
   - Submit.  
   - Form clears and the new item appears in the list; image is at `/images/menu/<uuid>.<ext>`.

3. **Waiter: See new item without refresh**  
   - Open **Waiter** in another tab/device.  
   - After Admin creates an item, the new item (with image) appears in the menu grid **automatically**.

4. **Kitchen: See new item without refresh**  
   - Open **Kitchen** in another tab/device.  
   - After a create, the new item appears in the **“Menu (live)”** section **automatically**.

5. **Optional: Test WebSocket**  
   - Open browser DevTools → Network → WS; confirm connection to `/ws`.  
   - Create an item from Admin; in the WS frame you should see a message with `event: "menu_item_added"` and the item payload.

---

## 5. File / Folder Summary

| Path | Purpose |
|------|--------|
| `static/images/menu/` | Local folder where uploaded menu images are stored; served at `/images/menu/`. |
| `websocket_manager.py` | ConnectionManager and broadcast logic. |
| `main.py` | `/ws` endpoint; `app.state.ws_manager`; creates `static/images/menu` if missing. |
| `routers/menu.py` | `POST /api/menu-items/upload` (form); `POST /api/menu-items/` (JSON); both broadcast `menu_item_added`. |
| `static/counter.js` | Admin form: FormData submit to `/api/menu-items/upload` when file present; error handling. |
| `static/waiter.js` | WebSocket client; on `menu_item_added` appends new item and re-renders menu grid. |
| `static/kitchen.js` | WebSocket client; on `menu_item_added` appends to “Menu (live)” and re-renders. |
