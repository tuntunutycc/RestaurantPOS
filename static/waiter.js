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
let modifierModalItem = null;

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

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeSelectedModifiers(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((m) => ({
      name: String(m?.name || '').trim(),
      price: toNumber(m?.price, 0),
      group: m?.group ? String(m.group) : null,
    }))
    .filter((m) => m.name);
}

function modifiersTotal(selectedModifiers) {
  return normalizeSelectedModifiers(selectedModifiers).reduce((sum, m) => sum + toNumber(m.price, 0), 0);
}

function buildCartLineKey(menuItemId, selectedModifiers, specialInstructions) {
  const normalized = normalizeSelectedModifiers(selectedModifiers)
    .map((m) => ({ name: m.name, price: Number(m.price.toFixed(2)), group: m.group || null }))
    .sort((a, b) => `${a.group || ''}|${a.name}`.localeCompare(`${b.group || ''}|${b.name}`));
  const note = String(specialInstructions || '').trim();
  return `${menuItemId}::${JSON.stringify(normalized)}::${note}`;
}

function getMenuItemById(id) {
  return menuItems.find((m) => m.id === id) || null;
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
      <div data-menu-card-id="${m.id}" class="menu-item-card cursor-pointer text-left p-0 bg-white rounded-lg shadow border border-slate-200 overflow-hidden ${cardStateClass}">
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
  grid.querySelectorAll('[data-menu-card-id]').forEach((card) => {
    card.addEventListener('click', () => {
      const itemId = Number(card.getAttribute('data-menu-card-id'));
      const menuItem = getMenuItemById(itemId);
      if (!menuItem) return;
      openModifierModal(menuItem);
    });
  });
  grid.querySelectorAll('.add-to-cart-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const itemId = Number(btn.dataset.id);
      const menuItem = getMenuItemById(itemId);
      if (!menuItem) return;
      openModifierModal(menuItem);
    });
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

function addToCart(menuItem, selectedModifiers = [], specialInstructions = '') {
  const id = Number(menuItem?.id);
  if (!id) return;
  const normalizedModifiers = normalizeSelectedModifiers(selectedModifiers);
  const note = String(specialInstructions || '').trim();
  const unitPrice = toNumber(menuItem.price, 0) + modifiersTotal(normalizedModifiers);
  const key = buildCartLineKey(id, normalizedModifiers, note);
  const existing = cart.get(key);
  if (existing) {
    existing.quantity += 1;
  } else {
    cart.set(key, {
      menu_item: { id, name: menuItem.name, price: toNumber(menuItem.price, 0) },
      selected_modifiers: normalizedModifiers,
      special_instructions: note || null,
      unit_price: unitPrice,
      quantity: 1,
    });
  }
  renderCart();
}

function addSimpleItem(menuItem) {
  if (menuItem && menuItem.is_available === false) {
    showError('This item is sold out.');
    return;
  }
  addToCart(menuItem, [], '');
}

function updateCartQuantity(lineKey, delta) {
  const item = cart.get(lineKey);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) cart.delete(lineKey);
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
  cart.forEach(({ menu_item, quantity, selected_modifiers, special_instructions, unit_price }, lineKey) => {
    const subtotal = unit_price * quantity;
    total += subtotal;
    const modifiersHtml = (selected_modifiers || []).length
      ? `<div class="text-xs text-slate-500 mt-0.5">${(selected_modifiers || []).map((m) => `+ ${escapeHtml(m.name)}${toNumber(m.price, 0) ? ` ($${toNumber(m.price, 0).toFixed(2)})` : ''}`).join(', ')}</div>`
      : '';
    const noteHtml = special_instructions
      ? `<div class="text-xs text-slate-500 italic mt-0.5">${escapeHtml(special_instructions)}</div>`
      : '';
    const li = document.createElement('li');
    li.className = 'flex items-center justify-between gap-2';
    li.innerHTML = `
      <div class="flex-1 min-w-0">
        <span class="truncate block">${escapeHtml(menu_item.name)} x ${quantity}</span>
        ${modifiersHtml}
        ${noteHtml}
      </div>
      <span class="font-medium">$${subtotal.toFixed(2)}</span>
      <div class="flex items-center gap-0">
        <button type="button" data-key="${escapeAttr(lineKey)}" class="qty-btn minus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">-</button>
        <span class="w-6 text-center text-sm">${quantity}</span>
        <button type="button" data-key="${escapeAttr(lineKey)}" class="qty-btn plus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">+</button>
      </div>
    `;
    list.appendChild(li);
  });

  list.querySelectorAll('.qty-btn.minus').forEach((btn) => btn.addEventListener('click', () => updateCartQuantity(btn.dataset.key, -1)));
  list.querySelectorAll('.qty-btn.plus').forEach((btn) => btn.addEventListener('click', () => updateCartQuantity(btn.dataset.key, 1)));

  totalEl.textContent = `$${total.toFixed(2)}`;
  submitBtn.disabled = !selectedTableId;
}

function closeModifierModal() {
  const backdrop = document.getElementById('modifier-modal-backdrop');
  const modal = document.getElementById('modifier-modal');
  if (backdrop) backdrop.classList.add('hidden');
  if (modal) modal.classList.add('hidden');
  modifierModalItem = null;
}

function getSelectedModifiersFromModal() {
  const selected = [];
  document.querySelectorAll('[data-modifier-option]').forEach((input) => {
    if (!input.checked) return;
    selected.push({
      name: String(input.getAttribute('data-option-name') || ''),
      price: toNumber(input.getAttribute('data-option-price'), 0),
      group: String(input.getAttribute('data-group-name') || '') || null,
    });
  });
  return normalizeSelectedModifiers(selected);
}

function updateModifierModalAddButton() {
  const addBtn = document.getElementById('modifier-modal-add');
  if (!addBtn || !modifierModalItem) return;
  const total = toNumber(modifierModalItem.price, 0) + modifiersTotal(getSelectedModifiersFromModal());
  addBtn.textContent = `Add to Cart ($${total.toFixed(2)})`;
}

function validateRequiredModifierGroups() {
  if (!modifierModalItem) return true;
  const groups = Array.isArray(modifierModalItem.modifiers_config) ? modifierModalItem.modifiers_config : [];
  for (let i = 0; i < groups.length; i += 1) {
    const group = groups[i];
    if (!group || !group.is_required) continue;
    const picked = document.querySelector(`input[name="mod-group-${i}"]:checked`);
    if (!picked) {
      showError(`Please choose one option for "${group.group || 'Required'}".`);
      return false;
    }
  }
  return true;
}

function openModifierModal(menuItem) {
  if (!menuItem || menuItem.is_available === false) {
    showError('This item is sold out.');
    return;
  }
  modifierModalItem = menuItem;
  const title = document.getElementById('modifier-modal-title');
  const base = document.getElementById('modifier-modal-base-price');
  const groupsEl = document.getElementById('modifier-modal-groups');
  const noteEl = document.getElementById('modifier-special-instructions');
  const backdrop = document.getElementById('modifier-modal-backdrop');
  const modal = document.getElementById('modifier-modal');
  if (!title || !base || !groupsEl || !noteEl || !backdrop || !modal) {
    addSimpleItem(menuItem);
    return;
  }
  title.textContent = menuItem.name || 'Customize Item';
  base.textContent = `Base: $${toNumber(menuItem.price, 0).toFixed(2)}`;
  noteEl.value = '';

  const groups = Array.isArray(menuItem.modifiers_config) ? menuItem.modifiers_config : [];
  if (!groups.length) {
    groupsEl.innerHTML = '<p class="text-sm text-slate-500">No modifiers for this item.</p>';
  } else {
    groupsEl.innerHTML = groups.map((group, i) => {
      const required = !!group?.is_required;
      const options = Array.isArray(group?.options) ? group.options : [];
      return `
        <div class="border border-slate-200 rounded-md p-3">
          <p class="text-sm font-semibold text-slate-800 mb-2">
            ${escapeHtml(group?.group || `Modifiers ${i + 1}`)}
            ${required ? '<span class="text-red-600">*</span>' : '<span class="text-slate-400 text-xs">(optional)</span>'}
          </p>
          <div class="space-y-1.5">
            ${options.map((opt) => `
              <label class="flex items-center justify-between gap-2 text-sm">
                <span class="flex items-center gap-2">
                  <input
                    type="${required ? 'radio' : 'checkbox'}"
                    name="mod-group-${i}"
                    data-modifier-option="1"
                    data-group-name="${escapeAttr(group?.group || '')}"
                    data-option-name="${escapeAttr(opt?.name || '')}"
                    data-option-price="${toNumber(opt?.price, 0)}"
                    class="rounded border-slate-300"
                  />
                  <span>${escapeHtml(opt?.name || 'Option')}</span>
                </span>
                <span class="text-slate-600">+${toNumber(opt?.price, 0).toFixed(2)}</span>
              </label>
            `).join('')}
          </div>
        </div>
      `;
    }).join('');
  }

  groupsEl.querySelectorAll('[data-modifier-option]').forEach((input) => {
    input.addEventListener('change', updateModifierModalAddButton);
  });

  updateModifierModalAddButton();
  backdrop.classList.remove('hidden');
  modal.classList.remove('hidden');
}

function bindModifierModal() {
  const closeBtn = document.getElementById('modifier-modal-close');
  const cancelBtn = document.getElementById('modifier-modal-cancel');
  const addBtn = document.getElementById('modifier-modal-add');
  const backdrop = document.getElementById('modifier-modal-backdrop');
  const noteEl = document.getElementById('modifier-special-instructions');

  if (closeBtn) closeBtn.addEventListener('click', closeModifierModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModifierModal);
  if (backdrop) backdrop.addEventListener('click', closeModifierModal);
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      if (!modifierModalItem) return;
      if (!validateRequiredModifierGroups()) return;
      const selectedModifiers = getSelectedModifiersFromModal();
      const specialInstructions = noteEl ? noteEl.value : '';
      addToCart(modifierModalItem, selectedModifiers, specialInstructions);
      closeModifierModal();
    });
  }
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
    cart.forEach(({ menu_item, quantity, selected_modifiers, special_instructions }) => {
      items.push({
        menu_item_id: menu_item.id,
        quantity,
        selected_modifiers: selected_modifiers || [],
        special_instructions: special_instructions || null,
      });
    });
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
            modifiers_config: Array.isArray(item.modifiers_config) ? item.modifiers_config : [],
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
        let changed = false;
        for (const [key, value] of cart.entries()) {
          if (Number(value?.menu_item?.id) === itemId) {
            cart.delete(key);
            changed = true;
          }
        }
        if (changed) {
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
    bindModifierModal();
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
