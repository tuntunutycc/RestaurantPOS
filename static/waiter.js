const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['waiter', 'admin'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

const AUTO_LOGOUT_AFTER_SUBMIT = false;
const TOKEN_KEY = 'pos_token';
const USER_KEY = 'pos_user';
const cart = new Map();
let menuItems = [];
let categories = [];
let activeCategoryId = null;
let zones = [];
let activeZoneId = null;
let selectedTableId = null;
let refreshTimer = null;
let tableDetailsOpen = false;
let tableDetailsOrderId = null;
let tableDetailsTableName = '';

function getCurrentUser() {
  return window.auth?.getUser?.() || null;
}

function tableLabel(table) {
  return table?.name || table?.name_or_number || `#${table?.id ?? ''}`;
}

function tableNameById(tableId, fallback) {
  const table = zones.flatMap((z) => z.tables || []).find((t) => t.id === tableId);
  return table ? tableLabel(table) : fallback;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML.replace(/"/g, '&quot;');
}

function showError(message) {
  if (window.toast?.error) window.toast.error(message);
  else window.alert(message);
}

function showSuccess(message) {
  if (window.toast?.success) window.toast.success(message);
  else window.alert(message);
}

function autoLogoutToPin() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem('pos_unauthorized');
  window.location.href = '/pin-login';
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...window.auth.getAuthHeaders(),
    },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = Array.isArray(data.detail)
      ? data.detail.map((x) => x.msg || x).join(', ')
      : (data.detail || 'Request failed');
    throw new Error(msg);
  }
  return data;
}

async function fetchMenuItems() {
  return fetchJson(`${API_BASE}/api/menu-items/`);
}

async function fetchCategories() {
  return fetchJson(`${API_BASE}/api/categories/`);
}

async function fetchTablesStatus() {
  return fetchJson(`${API_BASE}/api/tables/status`);
}

async function fetchActiveOrdersForMyTables() {
  return fetchJson(`${API_BASE}/api/orders/?status=open&status=dining&status=completed&status=pending`);
}

async function fetchActiveOrderByTable(tableId) {
  return fetchJson(`${API_BASE}/api/orders/active-by-table/${tableId}`);
}

async function fetchOrderDetails(orderId) {
  return fetchJson(`${API_BASE}/api/orders/${orderId}/details`);
}

async function markOrderItemServed(orderId, itemId) {
  return fetchJson(`${API_BASE}/api/orders/${orderId}/items/${itemId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'served' }),
  });
}

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
  container.innerHTML = [
    `<button type="button" data-category-id="" class="category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeCategoryId === null ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">All</button>`,
    ...withItems.map(
      (c) =>
        `<button type="button" data-category-id="${c.id}" class="category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeCategoryId === c.id ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(c.name)}</button>`
    ),
  ].join('');
  container.querySelectorAll('.category-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.categoryId;
      setActiveCategory(id === '' ? null : Number(id));
    });
  });
}

function getFilteredMenuItems() {
  if (activeCategoryId == null) return menuItems;
  return menuItems.filter((m) => m.category_id === activeCategoryId);
}

function renderMenu() {
  const grid = document.getElementById('menu-grid');
  const filtered = getFilteredMenuItems();
  if (!menuItems.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No menu items found.</p>';
    return;
  }
  if (!filtered.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No items in this category.</p>';
    return;
  }
  grid.innerHTML = filtered.map((m) => {
    const available = m.is_available !== false;
    const imgHtml = m.image_url
      ? `<img src="${escapeAttr(m.image_url)}" alt="" class="w-full h-20 object-cover rounded-t-lg" />`
      : `<div class="w-full h-20 bg-slate-200 rounded-t-lg flex items-center justify-center text-slate-400 text-xs">No image</div>`;
    const soldOutBadge = available
      ? ''
      : '<span class="absolute top-2 right-2 text-[11px] font-semibold px-2 py-0.5 rounded bg-red-600 text-white">Sold Out</span>';
    const cardStateClass = available ? 'hover:bg-blue-50' : 'opacity-50 grayscale pointer-events-none';
    return `
      <div class="menu-item-card text-left p-0 bg-white rounded-lg shadow border border-slate-200 overflow-hidden ${cardStateClass}">
        <div class="relative">
          ${imgHtml}
          ${soldOutBadge}
        </div>
        <div class="px-2 pt-1 pb-2">
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium text-slate-800 block">${escapeHtml(m.name)}</span>
            <button
              type="button"
              data-id="${m.id}"
              data-name="${escapeAttr(m.name)}"
              data-price="${m.price}"
              class="add-to-cart-btn h-7 w-7 rounded-full text-sm font-bold text-white ${available ? 'bg-blue-600 hover:bg-blue-700' : 'bg-slate-400 cursor-not-allowed'}"
              ${available ? '' : 'disabled'}
              aria-label="${available ? 'Add to cart' : 'Sold out'}"
            >
              +
            </button>
          </div>
          <span class="text-sm text-slate-600 block">$${Number(m.price).toFixed(2)}</span>
        </div>
      </div>`;
  }).join('');
  grid.querySelectorAll('.add-to-cart-btn').forEach((btn) => {
    btn.addEventListener('click', () => addToCart(Number(btn.dataset.id), btn.dataset.name, parseFloat(btn.dataset.price)));
  });
}

function setActiveZone(zoneId) {
  activeZoneId = zoneId;
  renderZoneTabs();
  renderTableCards();
}

function renderZoneTabs() {
  const container = document.getElementById('zone-tabs');
  if (!container) return;
  if (!zones.length) {
    container.innerHTML = '<span class="text-slate-500 text-sm">No zones found</span>';
    return;
  }
  container.innerHTML = zones.map((z) => (
    `<button type="button" data-zone-id="${z.id}" class="zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeZoneId === z.id ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(z.name)}</button>`
  )).join('');
  container.querySelectorAll('.zone-tab').forEach((btn) => {
    btn.addEventListener('click', () => setActiveZone(Number(btn.dataset.zoneId)));
  });
}

function getActiveZoneTables() {
  const zone = zones.find((z) => z.id === activeZoneId);
  return zone?.tables || [];
}

function renderSelectedTableLabel() {
  const label = document.getElementById('selected-table-label');
  if (!label) return;
  const selected = zones.flatMap((z) => z.tables || []).find((t) => t.id === selectedTableId);
  label.innerHTML = `Selected: <span class="font-medium">${selected ? escapeHtml(tableLabel(selected)) : 'None'}</span>`;
}

function renderTableCards() {
  const container = document.getElementById('table-cards');
  if (!container) return;
  const tables = getActiveZoneTables();
  if (!tables.length) {
    container.innerHTML = '<p class="col-span-full text-slate-500">No tables in this zone.</p>';
    renderSelectedTableLabel();
    renderCart();
    return;
  }
  container.innerHTML = tables.map((table) => {
    const isSelected = table.id === selectedTableId;
    const statusClass = table.status === 'occupied' ? 'bg-red-500 text-white' : 'bg-green-500 text-white';
    const ringClass = isSelected ? 'ring-2 ring-blue-700 ring-offset-2' : '';
    return `
      <button type="button" data-table-id="${table.id}" class="table-card rounded-md p-2 text-left transition ${statusClass} ${ringClass}">
        <div class="font-semibold">Table ${escapeHtml(tableLabel(table))}</div>
        <div class="text-xs uppercase tracking-wide">${escapeHtml(table.status)}</div>
      </button>
    `;
  }).join('');
  container.querySelectorAll('.table-card').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tableId = Number(btn.dataset.tableId);
      const table = zones.flatMap((z) => z.tables || []).find((t) => t.id === tableId);
      const tableName = tableLabel(table || { id: tableId });
      const isOccupied = String(table?.status || '').toLowerCase() === 'occupied';
      selectedTableId = tableId;
      renderTableCards();
      renderSelectedTableLabel();
      renderCart();
      if (isOccupied) {
        openTableDetailsSidebar(tableId, tableName).catch((err) => {
          console.error(err);
          showError(err.message || 'Failed to load table details');
        });
      }
    });
  });
  renderSelectedTableLabel();
  renderCart();
}

function addToCart(id, name, price) {
  const menuItem = menuItems.find((m) => m.id === id);
  if (menuItem && menuItem.is_available === false) {
    showError('This item is sold out.');
    return;
  }
  const current = cart.get(id);
  if (current) current.quantity += 1;
  else cart.set(id, { menu_item: { id, name, price }, quantity: 1 });
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
      <span class="flex-1 truncate">${escapeHtml(menu_item.name)} x ${quantity}</span>
      <span class="font-medium">$${subtotal.toFixed(2)}</span>
      <div class="flex items-center gap-0">
        <button type="button" data-id="${id}" class="qty-btn minus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">-</button>
        <span class="w-6 text-center text-sm">${quantity}</span>
        <button type="button" data-id="${id}" class="qty-btn plus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">+</button>
      </div>
    `;
    list.appendChild(li);
  });

  list.querySelectorAll('.qty-btn.minus').forEach((btn) => btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), -1)));
  list.querySelectorAll('.qty-btn.plus').forEach((btn) => btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), 1)));

  totalEl.textContent = `$${total.toFixed(2)}`;
  submitBtn.disabled = !selectedTableId;
}

function normalizeItemStatus(item) {
  const raw = String(item?.status || item?.batch_status || 'pending').toLowerCase();
  if (raw === 'ready' || raw === 'completed' || raw === 'served') return 'Ready';
  return 'Pending';
}

function normalizeTrackingStatus(raw) {
  const value = String(raw || '').toLowerCase();
  return value === 'served' ? 'served' : 'pending';
}

function statusBadgeHtml(status) {
  const s = normalizeTrackingStatus(status);
  if (s === 'served') {
    return '<span class="text-xs px-2 py-0.5 rounded bg-emerald-500 text-white">Served</span>';
  }
  return '<span class="text-xs px-2 py-0.5 rounded bg-amber-500 text-white">Ordered</span>';
}

function openDetailsSidebar() {
  const backdrop = document.getElementById('waiter-table-details-backdrop');
  const sidebar = document.getElementById('waiter-table-details-sidebar');
  if (backdrop) backdrop.classList.remove('hidden');
  if (sidebar) sidebar.classList.remove('translate-x-full');
  tableDetailsOpen = true;
}

function closeDetailsSidebar() {
  const backdrop = document.getElementById('waiter-table-details-backdrop');
  const sidebar = document.getElementById('waiter-table-details-sidebar');
  if (backdrop) backdrop.classList.add('hidden');
  if (sidebar) sidebar.classList.add('translate-x-full');
  tableDetailsOpen = false;
  tableDetailsOrderId = null;
  tableDetailsTableName = '';
}

function renderTableDetailsItems(orderDetails) {
  const content = document.getElementById('waiter-table-details-content');
  if (!content) return;
  const items = orderDetails?.items || [];
  if (!items.length) {
    content.innerHTML = '<p class="text-slate-500">No ordered items found.</p>';
    return;
  }

  content.innerHTML = items.map((item) => {
    const status = normalizeTrackingStatus(item.item_status);
    return `
      <div class="border border-slate-200 rounded-md p-3">
        <div class="flex items-center justify-between gap-2 mb-2">
          <div>
            <p class="font-medium text-slate-800">${escapeHtml(item.menu_item_name)} x ${item.quantity}</p>
            <p class="text-xs text-slate-500">Waiter: ${escapeHtml(item.waiter_name || '-')}</p>
          </div>
          ${statusBadgeHtml(status)}
        </div>
        ${
          status === 'pending'
            ? `<button type="button" data-mark-served-item-id="${item.id}" class="text-xs px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700">✓ Mark as Served</button>`
            : ''
        }
      </div>
    `;
  }).join('');

  content.querySelectorAll('[data-mark-served-item-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = Number(btn.getAttribute('data-mark-served-item-id'));
      if (!tableDetailsOrderId || !itemId) return;
      btn.disabled = true;
      try {
        await markOrderItemServed(tableDetailsOrderId, itemId);
        const refreshed = await fetchOrderDetails(tableDetailsOrderId);
        renderTableDetailsItems(refreshed);
        showSuccess('Item marked as served.');
        queueRefresh();
      } catch (err) {
        console.error(err);
        showError(err.message || 'Failed to mark item served');
        btn.disabled = false;
      }
    });
  });
}

async function openTableDetailsSidebar(tableId, tableName) {
  const subtitle = document.getElementById('waiter-table-details-subtitle');
  const content = document.getElementById('waiter-table-details-content');
  if (subtitle) subtitle.textContent = `Table ${tableName}`;
  if (content) content.innerHTML = '<p class="text-slate-500">Loading order details...</p>';
  openDetailsSidebar();

  const activeOrder = await fetchActiveOrderByTable(tableId);
  if (!activeOrder || !activeOrder.id) {
    if (content) content.innerHTML = '<p class="text-slate-500">No active order found for this table.</p>';
    return;
  }

  tableDetailsOrderId = activeOrder.id;
  tableDetailsTableName = tableName;
  const details = await fetchOrderDetails(activeOrder.id);
  renderTableDetailsItems(details);
}

function renderMyTables(orders) {
  const user = getCurrentUser();
  const target = document.getElementById('my-tables');
  if (!target) return;
  if (!orders?.length || !user?.username) {
    target.innerHTML = '<p class="text-slate-500">No active tables yet.</p>';
    return;
  }

  const myTablesMap = new Map();
  for (const order of orders) {
    const mine = (order.items || []).filter((item) => item.waiter_name === user.username);
    if (!mine.length) continue;
    const key = String(order.table_id ?? order.table_number ?? order.id);
    const existing = myTablesMap.get(key) || {
      tableLabel: `Table ${tableNameById(order.table_id, order.table_number ?? order.id)}`,
      pending: 0,
      ready: 0,
      items: [],
    };
    mine.forEach((item) => {
      const status = normalizeItemStatus(item);
      if (status === 'Ready') existing.ready += 1;
      else existing.pending += 1;
      existing.items.push({
        name: item.menu_item_name,
        quantity: item.quantity,
        status,
      });
    });
    myTablesMap.set(key, existing);
  }

  const cards = Array.from(myTablesMap.values());
  if (!cards.length) {
    target.innerHTML = '<p class="text-slate-500">No active tables yet.</p>';
    return;
  }

  target.innerHTML = cards.map((card) => `
    <div class="border border-slate-200 rounded-md p-3">
      <div class="flex items-center justify-between mb-2">
        <h3 class="font-semibold text-slate-800">${escapeHtml(card.tableLabel)}</h3>
        <div class="text-xs">
          <span class="px-2 py-1 rounded bg-amber-100 text-amber-800 mr-1">Pending: ${card.pending}</span>
          <span class="px-2 py-1 rounded bg-emerald-100 text-emerald-800">Ready: ${card.ready}</span>
        </div>
      </div>
      <ul class="space-y-1 text-sm">
        ${card.items.map((item) => `
          <li class="flex items-center justify-between">
            <span>${escapeHtml(item.name)} x ${item.quantity}</span>
            <span class="text-xs px-2 py-0.5 rounded ${item.status === 'Ready' ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'}">${item.status}</span>
          </li>
        `).join('')}
      </ul>
    </div>
  `).join('');
}

async function submitOrder(tableId, items) {
  return fetchJson(`${API_BASE}/api/orders/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ table_id: tableId, items }),
  });
}

function bindSubmitOrder() {
  const submitBtn = document.getElementById('submit-order');
  if (!submitBtn) return;
  submitBtn.addEventListener('click', async () => {
    if (!selectedTableId) {
      showError('Please select a table first.');
      return;
    }
    if (cart.size === 0) {
      showError('Cart is empty.');
      return;
    }
    const items = [];
    cart.forEach(({ menu_item, quantity }) => items.push({ menu_item_id: menu_item.id, quantity }));
    submitBtn.disabled = true;
    try {
      const data = await submitOrder(selectedTableId, items);
      if (!data) return;
      cart.clear();
      renderCart();
      showSuccess(data.message || 'Order submitted.');
      if (AUTO_LOGOUT_AFTER_SUBMIT) {
        setTimeout(() => autoLogoutToPin(), 650);
      }
    } catch (err) {
      console.error(err);
      showError(err.message || 'Failed to submit order');
      submitBtn.disabled = false;
    }
  });
}

async function refreshTableStatus() {
  const data = await fetchTablesStatus();
  if (!data) return;
  zones = data;
  if (!zones.length) {
    activeZoneId = null;
    selectedTableId = null;
  } else {
    if (!activeZoneId || !zones.some((z) => z.id === activeZoneId)) activeZoneId = zones[0].id;
    const allTableIds = zones.flatMap((z) => z.tables || []).map((t) => t.id);
    if (selectedTableId && !allTableIds.includes(selectedTableId)) selectedTableId = null;
  }
  renderZoneTabs();
  renderTableCards();

  // Optional preselect via /waiter?table_id=123 (used by Table Dashboard redirect).
  const paramTableId = Number(new URLSearchParams(window.location.search).get('table_id') || 0);
  if (paramTableId && zones.flatMap((z) => z.tables || []).some((t) => t.id === paramTableId)) {
    selectedTableId = paramTableId;
    const selectedZone = zones.find((z) => (z.tables || []).some((t) => t.id === paramTableId));
    if (selectedZone) activeZoneId = selectedZone.id;
    renderZoneTabs();
    renderTableCards();
  }
}

async function refreshMyTables() {
  const orders = await fetchActiveOrdersForMyTables();
  if (!orders) return;
  renderMyTables(orders);
}

function queueRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    try {
      await Promise.all([refreshTableStatus(), refreshMyTables()]);
    } catch (err) {
      console.error('Refresh error:', err);
    }
  }, 200);
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);
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
            is_available: item.is_available !== false,
          });
          renderCategoryTabs();
          renderMenu();
        }
        return;
      }
      if (msg.event === 'menu_item_availability_toggled' && msg.data) {
        const item = msg.data;
        const idx = menuItems.findIndex((m) => m.id === item.id);
        if (idx >= 0) {
          menuItems[idx] = {
            ...menuItems[idx],
            is_available: item.is_available !== false,
          };
          renderMenu();
        }
        return;
      }
      if (msg.event === 'menu_item_deleted' && msg.data) {
        const itemId = Number(msg.data.id);
        if (!itemId) return;
        menuItems = menuItems.filter((m) => m.id !== itemId);
        if (cart.has(itemId)) {
          cart.delete(itemId);
          renderCart();
        }
        renderCategoryTabs();
        renderMenu();
        return;
      }
      if (
        msg.event === 'new_order_batch' ||
        msg.event === 'order_updated' ||
        msg.event === 'batch_completed' ||
        msg.event === 'table_status_changed' ||
        msg.event === 'table_grid_updated'
      ) {
        queueRefresh();
        if (tableDetailsOpen && tableDetailsOrderId) {
          fetchOrderDetails(tableDetailsOrderId)
            .then((details) => {
              if (details) renderTableDetailsItems(details);
            })
            .catch(() => {});
        }
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 3000);
  ws.onerror = () => {};
}

if (window.auth && window.auth.getToken()) {
  (async function init() {
    bindSubmitOrder();
    const closeBtn = document.getElementById('waiter-table-details-close');
    const backdrop = document.getElementById('waiter-table-details-backdrop');
    if (closeBtn) closeBtn.addEventListener('click', closeDetailsSidebar);
    if (backdrop) backdrop.addEventListener('click', closeDetailsSidebar);
    connectWebSocket();
    try {
      const [items, cats] = await Promise.all([fetchMenuItems(), fetchCategories()]);
      menuItems = items || [];
      categories = cats || [];
      activeCategoryId = null;
      renderCategoryTabs();
      renderMenu();
      await Promise.all([refreshTableStatus(), refreshMyTables()]);
    } catch (err) {
      console.error(err);
      document.getElementById('menu-grid').innerHTML = '<p class="col-span-full text-red-600">Error loading waiter screen.</p>';
    }
  })();
}
