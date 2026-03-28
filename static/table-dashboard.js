const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['admin', 'waiter'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

let zones = [];
let activeZoneId = null;
let selectedOrderId = null;
let selectedTableLabel = '';

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}

function showError(msg) {
  if (window.toast?.error) window.toast.error(msg);
  else window.alert(msg);
}

function showSuccess(msg) {
  if (window.toast?.success) window.toast.success(msg);
  else window.alert(msg);
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
    const detail = Array.isArray(data.detail)
      ? data.detail.map((x) => x.msg || x).join(', ')
      : (data.detail || 'Request failed');
    throw new Error(detail);
  }
  return data;
}

async function fetchTableGrid() {
  return fetchJson(`${API_BASE}/api/tables/grid`);
}

async function fetchOrderDetails(orderId) {
  return fetchJson(`${API_BASE}/api/orders/${orderId}/details`);
}

async function updateOrderItemStatus(orderId, itemId, status) {
  return fetchJson(`${API_BASE}/api/orders/${orderId}/items/${itemId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
}

function getActiveZone() {
  return zones.find((z) => z.id === activeZoneId) || null;
}

function statusBadge(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'served') return 'bg-emerald-100 text-emerald-700';
  if (s === 'cooking') return 'bg-orange-100 text-orange-700';
  return 'bg-slate-200 text-slate-700';
}

function renderZoneTabs() {
  const container = document.getElementById('zone-tabs');
  if (!container) return;
  if (!zones.length) {
    container.innerHTML = '<p class="text-slate-500">No zones found.</p>';
    return;
  }
  container.innerHTML = zones
    .map((zone) => `
      <button type="button" data-zone-id="${zone.id}" class="zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${
        zone.id === activeZoneId
          ? 'bg-blue-600 text-white'
          : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
      }">
        ${escapeHtml(zone.name)}
      </button>
    `)
    .join('');
  container.querySelectorAll('.zone-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeZoneId = Number(btn.dataset.zoneId);
      renderZoneTabs();
      renderTablesGrid();
    });
  });
}

function renderTablesGrid() {
  const container = document.getElementById('tables-grid');
  if (!container) return;
  const zone = getActiveZone();
  const tables = zone?.tables || [];
  if (!tables.length) {
    container.innerHTML = '<p class="col-span-full text-slate-500">No tables in this zone.</p>';
    return;
  }

  container.innerHTML = tables
    .map((table) => {
      const occupied = String(table.status) === 'occupied';
      const cardColor = occupied
        ? 'bg-red-100 border-red-500'
        : 'bg-green-100 border-green-500';
      return `
        <button
          type="button"
          data-table-id="${table.id}"
          data-table-name="${escapeHtml(table.name)}"
          data-status="${escapeHtml(table.status)}"
          data-active-order-id="${table.active_order_id ?? ''}"
          class="table-card border-2 rounded-lg p-3 text-left ${cardColor} hover:shadow"
        >
          <div class="font-semibold text-slate-800">Table ${escapeHtml(table.name)}</div>
          <div class="text-xs mt-1 uppercase tracking-wide text-slate-700">${escapeHtml(table.status)}</div>
          ${
            occupied && table.active_order_id
              ? `<div class="text-xs mt-1 text-slate-600">Order #${table.active_order_id}</div>`
              : ''
          }
        </button>
      `;
    })
    .join('');

  container.querySelectorAll('.table-card').forEach((card) => {
    card.addEventListener('click', async () => {
      const tableId = Number(card.dataset.tableId);
      const tableName = card.dataset.tableName || String(tableId);
      const status = card.dataset.status;
      const activeOrderId = Number(card.dataset.activeOrderId || 0);

      if (status === 'available') {
        window.location.href = `/waiter?table_id=${encodeURIComponent(tableId)}`;
        return;
      }
      if (!activeOrderId) {
        showError('No active order found for this table.');
        return;
      }
      selectedOrderId = activeOrderId;
      selectedTableLabel = tableName;
      await openOrderSidebar(activeOrderId, tableName);
    });
  });
}

function openSidebar() {
  const backdrop = document.getElementById('order-sidebar-backdrop');
  const sidebar = document.getElementById('order-sidebar');
  if (backdrop) backdrop.classList.remove('hidden');
  if (sidebar) sidebar.classList.remove('translate-x-full');
}

function closeSidebar() {
  const backdrop = document.getElementById('order-sidebar-backdrop');
  const sidebar = document.getElementById('order-sidebar');
  if (backdrop) backdrop.classList.add('hidden');
  if (sidebar) sidebar.classList.add('translate-x-full');
  selectedOrderId = null;
}

async function openOrderSidebar(orderId, tableName) {
  const subtitle = document.getElementById('sidebar-subtitle');
  if (subtitle) subtitle.textContent = `Table ${tableName} • Order #${orderId}`;
  openSidebar();
  await renderOrderDetails(orderId);
}

function statusButtons(item) {
  const statuses = ['pending', 'cooking', 'served'];
  const current = String(item.item_status || 'pending');
  return statuses
    .map((s) => `
      <button
        type="button"
        data-item-id="${item.id}"
        data-status="${s}"
        class="item-status-btn px-2 py-1 text-xs rounded border ${
          s === current
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
        }"
      >
        ${s}
      </button>
    `)
    .join('');
}

async function renderOrderDetails(orderId) {
  const content = document.getElementById('sidebar-content');
  if (!content) return;
  content.innerHTML = '<p class="text-slate-500">Loading order...</p>';
  try {
    const order = await fetchOrderDetails(orderId);
    if (!order) return;
    const items = order.items || [];
    if (!items.length) {
      content.innerHTML = '<p class="text-slate-500">No items in this order.</p>';
      return;
    }
    content.innerHTML = items
      .map((item) => `
        <div class="border border-slate-200 rounded-md p-3">
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="font-medium text-slate-800">${escapeHtml(item.menu_item_name)} x ${item.quantity}</p>
              <p class="text-xs text-slate-500">Waiter: ${escapeHtml(item.waiter_name || '-')}</p>
            </div>
            <span class="text-xs px-2 py-1 rounded ${statusBadge(item.item_status)}">${escapeHtml(item.item_status)}</span>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            ${statusButtons(item)}
          </div>
        </div>
      `)
      .join('');

    content.querySelectorAll('.item-status-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const itemId = Number(btn.dataset.itemId);
        const newStatus = btn.dataset.status;
        try {
          await updateOrderItemStatus(orderId, itemId, newStatus);
          showSuccess(`Item updated to ${newStatus}.`);
          await renderOrderDetails(orderId);
          await refreshGrid();
        } catch (err) {
          console.error(err);
          showError(err.message || 'Failed to update item status');
        }
      });
    });
  } catch (err) {
    console.error(err);
    content.innerHTML = `<p class="text-red-600">${escapeHtml(err.message || 'Failed to load order')}</p>`;
  }
}

async function refreshGrid() {
  const data = await fetchTableGrid();
  if (!data) return;
  zones = data || [];
  if (!zones.length) {
    activeZoneId = null;
  } else if (!activeZoneId || !zones.some((z) => z.id === activeZoneId)) {
    activeZoneId = zones[0].id;
  }
  renderZoneTabs();
  renderTablesGrid();
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);
  ws.onmessage = async (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (
        msg.event === 'table_grid_updated' ||
        msg.event === 'table_status_changed' ||
        msg.event === 'new_order_batch' ||
        msg.event === 'order_updated'
      ) {
        await refreshGrid();
        if (selectedOrderId) {
          await renderOrderDetails(selectedOrderId);
        }
      }
    } catch (err) {
      console.error('WebSocket parse error', err);
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 2500);
  ws.onerror = () => {};
}

function bindUI() {
  const closeBtn = document.getElementById('btn-close-sidebar');
  const backdrop = document.getElementById('order-sidebar-backdrop');
  const refreshBtn = document.getElementById('btn-refresh-grid');
  if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if (backdrop) backdrop.addEventListener('click', closeSidebar);
  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    await refreshGrid();
    if (selectedOrderId) await renderOrderDetails(selectedOrderId);
  });
}

if (window.auth && window.auth.getToken()) {
  (async function init() {
    bindUI();
    connectWebSocket();
    try {
      await refreshGrid();
    } catch (err) {
      console.error(err);
      showError(err.message || 'Failed to load table dashboard');
    }
  })();
}
