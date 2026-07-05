const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['waiter', 'admin', 'root', 'cashier'])) return;
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
let currentView = 'tables'; // 'tables' | 'takeaway'
let selectedTableId = null;
let activeOrderContext = null;
let takeawayOrders = [];
let refreshTimer = null;
let tableDetailsOpen = false;
let tableDetailsOrderId = null;
let tableDetailsTableName = '';
let tableDetailsOrderContext = null;
let modifierModalItem = null;
let takeawayPromptResolver = null;
let takeawayOrdersById = new Map();
let takeawayPollTimer = null;

function t(key, fallback) {
  return window.i18n?.t?.(key) || fallback || key;
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

/** Fallback when API omits waiter display string (spec: tech-stack deleted-user label). */
function displayOrderWaiterLine(name) {
  const s = name != null && String(name).trim() !== '' ? String(name).trim() : '';
  return s || t('deleted_user', '[Deleted User]');
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

function getEffectiveBasePrice(menuItem) {
  const discount = toNumber(menuItem?.discount_price, 0);
  if (discount > 0) return discount;
  return toNumber(menuItem?.price, 0);
}

function getMenuPriceHtml(menuItem) {
  const normal = toNumber(menuItem?.price, 0);
  const discount = toNumber(menuItem?.discount_price, 0);
  if (discount > 0) {
    return `
      <div class="flex items-center gap-2 mt-0.5">
        <span class="line-through text-gray-500 text-xs">${formatMoney(normal)}</span>
        <span class="text-red-500 font-bold text-sm">${formatMoney(discount)}</span>
      </div>
    `;
  }
  return `<span class="text-sm text-slate-600 block">${formatMoney(normal)}</span>`;
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
  else if (window.CustomDialog?.alert) window.CustomDialog.alert(t('error', 'Error'), message);
  else console.warn(message);
}

function showSuccess(message) {
  if (window.toast?.success) window.toast.success(message);
  else if (window.CustomDialog?.alert) window.CustomDialog.alert(t('success', 'Success'), message);
  else console.info(message);
}

async function showSelectContextAlert() {
  const title = t('attention', 'Attention');
  const message = t('select_context_first', 'Please select a Table or create a Takeaway order first.');
  if (window.CustomDialog?.alert) {
    await window.CustomDialog.alert(title, message);
    return;
  }
  showError(message);
}

function showNativeConfirmModal(title, message) {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'fixed inset-0 bg-black/40 z-[10000] flex items-center justify-center p-4';

    const modal = document.createElement('div');
    modal.className = 'w-full max-w-md bg-white rounded-lg shadow-2xl overflow-hidden';
    modal.innerHTML = `
      <div class="px-4 py-3 border-b border-slate-200">
        <h3 class="text-lg font-semibold text-slate-800">${escapeHtml(title)}</h3>
      </div>
      <div class="px-4 py-4 text-sm text-slate-700">
        ${escapeHtml(message)}
      </div>
      <div class="px-4 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-2">
        <button type="button" data-confirm-cancel class="px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-100">${escapeHtml(t('cancel', 'Cancel'))}</button>
        <button type="button" data-confirm-ok class="px-4 py-2 rounded bg-rose-600 text-white hover:bg-rose-700">${escapeHtml(t('confirm', 'Confirm'))}</button>
      </div>
    `;

    function cleanup(result) {
      backdrop.remove();
      resolve(result);
    }

    modal.querySelector('[data-confirm-cancel]')?.addEventListener('click', () => cleanup(false));
    modal.querySelector('[data-confirm-ok]')?.addEventListener('click', () => cleanup(true));
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) cleanup(false);
    });
    document.addEventListener(
      'keydown',
      function onKeyDown(e) {
        if (e.key === 'Escape') {
          document.removeEventListener('keydown', onKeyDown);
          cleanup(false);
        }
      },
      { once: true }
    );

    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
  });
}

async function confirmAction(title, message) {
  if (window.CustomDialog?.confirm) {
    const result = await window.CustomDialog.confirm(title, message);
    return isConfirmAccepted(result);
  }
  return showNativeConfirmModal(title, message);
}

async function ensureActiveOrderContextSelected() {
  if (activeOrderContext) return true;
  await showSelectContextAlert();
  return false;
}

function updateCartUIContext() {
  const titleEl = document.getElementById('cart-context-title');
  const clearBtn = document.getElementById('cart-clear-context');
  const submitBtn = document.getElementById('submit-order');
  if (titleEl) {
    titleEl.textContent = activeOrderContext?.title || t('no_active_order', 'No Active Order');
  }
  if (clearBtn) {
    clearBtn.disabled = !activeOrderContext && cart.size === 0;
  }
  if (submitBtn) {
    submitBtn.disabled = !activeOrderContext || cart.size === 0;
  }
}

function setActiveOrderContext(nextContext) {
  activeOrderContext = nextContext ? { ...nextContext } : null;
  if (!activeOrderContext) {
    selectedTableId = null;
  } else if (activeOrderContext.type === 'dine_in') {
    selectedTableId = activeOrderContext.table_id ?? null;
  } else {
    selectedTableId = null;
  }
  updateCartUIContext();
}

function focusCartSidebar() {
  const sidebar = document.getElementById('cart-sidebar');
  if (sidebar) {
    sidebar.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  const submitBtn = document.getElementById('submit-order');
  if (submitBtn) submitBtn.focus();
}

function clearCartAndContext() {
  closeDetailsSidebar();
  cart.clear();
  setActiveOrderContext(null);
  renderZoneTabs();
  updateOrderSourceView();
  renderSelectedTableLabel();
  renderCart();
  if (window.toast?.info) window.toast.info(t('clear_context', 'Cancel / Clear Context'));
}

function autoLogoutToPin() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem('pos_unauthorized');
  window.location.href = '/pin-login';
}

function isCashierRole() {
  return String(window.auth?.getUser?.()?.role || '').toLowerCase() === 'cashier';
}

const COUNTER_DASHBOARD_ROLES = new Set(['cashier', 'admin', 'root']);

function redirectCashierToBillingTab() {
  window.location.href = '/counter?tab=cashier';
}

function bindBackToDashboardNav() {
  const btn = document.getElementById('btn-back-to-dashboard');
  if (!btn) return;

  const role = String(window.auth?.getUser?.()?.role || '').toLowerCase();
  if (COUNTER_DASHBOARD_ROLES.has(role)) {
    btn.classList.remove('hidden');
    btn.textContent =
      role === 'cashier'
        ? t('back_to_cashier', '🔙 Back to Cashier')
        : t('back_to_dashboard', 'Dashboard');
  } else {
    btn.classList.add('hidden');
  }

  btn.addEventListener('click', () => {
    window.location.href = role === 'cashier' ? '/counter?tab=cashier' : '/counter';
  });
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

async function fetchActiveTakeawayOrders() {
  return fetchJson(`${API_BASE}/api/orders/active-takeaways`);
}

async function fetchActiveOrderByTable(tableId) {
  return fetchJson(`${API_BASE}/api/orders/active-by-table/${tableId}`);
}

async function fetchOrderDetails(orderId) {
  return fetchJson(`${API_BASE}/api/orders/${orderId}/details`);
}

async function updateOrderItemStatus(orderId, itemId, status) {
  const safeOrderId = Number(orderId);
  const safeItemId = Number(itemId);
  const normalizedStatus = String(status || '').trim().toLowerCase();
  if (!Number.isFinite(safeOrderId) || safeOrderId <= 0 || !Number.isFinite(safeItemId) || safeItemId <= 0) {
    throw new Error(`Invalid order/item id. orderId=${orderId}, itemId=${itemId}`);
  }
  const url = `${API_BASE}/api/orders/${safeOrderId}/items/${safeItemId}/status`;
  try {
    return await fetchJson(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: normalizedStatus }),
    });
  } catch (err) {
    console.error('[Waiter][updateOrderItemStatus] failed', {
      url,
      orderId: safeOrderId,
      itemId: safeItemId,
      status: normalizedStatus,
      error: err,
    });
    throw err;
  }
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
    `<button type="button" data-category-id="" class="category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeCategoryId === null ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(t('all', 'All'))}</button>`,
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
    const promotedBadge = m.is_promoted === true
      ? '<span class="absolute top-2 left-2 text-[11px] font-bold px-2 py-0.5 rounded bg-amber-500 text-white shadow">★ Promo</span>'
      : '';
    const cardStateClass = available ? 'hover:bg-blue-50' : 'opacity-50 grayscale pointer-events-none';
    const promoBorder = m.is_promoted === true ? 'border-amber-400 ring-1 ring-amber-200' : 'border-slate-200';
    return `
      <div data-menu-card-id="${m.id}" class="menu-item-card cursor-pointer text-left p-0 bg-white rounded-lg shadow border overflow-hidden ${cardStateClass} ${promoBorder}">
        <div class="relative">
          ${imgHtml}
          ${promotedBadge}
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
          ${getMenuPriceHtml(m)}
        </div>
      </div>`;
  }).join('');
  grid.querySelectorAll('[data-menu-card-id]').forEach((card) => {
    card.addEventListener('click', async () => {
      if (!(await ensureActiveOrderContextSelected())) return;
      const itemId = Number(card.getAttribute('data-menu-card-id'));
      const menuItem = getMenuItemById(itemId);
      if (!menuItem) return;
      openModifierModal(menuItem);
    });
  });
  grid.querySelectorAll('.add-to-cart-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!(await ensureActiveOrderContextSelected())) return;
      const itemId = Number(btn.dataset.id);
      const menuItem = getMenuItemById(itemId);
      if (!menuItem) return;
      openModifierModal(menuItem);
    });
  });
}

function setActiveZone(zoneId) {
  currentView = 'tables';
  activeZoneId = zoneId;
  renderZoneTabs();
  updateOrderSourceView();
}

function renderZoneTabs() {
  const container = document.getElementById('zone-tabs');
  if (!container) return;
  const zoneButtons = zones.map((z) => (
    `<button type="button" data-zone-id="${z.id}" class="zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${currentView === 'tables' && activeZoneId === z.id ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(z.name)}</button>`
  ));
  const takeawayButton = `<button type="button" data-zone-view="takeaway" class="zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${currentView === 'takeaway' ? 'bg-orange-500 text-white' : 'bg-orange-100 text-orange-800 hover:bg-orange-200'}">🛍️ ${escapeHtml(t('takeaway', 'Takeaway'))}</button>`;
  container.innerHTML = [...zoneButtons, takeawayButton].join('');
  container.querySelectorAll('.zone-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-zone-view');
      if (view === 'takeaway') {
        currentView = 'takeaway';
        renderZoneTabs();
        updateOrderSourceView();
        return;
      }
      setActiveZone(Number(btn.dataset.zoneId));
    });
  });
}

function updateOrderSourceView() {
  const tableCards = document.getElementById('table-cards');
  const takeawayView = document.getElementById('takeaway-view');
  const showTakeaway = currentView === 'takeaway';
  if (tableCards) tableCards.classList.toggle('hidden', showTakeaway);
  if (takeawayView) takeawayView.classList.toggle('hidden', !showTakeaway);
  if (showTakeaway) renderTakeawayOrdersList(takeawayOrders);
  else renderTableCards();
}

function getActiveZoneTables() {
  const zone = zones.find((z) => z.id === activeZoneId);
  return zone?.tables || [];
}

function renderSelectedTableLabel() {
  const label = document.getElementById('selected-table-label');
  if (!label) return;
  if (!activeOrderContext) {
    label.innerHTML = `${escapeHtml(t('selected', 'Selected'))}: <span class="font-medium">${escapeHtml(t('none', 'None'))}</span>`;
    return;
  }
  if (activeOrderContext.type === 'takeaway') {
    const customer = String(activeOrderContext.customer_name || '').trim() || t('guest', 'Guest');
    label.innerHTML = `${escapeHtml(t('selected', 'Selected'))}: <span class="inline-flex items-center px-2 py-1 rounded bg-orange-100 text-orange-700 font-medium">${escapeHtml(t('takeaway', 'Takeaway'))} - ${escapeHtml(t('customer', 'Customer'))}: ${escapeHtml(customer)}</span>`;
    return;
  }
  const selected = zones.flatMap((z) => z.tables || []).find((t) => t.id === activeOrderContext.table_id);
  label.innerHTML = `${escapeHtml(t('selected', 'Selected'))}: <span class="font-medium">${selected ? escapeHtml(tableLabel(selected)) : escapeHtml(t('none', 'None'))}</span>`;
}

function renderTableCards() {
  const container = document.getElementById('table-cards');
  if (!container) return;
  if (currentView !== 'tables') {
    renderSelectedTableLabel();
    renderCart();
    return;
  }
  const tables = getActiveZoneTables();
  if (!tables.length) {
    container.innerHTML = `<p class="col-span-full text-slate-500">${escapeHtml(t('no_tables_in_zone', 'No tables in this zone.'))}</p>`;
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
      currentView = 'tables';
      selectedTableId = tableId;
      renderTableCards();
      renderSelectedTableLabel();
      renderCart();
      if (isOccupied) {
        openTableDetailsSidebar(tableId, tableName).catch((err) => {
          console.error(err);
          showError(err.message || t('load_failed', 'Load Failed'));
        });
      } else {
        setActiveOrderContext({
          type: 'dine_in',
          table_id: tableId,
          customer_name: null,
          title: `Table ${tableName}`,
        });
        renderSelectedTableLabel();
        renderCart();
        focusCartSidebar();
      }
    });
  });
  renderSelectedTableLabel();
  renderCart();
}

async function openOrderDetails(options) {
  const {
    orderId,
    orderType = 'dine_in',
    tableId = null,
    tableName = '',
    customerName = '',
    initialOrderData = null,
  } = options || {};
  if (!orderId) return;
  const subtitle = document.getElementById('waiter-table-details-subtitle');
  const content = document.getElementById('waiter-table-details-content');
  const normalizedType = String(orderType || 'dine_in').toLowerCase();
  const customer = String(customerName || '').trim() || t('walk_in', 'Walk-in');

  if (subtitle) {
    subtitle.textContent = normalizedType === 'takeaway'
      ? `${t('takeaway', 'Takeaway')} ${t('order', 'Order')} - ${t('customer', 'Customer')}: ${customer}`
      : `Table ${tableName}`;
  }
  if (content) content.innerHTML = `<p class="text-slate-500">${escapeHtml(t('loading_order_details', 'Loading order details...'))}</p>`;

  tableDetailsOrderId = Number(orderId);
  tableDetailsTableName = normalizedType === 'takeaway' ? `Takeaway ${customer}` : tableName;
  tableDetailsOrderContext = {
    type: normalizedType === 'takeaway' ? 'takeaway' : 'dine_in',
    table_id: normalizedType === 'takeaway' ? null : (tableId ?? initialOrderData?.table_id ?? null),
    customer_name: normalizedType === 'takeaway' ? customer : null,
    title: normalizedType === 'takeaway' ? `Takeaway: ${customer}` : `Table ${tableName}`,
    source_order_id: Number(orderId),
  };
  updateOrderDetailsAddMoreButton();
  openDetailsSidebar();

  if (initialOrderData && Array.isArray(initialOrderData.items)) {
    renderTableDetailsItems(initialOrderData);
    return;
  }
  const details = await fetchOrderDetails(orderId);
  if (details) {
    const detailsType = String(details.order_type || normalizedType).toLowerCase();
    const detailCustomer = String(details.customer_name || customer).trim() || 'Guest';
    const detailsTableId = details.table_id ?? tableId ?? null;
    const detailsTableLabel = detailsType === 'takeaway'
      ? `Takeaway: ${detailCustomer}`
      : `Table ${tableNameById(detailsTableId, tableName)}`;
    tableDetailsOrderContext = {
      type: detailsType === 'takeaway' ? 'takeaway' : 'dine_in',
      table_id: detailsType === 'takeaway' ? null : detailsTableId,
      customer_name: detailsType === 'takeaway' ? detailCustomer : null,
      title: detailsTableLabel,
      source_order_id: Number(orderId),
    };
    updateOrderDetailsAddMoreButton();
    renderTableDetailsItems(details);
  }
}

function renderTakeawayOrdersList(orders) {
  const container = document.getElementById('takeaway-orders-list');
  if (!container) return;
  const list = Array.isArray(orders) ? orders : [];
  takeawayOrdersById = new Map(list.map((order) => [Number(order.id), order]));

  Array.from(container.children).forEach((child) => {
    if (child.tagName === 'P' && !child.hasAttribute('data-takeaway-empty')) {
      child.remove();
    }
  });

  if (!container.dataset.takeawayClickBound) {
    container.dataset.takeawayClickBound = '1';
    container.addEventListener('click', (event) => {
      const newBtn = event.target.closest('[data-new-takeaway-order]');
      if (newBtn && container.contains(newBtn)) {
        startTakeawayOrder();
        return;
      }
      const orderBtn = event.target.closest('[data-takeaway-order-id]');
      if (!orderBtn || !container.contains(orderBtn)) return;
      const orderId = Number(orderBtn.getAttribute('data-takeaway-order-id'));
      const order = takeawayOrdersById.get(orderId);
      if (!order) return;
      const customer = String(order.customer_name || '').trim() || t('walk_in', 'Walk-in');
      openOrderDetails({
        orderId: order.id,
        orderType: 'takeaway',
        customerName: customer,
        initialOrderData: order,
      }).catch((err) => {
        console.error(err);
        showError(err.message || t('load_failed', 'Load Failed'));
      });
    });
  }

  let newCard = container.querySelector('[data-new-takeaway-order]');
  if (!newCard) {
    newCard = document.createElement('button');
    newCard.type = 'button';
    newCard.setAttribute('data-new-takeaway-order', '1');
    newCard.className = 'rounded-md p-3 text-left transition border-2 border-dashed border-orange-400 bg-orange-50 hover:bg-orange-100';
    newCard.innerHTML = `
      <div class="font-semibold text-orange-800">+ ${escapeHtml(t('create_new_takeaway_order', 'New Takeaway Order'))}</div>
      <div class="text-xs text-orange-700 mt-1">${escapeHtml(t('create_fresh_takeaway_cart', 'Create a fresh takeaway cart'))}</div>
    `;
    container.appendChild(newCard);
  } else if (container.firstElementChild !== newCard) {
    container.prepend(newCard);
  }

  const existingCards = new Map();
  container.querySelectorAll('[data-takeaway-order-id]').forEach((el) => {
    existingCards.set(Number(el.getAttribute('data-takeaway-order-id')), el);
  });

  const nextIds = new Set();
  for (const order of list) {
    const orderId = Number(order.id);
    if (!orderId) continue;
    nextIds.add(orderId);
    const customer = String(order.customer_name || '').trim() || t('walk_in', 'Walk-in');
    const items = Array.isArray(order.items) ? order.items : [];
    const pending = items.filter((i) => String(i.item_status || '').toLowerCase() !== 'served').length;
    const served = items.filter((i) => String(i.item_status || '').toLowerCase() === 'served').length;
    const signature = `${customer}|${toNumber(order.total_amount, 0).toFixed(2)}|${pending}|${served}`;
    let card = existingCards.get(orderId);
    if (!card) {
      card = document.createElement('button');
      card.type = 'button';
      card.setAttribute('data-takeaway-order-id', String(orderId));
      card.className = 'rounded-md p-3 text-left transition border-2 bg-orange-50 border-orange-300 hover:bg-orange-100';
      container.appendChild(card);
    }
    if (card.dataset.signature !== signature) {
      card.dataset.signature = signature;
      card.innerHTML = `
        <div class="font-semibold text-slate-800">${escapeHtml(t('takeaway', 'Takeaway'))} - ${escapeHtml(customer)}</div>
        <div class="text-xs text-slate-600 mt-1">Order #${orderId}</div>
        <div class="text-sm font-medium text-orange-700 mt-1">${formatMoney(toNumber(order.total_amount, 0))}</div>
        <div class="mt-2 flex gap-1 flex-wrap">
          <span class="text-[11px] px-2 py-0.5 rounded bg-amber-100 text-amber-800">${escapeHtml(t('pending', 'Pending'))}: ${pending}</span>
          <span class="text-[11px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">${escapeHtml(t('served', 'Served'))}: ${served}</span>
        </div>
      `;
    }
  }

  for (const [orderId, el] of existingCards.entries()) {
    if (!nextIds.has(orderId)) {
      el.remove();
    }
  }

  let emptyState = container.querySelector('[data-takeaway-empty]');
  if (!list.length) {
    if (!emptyState) {
      emptyState = document.createElement('p');
      emptyState.setAttribute('data-takeaway-empty', '1');
      emptyState.className = 'text-slate-500 text-sm';
      emptyState.textContent = t('no_active_takeaway_orders', 'No active takeaway orders.');
      container.appendChild(emptyState);
    }
  } else if (emptyState) {
    emptyState.remove();
  }
}

function setTakeawayContext(customerName = 'Guest') {
  const normalizedName = String(customerName || '').trim() || t('guest', 'Guest');
  setActiveOrderContext({
    type: 'takeaway',
    table_id: null,
    customer_name: normalizedName,
    title: `Takeaway: ${normalizedName}`,
  });
  currentView = 'takeaway';
  renderZoneTabs();
  updateOrderSourceView();
  renderSelectedTableLabel();
  renderCart();
  focusCartSidebar();
  if (window.toast?.info) window.toast.info(t('takeaway_mode_enabled', 'Takeaway order mode enabled.'));
}

function openTakeawayModal(initialName = 'Guest') {
  const backdrop = document.getElementById('takeaway-modal-backdrop');
  const modal = document.getElementById('takeaway-modal');
  const input = document.getElementById('takeaway-customer-name');
  return new Promise((resolve) => {
    if (!backdrop || !modal || !input) {
      resolve(String(initialName || t('guest', 'Guest')));
      return;
    }
    takeawayPromptResolver = resolve;
    input.value = String(initialName || t('guest', 'Guest'));
    backdrop.classList.remove('hidden');
    modal.classList.remove('hidden');
    setTimeout(() => {
      input.focus();
      input.select();
    }, 0);
  });
}

function bindTakeawayModal() {
  const backdrop = document.getElementById('takeaway-modal-backdrop');
  const closeBtn = document.getElementById('takeaway-modal-close');
  const cancelBtn = document.getElementById('takeaway-modal-cancel');
  const confirmBtn = document.getElementById('takeaway-modal-confirm');
  const input = document.getElementById('takeaway-customer-name');

  const resolveAndClose = (value) => {
    if (takeawayPromptResolver) {
      takeawayPromptResolver(value);
      takeawayPromptResolver = null;
    }
    const modalBackdrop = document.getElementById('takeaway-modal-backdrop');
    const modalEl = document.getElementById('takeaway-modal');
    if (modalBackdrop) modalBackdrop.classList.add('hidden');
    if (modalEl) modalEl.classList.add('hidden');
  };

  const submit = () => {
    const name = String(input?.value || '').trim() || 'Guest';
    resolveAndClose(name);
  };

  if (backdrop) backdrop.addEventListener('click', () => resolveAndClose(null));
  if (closeBtn) closeBtn.addEventListener('click', () => resolveAndClose(null));
  if (cancelBtn) cancelBtn.addEventListener('click', () => resolveAndClose(null));
  if (confirmBtn) confirmBtn.addEventListener('click', submit);
  if (input) {
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        submit();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        resolveAndClose(null);
      }
    });
  }
}

function normalizePromptResult(result) {
  if (result === null || result === undefined || result === false) return null;
  if (typeof result === 'string') return result;
  if (typeof result === 'object') {
    if ('cancelled' in result && result.cancelled) return null;
    if ('confirmed' in result && result.confirmed === false) return null;
    if (typeof result.value === 'string') return result.value;
    if (typeof result.text === 'string') return result.text;
  }
  return String(result);
}

async function startTakeawayOrder() {
  const defaultName = activeOrderContext?.type === 'takeaway'
    ? (activeOrderContext.customer_name || t('guest', 'Guest'))
    : t('guest', 'Guest');
  let name = null;
  if (window.CustomDialog?.prompt) {
    const result = await window.CustomDialog.prompt(
      t('new_takeaway_order', 'New Takeaway Order'),
      t('enter_customer_name_optional', 'Enter customer name (optional)'),
      t('guest', 'Guest'),
    );
    name = normalizePromptResult(result);
  } else {
    name = await openTakeawayModal(defaultName);
  }
  if (name === null) return;
  setTakeawayContext(name);
}

function addToCart(menuItem, selectedModifiers = [], specialInstructions = '') {
  const id = Number(menuItem?.id);
  if (!id) return;
  const normalizedModifiers = normalizeSelectedModifiers(selectedModifiers);
  const note = String(specialInstructions || '').trim();
  const unitPrice = getEffectiveBasePrice(menuItem) + modifiersTotal(normalizedModifiers);
  const key = buildCartLineKey(id, normalizedModifiers, note);
  const existing = cart.get(key);
  if (existing) {
    existing.quantity += 1;
  } else {
    cart.set(key, {
      menu_item: {
        id,
        name: menuItem.name,
        price: toNumber(menuItem.price, 0),
        discount_price: toNumber(menuItem.discount_price, 0) > 0 ? toNumber(menuItem.discount_price, 0) : null,
      },
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

  if (cart.size === 0) {
    list.innerHTML = `<li class="text-slate-500">${escapeHtml(t('cart_empty', 'Cart is empty'))}</li>`;
    totalEl.textContent = formatMoney(0);
    renderSelectedTableLabel();
    updateCartUIContext();
    return;
  }

  let total = 0;
  list.innerHTML = '';
  cart.forEach(({ menu_item, quantity, selected_modifiers, special_instructions, unit_price }, lineKey) => {
    const subtotal = unit_price * quantity;
    total += subtotal;
    const discountPrice = toNumber(menu_item?.discount_price, 0);
    const normalPrice = toNumber(menu_item?.price, 0);
    const priceHtml = discountPrice > 0
      ? `<div class="text-xs mt-0.5"><span class="line-through text-slate-400">${formatMoney(normalPrice)}</span> <span class="text-red-500 font-semibold">${formatMoney(discountPrice)}</span></div>`
      : '';
    const modifiersHtml = (selected_modifiers || []).length
      ? `<div class="text-xs text-slate-500 mt-0.5">${(selected_modifiers || []).map((m) => `+ ${escapeHtml(m.name)}${toNumber(m.price, 0) ? ` (${formatMoney(toNumber(m.price, 0))})` : ''}`).join(', ')}</div>`
      : '';
    const noteHtml = special_instructions
      ? `<div class="text-xs text-slate-500 italic mt-0.5">${escapeHtml(special_instructions)}</div>`
      : '';
    const li = document.createElement('li');
    li.className = 'flex items-center justify-between gap-2';
    li.innerHTML = `
      <div class="flex-1 min-w-0">
        <span class="truncate block">${escapeHtml(menu_item.name)} x ${quantity}</span>
        ${priceHtml}
        ${modifiersHtml}
        ${noteHtml}
      </div>
      <span class="font-medium">${formatMoney(subtotal)}</span>
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

  totalEl.textContent = formatMoney(total);
  renderSelectedTableLabel();
  updateCartUIContext();
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
  const total = getEffectiveBasePrice(modifierModalItem) + modifiersTotal(getSelectedModifiersFromModal());
  addBtn.textContent = `${t('add_to_cart', 'Add to Cart')} (${formatMoney(total)})`;
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
  title.textContent = menuItem.name || t('customize_item', 'Customize Item');
  const basePrice = getEffectiveBasePrice(menuItem);
  const normalPrice = toNumber(menuItem.price, 0);
  if (toNumber(menuItem.discount_price, 0) > 0) {
    base.innerHTML = `Base: <span class="line-through text-slate-400">${formatMoney(normalPrice)}</span> <span class="text-red-500 font-semibold">${formatMoney(basePrice)}</span>`;
  } else {
    base.textContent = `Base: ${formatMoney(basePrice)}`;
  }
  noteEl.value = '';

  const groups = Array.isArray(menuItem.modifiers_config) ? menuItem.modifiers_config : [];
  if (!groups.length) {
    groupsEl.innerHTML = `<p class="text-sm text-slate-500">${escapeHtml(t('none', 'None'))}</p>`;
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
                <span class="text-slate-600">+${formatMoney(toNumber(opt?.price, 0))}</span>
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
  const raw = String(item?.status || 'pending').toLowerCase();
  if (raw === 'ready' || raw === 'completed' || raw === 'served') return 'Ready';
  return 'Pending';
}

function normalizeTrackingStatus(raw) {
  const value = String(raw || '').toLowerCase();
  if (value === 'cancelled') return 'cancelled';
  if (value === 'served') return 'served';
  return 'pending';
}

function statusBadgeHtml(status) {
  const s = normalizeTrackingStatus(status);
  if (s === 'cancelled') {
    return `<span class="text-xs px-2 py-0.5 rounded bg-rose-100 text-rose-700">${escapeHtml(t('cancelled', 'Cancelled'))}</span>`;
  }
  if (s === 'served') {
    return `<span class="text-xs px-2 py-0.5 rounded bg-emerald-500 text-white">${escapeHtml(t('served', 'Served'))}</span>`;
  }
  return `<span class="text-xs px-2 py-0.5 rounded bg-amber-500 text-white">${escapeHtml(t('ordered', 'Ordered'))}</span>`;
}

function statusToggleButtonHtml(itemId, status) {
  const s = normalizeTrackingStatus(status);
  if (s === 'cancelled') return '';
  if (s === 'served') {
    return `<button type="button" data-toggle-served-item-id="${itemId}" data-next-status="pending" class="text-xs px-3 py-1.5 rounded bg-slate-400 text-white hover:bg-slate-500">↩ ${escapeHtml(t('undo', 'Undo'))}</button>`;
  }
  return `<button type="button" data-toggle-served-item-id="${itemId}" data-next-status="served" class="text-xs px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700">✓ ${escapeHtml(t('mark_as_served', 'Mark as Served'))}</button>`;
}

function cancelButtonHtml(itemId, status) {
  if (normalizeTrackingStatus(status) === 'cancelled') return '';
  return `<button type="button" data-cancel-order-item-id="${itemId}" class="text-xs px-3 py-1.5 rounded border border-rose-500 text-rose-600 hover:bg-rose-50">✖ ${escapeHtml(t('cancel_item', 'Cancel Item'))}</button>`;
}

function isConfirmAccepted(result) {
  if (typeof result === 'boolean') return result;
  if (result && typeof result === 'object') {
    if ('confirmed' in result) return Boolean(result.confirmed);
    if ('ok' in result) return Boolean(result.ok);
    if ('value' in result && typeof result.value === 'boolean') return result.value;
  }
  return Boolean(result);
}

function openDetailsSidebar() {
  const backdrop = document.getElementById('waiter-table-details-backdrop');
  const sidebar = document.getElementById('waiter-table-details-sidebar');
  if (backdrop) backdrop.classList.remove('hidden');
  if (sidebar) sidebar.classList.remove('translate-x-full');
  tableDetailsOpen = true;
}

function updateOrderDetailsAddMoreButton() {
  const btn = document.getElementById('waiter-table-details-add-more');
  if (!btn) return;
  if (!tableDetailsOrderContext) {
    btn.disabled = true;
    btn.classList.add('hidden');
    return;
  }
  const isTakeaway = tableDetailsOrderContext.type === 'takeaway';
  btn.classList.toggle('hidden', isTakeaway);
  if (isTakeaway) {
    btn.disabled = true;
    return;
  }
  btn.disabled = false;
  btn.textContent = t('add_more_items', 'Add More Items');
}

function closeDetailsSidebar() {
  const backdrop = document.getElementById('waiter-table-details-backdrop');
  const sidebar = document.getElementById('waiter-table-details-sidebar');
  if (backdrop) backdrop.classList.add('hidden');
  if (sidebar) sidebar.classList.add('translate-x-full');
  tableDetailsOpen = false;
  tableDetailsOrderId = null;
  tableDetailsTableName = '';
  tableDetailsOrderContext = null;
  updateOrderDetailsAddMoreButton();
}

function activateContextFromOrderDetails() {
  if (!tableDetailsOrderContext) return;
  if (tableDetailsOrderContext.type === 'takeaway') return;
  setActiveOrderContext(tableDetailsOrderContext);
  currentView = activeOrderContext.type === 'takeaway' ? 'takeaway' : 'tables';
  renderZoneTabs();
  updateOrderSourceView();
  renderSelectedTableLabel();
  renderCart();
  closeDetailsSidebar();
  focusCartSidebar();
  if (window.toast?.success) window.toast.success(`Active context: ${activeOrderContext.title}`);
}

function renderTableDetailsItems(orderDetails) {
  const content = document.getElementById('waiter-table-details-content');
  if (!content) return;
  const items = orderDetails?.items || [];
  if (!items.length) {
    content.innerHTML = `<p class="text-slate-500">${escapeHtml(t('no_ordered_items_found', 'No ordered items found.'))}</p>`;
    return;
  }

  content.innerHTML = `
    <div class="rounded-md border border-slate-200 bg-slate-50 p-3 mb-2">
      <p class="text-sm text-slate-600">${escapeHtml(t('grand_total', 'Grand Total'))}</p>
      <p class="text-lg font-semibold text-slate-800">${formatMoney(Number(orderDetails?.total_amount || 0))}</p>
    </div>
    ${items.map((item) => {
    const status = normalizeTrackingStatus(item.item_status);
    const isCancelled = status === 'cancelled';
    const textClass = isCancelled ? 'line-through text-gray-400' : 'text-slate-800';
    const waiterClass = isCancelled ? 'line-through text-gray-400' : 'text-slate-500';
    return `
      <div class="border border-slate-200 rounded-md p-3" data-order-item-id="${item.id}">
        <div class="flex items-center justify-between gap-2 mb-2">
          <div>
            <p class="font-medium ${textClass}">${escapeHtml(item.menu_item_name)} x ${item.quantity}</p>
            <p class="text-xs ${waiterClass}">${escapeHtml(t('waiter', 'Waiter'))}: ${escapeHtml(displayOrderWaiterLine(item.waiter_name))}</p>
          </div>
          <span data-item-status-badge>${statusBadgeHtml(status)}</span>
        </div>
        <div data-item-status-action class="flex flex-wrap gap-2">
          ${statusToggleButtonHtml(item.id, status)}
          ${cancelButtonHtml(item.id, status)}
        </div>
      </div>
    `;
  }).join('')}
  `;

  content.onclick = async (event) => {
    const statusBtn = event.target.closest('[data-toggle-served-item-id]');
    const cancelBtn = event.target.closest('[data-cancel-order-item-id]');

    if (statusBtn && content.contains(statusBtn)) {
      const itemId = Number(statusBtn.getAttribute('data-toggle-served-item-id'));
      const nextStatus = normalizeTrackingStatus(statusBtn.getAttribute('data-next-status'));
      const orderIdForUpdate = Number(tableDetailsOrderId || orderDetails?.id || 0);
      if (!orderIdForUpdate || !itemId) {
        console.warn('[Waiter][status-toggle] missing identifiers', {
          tableDetailsOrderId,
          orderDetailsId: orderDetails?.id,
          itemId,
          nextStatus,
        });
        showError(t('load_failed', 'Load Failed'));
        return;
      }
      statusBtn.disabled = true;
      try {
        const updatedOrder = await updateOrderItemStatus(orderIdForUpdate, itemId, nextStatus);
        renderTableDetailsItems(updatedOrder || orderDetails);
        if (nextStatus === 'served') showSuccess(`${t('item', 'Item')} ${t('served', 'Served')}.`);
        else showSuccess(`${t('item', 'Item')} ${t('pending', 'Pending')}.`);
        queueRefresh();
      } catch (err) {
        console.error(err);
        showError(err.message || t('load_failed', 'Load Failed'));
        statusBtn.disabled = false;
      }
      return;
    }

    if (cancelBtn && content.contains(cancelBtn)) {
      const itemId = Number(cancelBtn.getAttribute('data-cancel-order-item-id'));
      const orderIdForUpdate = Number(tableDetailsOrderId || orderDetails?.id || 0);
      if (!orderIdForUpdate || !itemId) {
        console.warn('[Waiter][cancel-item] missing identifiers', {
          tableDetailsOrderId,
          orderDetailsId: orderDetails?.id,
          itemId,
        });
        showError(t('load_failed', 'Load Failed'));
        return;
      }
      const confirmTitle = 'Cancel Item';
      const confirmMessage = 'Did you check with the kitchen? Are you sure you want to cancel this item?';
      const isConfirmed = await confirmAction(confirmTitle, confirmMessage);
      if (!isConfirmed) return;
      cancelBtn.disabled = true;
      try {
        const updatedOrder = await updateOrderItemStatus(orderIdForUpdate, itemId, 'cancelled');
        if (String(updatedOrder?.status || '').toLowerCase() === 'cancelled') {
          closeDetailsSidebar();
          setActiveOrderContext(null);
          selectedTableId = null;
          updateOrderSourceView();
          renderSelectedTableLabel();
        } else {
          renderTableDetailsItems(updatedOrder || orderDetails);
        }
        showSuccess(t('cancelled', 'Cancelled'));
        queueRefresh();
      } catch (err) {
        console.error(err);
        showError(err.message || t('load_failed', 'Load Failed'));
        cancelBtn.disabled = false;
      }
    }
  };
}

async function openTableDetailsSidebar(tableId, tableName) {
  const activeOrder = await fetchActiveOrderByTable(tableId);
  if (!activeOrder || !activeOrder.id) {
    const content = document.getElementById('waiter-table-details-content');
    if (content) content.innerHTML = `<p class="text-slate-500">${escapeHtml(t('no_active_order_for_table', 'No active order found for this table.'))}</p>`;
    return;
  }
  await openOrderDetails({
    orderId: activeOrder.id,
    orderType: activeOrder.order_type || 'dine_in',
    tableId,
    tableName,
  });
}

async function submitOrder(payload) {
  return fetchJson(`${API_BASE}/api/orders/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

function bindSubmitOrder() {
  const submitBtn = document.getElementById('submit-order');

  if (!submitBtn) return;
  submitBtn.addEventListener('click', async () => {
    if (!activeOrderContext) {
      showError('Please select a table first, or choose New Takeaway Order.');
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
    const payload = {
      table_id: activeOrderContext.table_id ?? null,
      order_type: activeOrderContext.type === 'takeaway' ? 'takeaway' : 'dine_in',
      customer_name: activeOrderContext.customer_name || null,
      items,
    };
    submitBtn.disabled = true;
    try {
      const data = await submitOrder(payload);
      if (!data) return;
      cart.clear();
      setActiveOrderContext(null);
      renderCart();
      showSuccess(data.message || t('order_submitted', 'Order submitted.'));
      if (AUTO_LOGOUT_AFTER_SUBMIT) {
        setTimeout(() => autoLogoutToPin(), 650);
      } else if (isCashierRole()) {
        setTimeout(() => redirectCashierToBillingTab(), 500);
      } else {
        submitBtn.disabled = false;
      }
    } catch (err) {
      console.error(err);
      showError(err.message || t('failed_to_submit_order', 'Failed to submit order'));
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
    if (activeOrderContext?.type === 'dine_in') setActiveOrderContext(null);
  } else {
    if (!activeZoneId || !zones.some((z) => z.id === activeZoneId)) activeZoneId = zones[0].id;
    const allTableIds = zones.flatMap((z) => z.tables || []).map((t) => t.id);
    if (selectedTableId && !allTableIds.includes(selectedTableId)) selectedTableId = null;
    if (
      activeOrderContext?.type === 'dine_in' &&
      activeOrderContext.table_id &&
      !allTableIds.includes(activeOrderContext.table_id)
    ) {
      setActiveOrderContext(null);
    }
  }
  renderZoneTabs();
  updateOrderSourceView();

  // Optional preselect via /waiter?table_id=123 (used by Table Dashboard redirect).
  const paramTableId = Number(new URLSearchParams(window.location.search).get('table_id') || 0);
  if (paramTableId && zones.flatMap((z) => z.tables || []).some((t) => t.id === paramTableId)) {
    currentView = 'tables';
    selectedTableId = paramTableId;
    const paramTable = zones.flatMap((z) => z.tables || []).find((t) => t.id === paramTableId);
    const paramTableName = tableLabel(paramTable || { id: paramTableId });
    setActiveOrderContext({
      type: 'dine_in',
      table_id: paramTableId,
      customer_name: null,
      title: `Table ${paramTableName}`,
    });
    const selectedZone = zones.find((z) => (z.tables || []).some((t) => t.id === paramTableId));
    if (selectedZone) activeZoneId = selectedZone.id;
    renderZoneTabs();
    updateOrderSourceView();
  }
}

async function loadTakeawayOrders() {
  const data = await fetchActiveTakeawayOrders();
  if (!data) return;
  takeawayOrders = data;
  renderTakeawayOrdersList(takeawayOrders);
}

function startTakeawayPolling() {
  if (takeawayPollTimer) return;
  takeawayPollTimer = setInterval(() => {
    if (currentView !== 'takeaway') return;
    loadTakeawayOrders().catch((err) => {
      console.error('Takeaway polling error:', err);
    });
  }, 5000);
}

function queueRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    try {
      await Promise.all([refreshTableStatus(), loadTakeawayOrders()]);
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
            discount_price: item.discount_price ?? null,
            category_id: item.category_id,
            description: item.description ?? null,
            image_url: item.image_url ?? null,
            is_available: item.is_available !== false,
            is_promoted: item.is_promoted === true,
            modifiers_config: Array.isArray(item.modifiers_config) ? item.modifiers_config : [],
          });
          renderCategoryTabs();
          renderMenu();
        }
        return;
      }
      if (msg.event === 'menu_item_updated' && msg.data) {
        const item = msg.data;
        const idx = menuItems.findIndex((m) => m.id === item.id);
        if (idx >= 0) {
          menuItems[idx] = {
            ...menuItems[idx],
            ...item,
            discount_price: item.discount_price ?? null,
          };
          renderMenu();
          renderCart();
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
        return;
      }
      if (
        msg.event === 'takeaways_updated' ||
        (msg.event === 'order_completed' && String(msg?.data?.order_type || '').toLowerCase() === 'takeaway')
      ) {
        if (currentView === 'takeaway') {
          loadTakeawayOrders().catch((err) => {
            console.error('Takeaway live refresh error:', err);
          });
        }
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 3000);
  ws.onerror = () => {};
}

if (
  window.auth &&
  window.auth.getToken() &&
  ['waiter', 'cashier', 'admin', 'root'].includes(String(window.auth.getUser?.()?.role || '').toLowerCase())
) {
  (async function init() {
    bindBackToDashboardNav();
    bindSubmitOrder();
    bindModifierModal();
    bindTakeawayModal();
    const closeBtn = document.getElementById('waiter-table-details-close');
    const addMoreBtn = document.getElementById('waiter-table-details-add-more');
    const clearContextBtn = document.getElementById('cart-clear-context');
    const backdrop = document.getElementById('waiter-table-details-backdrop');
    if (closeBtn) closeBtn.addEventListener('click', closeDetailsSidebar);
    if (addMoreBtn) addMoreBtn.addEventListener('click', activateContextFromOrderDetails);
    if (clearContextBtn) clearContextBtn.addEventListener('click', clearCartAndContext);
    if (backdrop) backdrop.addEventListener('click', closeDetailsSidebar);
    updateOrderDetailsAddMoreButton();
    updateCartUIContext();
    connectWebSocket();
    startTakeawayPolling();
    try {
      const [items, cats] = await Promise.all([fetchMenuItems(), fetchCategories()]);
      menuItems = items || [];
      categories = cats || [];
      activeCategoryId = null;
      renderCategoryTabs();
      renderMenu();
      await Promise.all([refreshTableStatus(), loadTakeawayOrders()]);
    } catch (err) {
      console.error(err);
      document.getElementById('menu-grid').innerHTML = '<p class="col-span-full text-red-600">Error loading waiter screen.</p>';
    }
  })();
}
