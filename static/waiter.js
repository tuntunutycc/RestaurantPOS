const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['waiter', 'admin'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

let menuItems = [];
let categories = []; // { id, name } from API
let activeCategoryId = null; // null = "All"
const cart = new Map(); // menu_item_id -> { menu_item, quantity }

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
}

async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

/** Get categories that have at least one menu item, in API order; "All" is handled separately. */
function getCategoriesWithItems() {
  const ids = new Set(menuItems.map((m) => m.category_id));
  return categories.filter((c) => ids.has(c.id));
}

function setActiveCategory(categoryId) {
  activeCategoryId = categoryId;
  renderCategoryTabs();
  renderMenu();
}

function renderCategoryTabs() {
  const container = document.getElementById('category-tabs');
  if (!container) return;
  const withItems = getCategoriesWithItems();
  const allLabel = 'All'; // or 'အားလုံး' for Burmese
  container.innerHTML = [
    `<button type="button" data-category-id="" class="category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeCategoryId === null ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(allLabel)}</button>`,
    ...withItems.map(
      (c) =>
        `<button type="button" data-category-id="${c.id}" class="category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeCategoryId === c.id ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(c.name)}</button>`
    ),
  ].join('');

  container.querySelectorAll('.category-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.categoryId;
      setActiveCategory(id === '' ? null : parseInt(id, 10));
    });
  });
}

/** Items to show: all or filtered by activeCategoryId */
function getFilteredMenuItems() {
  if (activeCategoryId == null) return menuItems;
  return menuItems.filter((m) => m.category_id === activeCategoryId);
}

function renderMenu() {
  const grid = document.getElementById('menu-grid');
  const filtered = getFilteredMenuItems();
  if (!menuItems.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No menu items. Add some from the main menu first.</p>';
    return;
  }
  if (!filtered.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No items in this category.</p>';
    return;
  }
  grid.innerHTML = filtered
    .map(
      (m) => {
        const imgSrc = m.image_url || null;
        const imgHtml = imgSrc
          ? `<img src="${escapeAttr(imgSrc)}" alt="" class="w-full h-20 object-cover rounded-t-lg" />`
          : `<div class="w-full h-20 bg-slate-200 rounded-t-lg flex items-center justify-center text-slate-400 text-xs">No image</div>`;
        return `
      <button
        type="button"
        data-id="${m.id}"
        data-name="${escapeAttr(m.name)}"
        data-price="${m.price}"
        class="menu-item-btn text-left p-0 bg-white rounded-lg shadow hover:bg-blue-50 border border-slate-200 overflow-hidden"
      >
        ${imgHtml}
        <span class="font-medium text-slate-800 block px-2 pt-1">${escapeHtml(m.name)}</span>
        <span class="text-sm text-slate-600 block px-2 pb-2">$${Number(m.price).toFixed(2)}</span>
      </button>
    `;
      }
    )
    .join('');

  grid.querySelectorAll('.menu-item-btn').forEach((btn) => {
    btn.addEventListener('click', () => addToCart(Number(btn.dataset.id), btn.dataset.name, parseFloat(btn.dataset.price)));
  });
}

function addToCart(id, name, price) {
  const current = cart.get(id);
  if (current) {
    current.quantity += 1;
  } else {
    cart.set(id, { menu_item: { id, name, price }, quantity: 1 });
  }
  renderCart();
}

function updateCartQuantity(id, delta) {
  const item = cart.get(id);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) cart.delete(id);
  renderCart();
}

function renderCart() {
  const list = document.getElementById('cart-list');
  const totalEl = document.getElementById('cart-total');
  const submitBtn = document.getElementById('submit-order');

  if (cart.size === 0) {
    list.innerHTML = '<li class="text-slate-500">Cart is empty</li>';
    totalEl.textContent = '$0.00';
    submitBtn.disabled = true;
    return;
  }

  let total = 0;
  list.innerHTML = '';
  cart.forEach(({ menu_item, quantity }, id) => {
    const subtotal = menu_item.price * quantity;
    total += subtotal;
    const li = document.createElement('li');
    li.className = 'flex items-center justify-between gap-2';
    li.innerHTML = `
      <span class="flex-1 truncate">${escapeHtml(menu_item.name)} × ${quantity}</span>
      <span class="font-medium">$${subtotal.toFixed(2)}</span>
      <div class="flex items-center gap-0">
        <button type="button" data-id="${id}" class="qty-btn minus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">−</button>
        <span class="w-6 text-center text-sm">${quantity}</span>
        <button type="button" data-id="${id}" class="qty-btn plus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">+</button>
      </div>
    `;
    list.appendChild(li);
  });

  list.querySelectorAll('.qty-btn.minus').forEach((btn) => {
    btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), -1));
  });
  list.querySelectorAll('.qty-btn.plus').forEach((btn) => {
    btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), 1));
  });

  totalEl.textContent = `$${total.toFixed(2)}`;
  submitBtn.disabled = false;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
}

async function submitOrder(tableId, items) {
  const res = await fetch(`${API_BASE}/api/orders/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
    body: JSON.stringify({ table_id: tableId, items }),
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = Array.isArray(data.detail) ? data.detail.map((x) => x.msg || x).join(', ') : (data.detail || 'Failed to submit order');
    throw new Error(msg);
  }
  return data;
}

document.getElementById('submit-order').addEventListener('click', async () => {
  const tableInput = document.getElementById('table-number');
  const tableNumber = parseInt(tableInput.value, 10);
  if (!tableNumber || tableNumber < 1) {
    if (window.toast) window.toast.error('Please enter a valid table number.');
    else alert('Please enter a valid table number.');
    return;
  }
  if (cart.size === 0) {
    if (window.toast) window.toast.error('Cart is empty.');
    else alert('Cart is empty.');
    return;
  }

  const items = [];
  cart.forEach(({ menu_item, quantity }) => {
    items.push({ menu_item_id: menu_item.id, quantity });
  });

  const submitBtn = document.getElementById('submit-order');
  submitBtn.disabled = true;
  try {
    const data = await submitOrder(tableNumber, items);
    cart.clear();
    renderCart();
    tableInput.value = '';
    if (window.toast) {
      window.toast.success(data.message || (data.is_new_order ? `New order created for Table ${data.table_number}` : `Items added to Table ${data.table_number}'s existing order`));
    } else {
      alert(data.message || 'Order submitted.');
    }
  } catch (err) {
    console.error(err);
    if (window.toast) window.toast.error(err.message || 'Failed to submit order');
    else alert(err.message || 'Failed to submit order');
  } finally {
    submitBtn.disabled = false;
  }
});

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws`;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.event === 'menu_item_added' && msg.data) {
        const item = msg.data;
        if (!menuItems.some((m) => m.id === item.id)) {
          menuItems.push({
            id: item.id,
            name: item.name,
            price: item.price,
            category_id: item.category_id,
            description: item.description ?? null,
            image_url: item.image_url ?? null,
          });
          renderCategoryTabs();
          renderMenu();
        }
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  };
  ws.onclose = () => {
    setTimeout(connectWebSocket, 3000);
  };
  ws.onerror = () => {};
}
connectWebSocket();

if (window.auth && window.auth.getToken()) {
  (async function init() {
    try {
      const [items, cats] = await Promise.all([fetchMenuItems(), fetchCategories()]);
      menuItems = items;
      categories = cats;
      activeCategoryId = null;
      renderCategoryTabs();
      renderMenu();
    } catch (e) {
      console.error(e);
      document.getElementById('menu-grid').innerHTML =
        '<p class="col-span-full text-red-600">Error loading menu.</p>';
    }
  })();
}
