const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['cashier', 'admin'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

// —— Tab switching ——
const tabCashier = document.getElementById('tab-cashier');
const tabMenu = document.getElementById('tab-menu');
const tabUsers = document.getElementById('tab-users');
const tabTables = document.getElementById('tab-tables');
const panelCashier = document.getElementById('panel-cashier');
const panelMenu = document.getElementById('panel-menu');
const panelUsers = document.getElementById('panel-users');
const panelTables = document.getElementById('panel-tables');

function showPanel(panel) {
  if (!panel) return;
  panelCashier.classList.add('hidden');
  panelMenu.classList.add('hidden');
  if (panelUsers) panelUsers.classList.add('hidden');
  if (panelTables) panelTables.classList.add('hidden');

  tabCashier.classList.remove('border-blue-600', 'text-blue-600');
  tabCashier.classList.add('border-transparent', 'text-slate-600');
  tabMenu.classList.remove('border-blue-600', 'text-blue-600');
  tabMenu.classList.add('border-transparent', 'text-slate-600');

  if (tabUsers) {
    tabUsers.classList.remove('border-blue-600', 'text-blue-600');
    tabUsers.classList.add('border-transparent', 'text-slate-600');
  }
  if (tabTables) {
    tabTables.classList.remove('border-blue-600', 'text-blue-600');
    tabTables.classList.add('border-transparent', 'text-slate-600');
  }

  panel.classList.remove('hidden');

  if (panel === panelCashier) {
    tabCashier.classList.add('border-blue-600', 'text-blue-600');
    loadUnpaidOrders();
  } else if (panel === panelMenu) {
    tabMenu.classList.add('border-blue-600', 'text-blue-600');
    loadMenuData();
  } else if (panelUsers && panel === panelUsers) {
    if (tabUsers) tabUsers.classList.add('border-blue-600', 'text-blue-600');
    loadUsers();
  } else if (panelTables && panel === panelTables) {
    if (tabTables) tabTables.classList.add('border-blue-600', 'text-blue-600');
    loadTableManagementData();
  }
}

tabCashier.addEventListener('click', () => showPanel(panelCashier));
tabMenu.addEventListener('click', () => showPanel(panelMenu));
if (tabUsers && panelUsers) tabUsers.addEventListener('click', () => showPanel(panelUsers));
if (tabTables && panelTables) tabTables.addEventListener('click', () => showPanel(panelTables));

// Fallback delegated tab handler (handles dynamic/edge cases where direct listeners fail).
document.addEventListener('click', (e) => {
  const btn = e.target && e.target.closest ? e.target.closest('.tab-btn[data-target-panel]') : null;
  if (!btn) return;
  const panelId = btn.getAttribute('data-target-panel');
  if (!panelId) return;
  const panel = document.getElementById(panelId);
  if (!panel) return;
  e.preventDefault();
  showPanel(panel);
});

function applyAdminOnlyTabVisibility(role) {
  const normalizedRole = String(role || '').toLowerCase();
  const isAdmin = normalizedRole === 'admin';
  if (tabUsers) tabUsers.classList.toggle('hidden', !isAdmin);
  if (tabTables) tabTables.classList.toggle('hidden', !isAdmin);
  // If current panel is admin-only but user is not admin, fallback to cashier.
  if (!isAdmin && panelTables && !panelTables.classList.contains('hidden')) {
    showPanel(panelCashier);
  }
}

// User + table management tabs are admin-only.
if (window.auth && window.auth.getUser) {
  const user = window.auth.getUser();
  if (user && user.role) {
    applyAdminOnlyTabVisibility(user.role);
  } else if (window.auth.getToken) {
    // Recover role if token exists but localStorage user object is missing.
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { ...window.auth.getAuthHeaders() },
    })
      .then(async (res) => {
        if (window.auth && window.auth.checkUnauthorized(res)) return null;
        if (!res.ok) return null;
        const me = await res.json().catch(() => null);
        if (me && me.role && window.auth.setAuth && window.auth.getToken) {
          window.auth.setAuth(window.auth.getToken(), me);
          return me;
        }
        return null;
      })
      .then((me) => {
        applyAdminOnlyTabVisibility(me?.role || '');
      })
      .catch(() => {
        applyAdminOnlyTabVisibility('');
      });
  } else {
    applyAdminOnlyTabVisibility('');
  }
}

// —— Cashier / Billing (table-centric: one active order per table, consolidated items + grand total) ——
let selectedOrderId = null;
let selectedTableNumber = null;
let selectedOrderTotal = 0;
let cashierZones = [];
let cashierActiveZoneId = null;

async function fetchCashierTableGrid() {
  const res = await fetch(`${API_BASE}/api/tables/grid`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch table grid');
  return res.json();
}

async function fetchActiveOrderByTable(tableId) {
  const res = await fetch(`${API_BASE}/api/orders/active-by-table/${tableId}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) throw new Error('Unauthorized');
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `No active order for table ${tableId}`);
  }
  return res.json();
}

function cashierTableName(table) {
  return table?.name || table?.name_or_number || `#${table?.id ?? ''}`;
}

function renderCashierZoneTabs() {
  const tabs = document.getElementById('cashier-zone-tabs');
  if (!tabs) return;
  if (!cashierZones.length) {
    tabs.innerHTML = '<span class="text-slate-500 text-sm">No zones</span>';
    return;
  }
  tabs.innerHTML = cashierZones
    .map((zone) => `
      <button
        type="button"
        data-cashier-zone-id="${zone.id}"
        class="cashier-zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${
          zone.id === cashierActiveZoneId
            ? 'bg-blue-600 text-white'
            : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
        }"
      >
        ${escapeHtml(zone.name)}
      </button>
    `)
    .join('');
  tabs.querySelectorAll('.cashier-zone-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      cashierActiveZoneId = parseInt(btn.dataset.cashierZoneId, 10);
      renderCashierZoneTabs();
      renderCashierTablesGrid();
    });
  });
}

function getCashierActiveZoneTables() {
  const zone = cashierZones.find((z) => z.id === cashierActiveZoneId);
  return zone?.tables || [];
}

function renderCashierTablesGrid() {
  const grid = document.getElementById('cashier-tables-grid');
  if (!grid) return;
  const tables = getCashierActiveZoneTables();
  if (!tables.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No tables in this zone.</p>';
    return;
  }
  grid.innerHTML = tables
    .map((table) => {
      const occupied = String(table.status) === 'occupied';
      const color = occupied
        ? 'bg-red-100 border-red-500'
        : 'bg-green-100 border-green-500';
      return `
        <button
          type="button"
          data-cashier-table-id="${table.id}"
          data-cashier-table-name="${escapeHtml(cashierTableName(table))}"
          data-cashier-table-status="${escapeHtml(table.status)}"
          class="cashier-table-card border-2 rounded-md p-2 text-left ${color} hover:shadow"
        >
          <div class="font-medium text-slate-800 text-sm">Table ${escapeHtml(cashierTableName(table))}</div>
          <div class="text-[11px] uppercase tracking-wide text-slate-700">${escapeHtml(table.status)}</div>
        </button>
      `;
    })
    .join('');

  grid.querySelectorAll('.cashier-table-card').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const tableId = parseInt(btn.dataset.cashierTableId, 10);
      const status = btn.dataset.cashierTableStatus;
      const tableName = btn.dataset.cashierTableName || String(tableId);
      if (status === 'available') {
        if (window.toast) window.toast.info('Table is currently empty');
        else alert('Table is currently empty');
        return;
      }
      try {
        const order = await fetchActiveOrderByTable(tableId);
        selectOrder(order);
      } catch (e) {
        if (window.toast) window.toast.error(e.message || `No active order for Table ${tableName}`);
        else alert(e.message || `No active order for Table ${tableName}`);
      }
    });
  });
}

function loadUnpaidOrders() {
  const grid = document.getElementById('cashier-tables-grid');
  if (grid) grid.innerHTML = '<p class="col-span-full text-slate-500">Loading table grid...</p>';
  fetchCashierTableGrid()
    .then((zones) => {
      cashierZones = zones || [];
      if (cashierZones.length) {
        if (!cashierActiveZoneId || !cashierZones.some((z) => z.id === cashierActiveZoneId)) {
          cashierActiveZoneId = cashierZones[0].id;
        }
      } else {
        cashierActiveZoneId = null;
      }
      renderCashierZoneTabs();
      renderCashierTablesGrid();
    })
    .catch((e) => {
      console.error(e);
      if (grid) grid.innerHTML = '<p class="col-span-full text-red-600">Error loading table grid.</p>';
    });
}

function selectOrder(order) {
  if (!order) return;
  selectedOrderId = order.id;
  selectedTableNumber = order.table_number;
  selectedOrderTotal = Number(order.total_amount) || 0;
  document.getElementById('receipt-placeholder').classList.add('hidden');
  const container = document.getElementById('receipt-container');
  container.classList.remove('hidden');
  document.getElementById('receipt-table-number').textContent = order.table_number;
  const itemsRows = (order.items || [])
    .map(
      (i) =>
        `<tr><td class="py-1">${escapeHtml(i.menu_item_name)}</td><td class="py-1 text-right">${i.quantity}</td><td class="py-1 text-right">$${Number(i.subtotal).toFixed(2)}</td></tr>`
    )
    .join('');
  document.getElementById('receipt-content').innerHTML = `
    <table class="w-full text-sm text-slate-700">
      <thead><tr class="border-b border-slate-200"><th class="text-left py-1">Item</th><th class="text-right py-1">Qty</th><th class="text-right py-1">Subtotal</th></tr></thead>
      <tbody>${itemsRows}</tbody>
    </table>
  `;
  document.getElementById('receipt-grand-total').textContent = 'Grand Total: $' + Number(order.total_amount).toFixed(2);
  const servedByEl = document.getElementById('receipt-served-by');
  if (servedByEl) servedByEl.textContent = order.served_by_name || '—';
  // Reset payment inputs for this order
  const amountInput = document.getElementById('amount-tendered');
  const changeSpan = document.getElementById('change-amount');
  const methodSelect = document.getElementById('payment-method');
  if (amountInput) amountInput.value = '';
  if (changeSpan) changeSpan.textContent = '$0.00';
  if (methodSelect) methodSelect.value = 'cash';
}

function renderReceiptForPrint(order) {
  try {
    const rpTable = document.getElementById('rp-table');
    const rpServedBy = document.getElementById('rp-served-by');
    const rpDatetime = document.getElementById('rp-datetime');
    const rpItems = document.getElementById('rp-items');
    const rpTotal = document.getElementById('rp-total');
    const rpMethod = document.getElementById('rp-method');
    const rpTendered = document.getElementById('rp-tendered');
    const rpChange = document.getElementById('rp-change');

    if (rpTable) rpTable.textContent = order.table_number ?? '';
    if (rpServedBy) rpServedBy.textContent = order.served_by_name || '—';
    if (rpDatetime) rpDatetime.textContent = order.created_at ? new Date(order.created_at).toLocaleString() : '';
    if (rpMethod) rpMethod.textContent = order.payment_method || '';
    if (rpTendered) rpTendered.textContent = order.amount_tendered != null ? `$${Number(order.amount_tendered).toFixed(2)}` : '$0.00';
    if (rpChange) rpChange.textContent = order.change_amount != null ? `$${Number(order.change_amount).toFixed(2)}` : '$0.00';

    let subtotal = 0;
    const rows = (order.items || [])
      .map((item) => {
        subtotal += Number(item.subtotal) || 0;
        return `
          <div class="flex justify-between gap-2">
            <span class="flex-1">${escapeHtml(item.menu_item_name)}</span>
            <span class="text-right">× ${item.quantity}</span>
            <span class="text-right">$${Number(item.subtotal).toFixed(2)}</span>
          </div>
        `;
      })
      .join('');
    if (rpItems) rpItems.innerHTML = rows || '<div class="text-sm text-slate-600">No items</div>';
    if (rpTotal) rpTotal.textContent = `$${Number(order.total_amount).toFixed(2)}`;
  } catch (e) {
    // Don't block checkout if printing fails.
    console.error('Receipt print rendering failed:', e);
  }
}

// Dynamic change calculation and payment processing
const amountInputEl = document.getElementById('amount-tendered');
const changeSpanEl = document.getElementById('change-amount');
const paymentMethodEl = document.getElementById('payment-method');

if (amountInputEl) {
  amountInputEl.addEventListener('input', () => {
    const tendered = parseFloat(amountInputEl.value || '0');
    const change = tendered - selectedOrderTotal;
    if (Number.isNaN(change)) {
      changeSpanEl.textContent = '$0.00';
    } else if (change >= 0) {
      changeSpanEl.textContent = `$${change.toFixed(2)}`;
    } else {
      changeSpanEl.textContent = 'Insufficient';
    }
  });
}

document.getElementById('btn-process-payment').addEventListener('click', async () => {
  if (selectedOrderId == null) return;
  const btn = document.getElementById('btn-process-payment');
  const amountInput = document.getElementById('amount-tendered');
  const methodSelect = document.getElementById('payment-method');
  const tendered = parseFloat((amountInput && amountInput.value) || '0');

  if (Number.isNaN(tendered) || tendered <= 0) {
    if (window.toast) window.toast.error('Enter a valid amount tendered.');
    else alert('Enter a valid amount tendered.');
    return;
  }
  if (tendered < selectedOrderTotal) {
    if (window.toast) window.toast.error('Amount tendered is less than total.');
    else alert('Amount tendered is less than total.');
    return;
  }

  const method = methodSelect ? methodSelect.value || 'cash' : 'cash';

  btn.disabled = true;
  btn.textContent = 'Processing…';
  try {
    const res = await fetch(`${API_BASE}/api/orders/${selectedOrderId}/checkout`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify({ payment_method: method, amount_tendered: tendered }),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (window.toast) window.toast.error(data.detail || 'Payment failed');
      else alert(data.detail || 'Payment failed');
      return;
    }
    if (window.toast) window.toast.success('Payment processed successfully.');
    else alert('Payment processed successfully.');

    // Populate printable receipt and trigger print
    renderReceiptForPrint(data);
    window.print();

    selectedOrderId = null;
    selectedTableNumber = null;
    selectedOrderTotal = 0;
    document.getElementById('receipt-container').classList.add('hidden');
    document.getElementById('receipt-placeholder').classList.remove('hidden');
    // Reload grid from backend after payment.
    loadUnpaidOrders();
  } catch (e) {
    console.error(e);
    if (window.toast) window.toast.error('Payment failed');
    else alert('Payment failed');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Confirm Payment';
  }
});

// —— Menu Management (same as app.js) ——
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// —— Admin User Management ——
let usersState = [];
let selectedUserId = null;

async function fetchUsers() {
  const res = await fetch(`${API_BASE}/api/admin/users`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to fetch users');
  }
  return res.json();
}

function renderUsers(users) {
  usersState = users || [];
  const tbody = document.getElementById('users-table-body');
  if (!tbody) return;
  if (!usersState.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="py-3 text-slate-500">No users</td></tr>';
    return;
  }
  tbody.innerHTML = usersState
    .map((u) => {
      const pin = u.pin_code || '';
      return `
        <tr class="border-b border-slate-100">
          <td class="py-2">${escapeHtml(u.username)}</td>
          <td class="py-2">${escapeHtml(u.role)}</td>
          <td class="py-2 font-medium">${escapeHtml(pin)}</td>
          <td class="py-2 text-right">
            <button type="button" class="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded border border-slate-200 text-sm" data-edit-user-id="${u.id}">
              Edit
            </button>
          </td>
        </tr>
      `;
    })
    .join('');

  tbody.querySelectorAll('[data-edit-user-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.dataset.editUserId, 10);
      const user = usersState.find((x) => x.id === id);
      if (user) {
        selectedUserId = user.id;
        document.getElementById('user-id').value = user.id;
        document.getElementById('user-username').value = user.username || '';
        document.getElementById('user-role').value = user.role || 'waiter';
        document.getElementById('user-pin').value = user.pin_code || '';
        document.getElementById('user-form-title').textContent = 'Edit User';
        document.getElementById('btn-delete-user').classList.remove('hidden');
        renderUserPinValidationState();
      }
    });
  });
}

function resetUserForm() {
  selectedUserId = null;
  const userIdEl = document.getElementById('user-id');
  if (userIdEl) userIdEl.value = '';
  const titleEl = document.getElementById('user-form-title');
  if (titleEl) titleEl.textContent = 'Create User';
  const deleteBtn = document.getElementById('btn-delete-user');
  if (deleteBtn) deleteBtn.classList.add('hidden');
  const usernameEl = document.getElementById('user-username');
  const roleEl = document.getElementById('user-role');
  const pinEl = document.getElementById('user-pin');
  const pinWarningEl = document.getElementById('user-pin-warning');
  if (usernameEl) usernameEl.value = '';
  if (roleEl) roleEl.value = 'waiter';
  if (pinEl) pinEl.value = '';
  if (pinWarningEl) pinWarningEl.classList.add('hidden');
  if (pinEl) {
    pinEl.classList.remove('border-rose-500', 'focus:ring-rose-500', 'focus:border-rose-500');
    pinEl.classList.add('border-slate-300', 'focus:ring-blue-500', 'focus:border-blue-500');
  }
}

function validateUserPinInput(raw) {
  const cleaned = (raw || '').trim();
  return /^\d{4}$/.test(cleaned);
}

function renderUserPinValidationState() {
  const pinEl = document.getElementById('user-pin');
  const warningEl = document.getElementById('user-pin-warning');
  if (!pinEl) return true;
  const isValid = validateUserPinInput(pinEl.value);
  if (isValid) {
    if (warningEl) warningEl.classList.add('hidden');
    pinEl.classList.remove('border-rose-500', 'focus:ring-rose-500', 'focus:border-rose-500');
    pinEl.classList.add('border-slate-300', 'focus:ring-blue-500', 'focus:border-blue-500');
  } else {
    if (warningEl) warningEl.classList.remove('hidden');
    pinEl.classList.remove('border-slate-300', 'focus:ring-blue-500', 'focus:border-blue-500');
    pinEl.classList.add('border-rose-500', 'focus:ring-rose-500', 'focus:border-rose-500');
  }
  return isValid;
}

async function loadUsers() {
  try {
    const users = await fetchUsers();
    renderUsers(users);
  } catch (e) {
    console.error(e);
    const tbody = document.getElementById('users-table-body');
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="py-3 text-red-600">Error loading users.</td></tr>';
  }
}

// Bind User Management UI
const userForm = document.getElementById('user-form');
if (userForm) {
  const pinEl = document.getElementById('user-pin');
  if (pinEl) {
    pinEl.addEventListener('input', () => {
      // Keep only digits to improve mobile keyboard UX.
      pinEl.value = (pinEl.value || '').replace(/\D/g, '').slice(0, 4);
      renderUserPinValidationState();
    });
    pinEl.addEventListener('blur', () => {
      renderUserPinValidationState();
    });
  }

  userForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userId = document.getElementById('user-id').value;
    const username = document.getElementById('user-username').value.trim().toLowerCase();
    const role = document.getElementById('user-role').value;
    const pin = document.getElementById('user-pin').value.trim();

    if (!username) {
      if (window.toast) window.toast.error('Username is required.');
      return;
    }
    if (!renderUserPinValidationState() || !pin) {
      if (window.toast) window.toast.error('PIN must be exactly 4 digits.');
      return;
    }

    const method = userId ? 'PUT' : 'POST';
    const url = userId
      ? `${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`
      : `${API_BASE}/api/admin/users`;

    const payload = { username, role, pin_code: pin };

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify(payload),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (window.toast) window.toast.error(data.detail || 'Failed to save user');
        else alert(data.detail || 'Failed to save user');
        return;
      }
      if (window.toast) window.toast.success('User saved successfully.');
      resetUserForm();
      await loadUsers();
    } catch (err) {
      console.error(err);
      if (window.toast) window.toast.error('Failed to save user');
      else alert('Failed to save user');
    }
  });
}

const btnDeleteUser = document.getElementById('btn-delete-user');
if (btnDeleteUser) {
  btnDeleteUser.addEventListener('click', async () => {
    const userId = document.getElementById('user-id').value;
    if (!userId) return;
    const ok = confirm('Delete this user?');
    if (!ok) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
        method: 'DELETE',
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (window.toast) window.toast.error(data.detail || 'Delete failed');
        else alert(data.detail || 'Delete failed');
        return;
      }
      if (window.toast) window.toast.success('User deleted.');
      resetUserForm();
      await loadUsers();
    } catch (e) {
      console.error(e);
      if (window.toast) window.toast.error('Delete failed');
      else alert('Delete failed');
    }
  });
}

const btnResetUser = document.getElementById('btn-reset-user');
if (btnResetUser) {
  btnResetUser.addEventListener('click', () => resetUserForm());
}

// —— Admin Table Management (Zones + Tables) ——
let zonesState = [];
let addTableZoneId = null;

async function fetchTableGrid() {
  const res = await fetch(`${API_BASE}/api/tables/grid`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch table grid');
  return data;
}

function tableDisplayName(t) {
  return t.name || t.name_or_number || `#${t.id}`;
}

function renderTableKanbanBoard(zones) {
  zonesState = zones || [];
  const board = document.getElementById('kanban-zones-board');
  if (!board) return;
  if (!zonesState.length) {
    board.innerHTML = '<div class="bg-slate-100 rounded-lg p-3 border border-slate-200 text-slate-500">No zones yet.</div>';
    return;
  }

  board.innerHTML = zonesState.map((zone) => {
    const tables = zone.tables || [];
    const addMode = addTableZoneId === zone.id;
    return `
      <div class="bg-slate-100 rounded-lg p-2.5 border border-slate-200">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-slate-800 text-sm truncate pr-2">${escapeHtml(zone.name)}</h3>
          <button type="button" data-delete-zone-id="${zone.id}" class="w-6 h-6 rounded bg-rose-100 text-rose-700 hover:bg-rose-200 text-xs shrink-0" title="Delete zone">✕</button>
        </div>
        <div class="space-y-2">
          ${
            tables.length
              ? tables.map((table) => `
                <div class="bg-white border border-slate-200 rounded-md px-2 py-1.5 flex items-center justify-between">
                  <span class="text-xs font-medium text-slate-800 truncate pr-2">${escapeHtml(tableDisplayName(table))}</span>
                  <button type="button" data-delete-table-id="${table.id}" class="w-6 h-6 rounded bg-rose-100 text-rose-700 hover:bg-rose-200 text-xs" title="Delete table">✕</button>
                </div>
              `).join('')
              : '<p class="text-xs text-slate-500">No tables in this zone.</p>'
          }
        </div>
        <div class="mt-3">
          ${
            addMode
              ? `
                <div class="space-y-2">
                  <input type="text" data-add-table-input-id="${zone.id}" placeholder="Table name"
                    class="w-full px-2 py-1.5 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                  <div class="flex gap-2">
                    <button type="button" data-save-table-zone-id="${zone.id}" class="px-2 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
                    <button type="button" data-cancel-table-zone-id="${zone.id}" class="px-2 py-1.5 text-xs bg-slate-200 text-slate-800 rounded hover:bg-slate-300">Cancel</button>
                  </div>
                </div>
              `
              : `<button type="button" data-open-add-table-zone-id="${zone.id}" class="w-full px-2 py-2 text-sm border border-dashed border-slate-400 text-slate-700 rounded hover:bg-slate-200">[+] Add Table</button>`
          }
        </div>
      </div>
    `;
  }).join('');
}

async function loadTableManagementData() {
  try {
    const zones = await fetchTableGrid();
    renderTableKanbanBoard(zones);
  } catch (e) {
    console.error(e);
    const board = document.getElementById('kanban-zones-board');
    if (board) board.innerHTML = `<div class="min-w-[280px] bg-slate-100 rounded-lg p-3 border border-slate-200 text-red-600">${escapeHtml(e.message || 'Error loading table grid.')}</div>`;
  }
}

const kanbanZoneForm = document.getElementById('kanban-zone-form');
if (kanbanZoneForm) {
  kanbanZoneForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const zoneNameInput = document.getElementById('kanban-zone-name');
    const zoneName = (zoneNameInput && zoneNameInput.value || '').trim();
    if (!zoneName) return;
    try {
      const res = await fetch(`${API_BASE}/api/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ name: zoneName }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (window.toast) window.toast.error(data.detail || 'Failed to create zone');
        else alert(data.detail || 'Failed to create zone');
        return;
      }
      if (window.toast) window.toast.success('Zone created.');
      zoneNameInput.value = '';
      await loadTableManagementData();
    } catch (err) {
      console.error(err);
      if (window.toast) window.toast.error('Failed to create zone');
      else alert('Failed to create zone');
    }
  });
}

const kanbanBoard = document.getElementById('kanban-zones-board');
if (kanbanBoard) {
  kanbanBoard.addEventListener('click', async (e) => {
    const target = e.target;
    const deleteZoneBtn = target.closest('[data-delete-zone-id]');
    const deleteTableBtn = target.closest('[data-delete-table-id]');
    const openAddBtn = target.closest('[data-open-add-table-zone-id]');
    const cancelAddBtn = target.closest('[data-cancel-table-zone-id]');
    const saveTableBtn = target.closest('[data-save-table-zone-id]');

    if (deleteZoneBtn) {
      const zoneId = deleteZoneBtn.getAttribute('data-delete-zone-id');
      if (!zoneId) return;
      if (!confirm('Delete this zone and its tables?')) return;
      try {
        const res = await fetch(`${API_BASE}/api/zones/${encodeURIComponent(zoneId)}`, {
          method: 'DELETE',
          headers: { ...window.auth.getAuthHeaders() },
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (window.toast) window.toast.error(data.detail || 'Delete failed');
          else alert(data.detail || 'Delete failed');
          return;
        }
        if (window.toast) window.toast.success('Zone deleted.');
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        if (window.toast) window.toast.error('Delete failed');
        else alert('Delete failed');
      }
      return;
    }

    if (deleteTableBtn) {
      const tableId = deleteTableBtn.getAttribute('data-delete-table-id');
      if (!tableId) return;
      if (!confirm('Delete this table?')) return;
      try {
        const res = await fetch(`${API_BASE}/api/tables/${encodeURIComponent(tableId)}`, {
          method: 'DELETE',
          headers: { ...window.auth.getAuthHeaders() },
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (window.toast) window.toast.error(data.detail || 'Delete failed');
          else alert(data.detail || 'Delete failed');
          return;
        }
        if (window.toast) window.toast.success('Table deleted.');
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        if (window.toast) window.toast.error('Delete failed');
        else alert('Delete failed');
      }
      return;
    }

    if (openAddBtn) {
      addTableZoneId = Number(openAddBtn.getAttribute('data-open-add-table-zone-id'));
      renderTableKanbanBoard(zonesState);
      const input = document.querySelector(`[data-add-table-input-id="${addTableZoneId}"]`);
      if (input) input.focus();
      return;
    }

    if (cancelAddBtn) {
      addTableZoneId = null;
      renderTableKanbanBoard(zonesState);
      return;
    }

    if (saveTableBtn) {
      const zoneId = Number(saveTableBtn.getAttribute('data-save-table-zone-id'));
      const input = document.querySelector(`[data-add-table-input-id="${zoneId}"]`);
      const tableName = (input && input.value || '').trim();
      if (!tableName) {
        if (window.toast) window.toast.error('Please enter table name.');
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/tables`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
          body: JSON.stringify({ name: tableName, zone_id: zoneId }),
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (window.toast) window.toast.error(data.detail || 'Failed to create table');
          else alert(data.detail || 'Failed to create table');
          return;
        }
        if (window.toast) window.toast.success('Table created.');
        addTableZoneId = null;
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        if (window.toast) window.toast.error('Failed to create table');
        else alert('Failed to create table');
      }
    }
  });

  kanbanBoard.addEventListener('keydown', async (e) => {
    const input = e.target;
    if (!input || !input.matches || !input.matches('[data-add-table-input-id]')) return;
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const zoneId = Number(input.getAttribute('data-add-table-input-id'));
    const tableName = (input.value || '').trim();
    if (!tableName) return;
    try {
      const res = await fetch(`${API_BASE}/api/tables`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ name: tableName, zone_id: zoneId }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (window.toast) window.toast.error(data.detail || 'Failed to create table');
        else alert(data.detail || 'Failed to create table');
        return;
      }
      if (window.toast) window.toast.success('Table created.');
      addTableZoneId = null;
      await loadTableManagementData();
    } catch (err) {
      console.error(err);
      if (window.toast) window.toast.error('Failed to create table');
      else alert('Failed to create table');
    }
  });
}

async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
}

async function toggleMenuItemAvailability(itemId) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}/toggle-availability`, {
    method: 'PUT',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Failed to update availability');
  if (window.toast) {
    window.toast.success(
      data.is_available === false ? 'Item marked Sold Out.' : 'Item enabled for ordering.'
    );
  }
  return data;
}

async function deleteMenuItem(itemId) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}`, {
    method: 'DELETE',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Failed to delete menu item');
  if (window.toast) window.toast.success('Menu item deleted.');
  return data;
}

function renderCategories(categories) {
  const el = document.getElementById('categories-list');
  if (!categories.length) {
    el.innerHTML = '<li class="text-slate-500">No categories yet.</li>';
    return;
  }
  el.innerHTML = categories.map((c) => `<li class="py-1">${escapeHtml(c.name)}</li>`).join('');
}

function renderMenuItems(items) {
  const el = document.getElementById('menu-items-list');
  if (!items.length) {
    el.innerHTML = '<li class="text-slate-500">No menu items yet.</li>';
    return;
  }
  el.innerHTML = items
    .map((m) => {
      const img = m.image_url
        ? `<img src="${escapeAttr(m.image_url)}" alt="" class="w-10 h-10 object-cover rounded inline-block mr-2 align-middle" />`
        : '';
      const available = m.is_available !== false;
      const badge = available
        ? '<span class="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Available</span>'
        : '<span class="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Sold Out</span>';
      const btnLabel = available ? 'Disable' : 'Enable';
      const btnClass = available
        ? 'bg-red-600 hover:bg-red-700'
        : 'bg-emerald-600 hover:bg-emerald-700';
      return `
        <li class="py-2 flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 min-w-0">
            ${img}
            <span class="truncate">${escapeHtml(m.name)} — $${Number(m.price).toFixed(2)}</span>
            ${badge}
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              data-toggle-availability-id="${m.id}"
              class="text-xs text-white px-3 py-1 rounded ${btnClass}"
            >
              ${btnLabel}
            </button>
            <button
              type="button"
              data-delete-menu-item-id="${m.id}"
              class="text-xs text-white px-3 py-1 rounded bg-slate-700 hover:bg-slate-800"
            >
              Delete
            </button>
          </div>
        </li>
      `;
    })
    .join('');

  el.querySelectorAll('[data-toggle-availability-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = Number(btn.getAttribute('data-toggle-availability-id'));
      if (!itemId) return;
      btn.disabled = true;
      try {
        await toggleMenuItemAvailability(itemId);
        await loadMenuData();
      } catch (err) {
        console.error(err);
        if (window.toast) window.toast.error(err.message || 'Failed to update availability');
        else alert(err.message || 'Failed to update availability');
        btn.disabled = false;
      }
    });
  });

  el.querySelectorAll('[data-delete-menu-item-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = Number(btn.getAttribute('data-delete-menu-item-id'));
      if (!itemId) return;
      const confirmed = window.confirm('Delete this menu item permanently?');
      if (!confirmed) return;
      btn.disabled = true;
      try {
        await deleteMenuItem(itemId);
        await loadMenuData();
      } catch (err) {
        console.error(err);
        if (window.toast) window.toast.error(err.message || 'Failed to delete menu item');
        else alert(err.message || 'Failed to delete menu item');
        btn.disabled = false;
      }
    });
  });
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
}

function createModifierOptionRow(groupEl, option = {}) {
  const optionsContainer = groupEl.querySelector('[data-modifier-options-container]');
  if (!optionsContainer) return;
  const row = document.createElement('div');
  row.className = 'grid grid-cols-12 gap-2 items-center';
  row.innerHTML = `
    <input
      type="text"
      data-modifier-option-name
      placeholder="Option name (e.g. Duck Egg)"
      value="${escapeAttr(option.name || '')}"
      class="col-span-7 px-2 py-1.5 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
    />
    <input
      type="number"
      data-modifier-option-price
      min="0"
      step="0.01"
      value="${Number(option.price || 0)}"
      class="col-span-4 px-2 py-1.5 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
    />
    <button type="button" data-remove-modifier-option class="col-span-1 text-xs px-2 py-1.5 rounded bg-rose-100 text-rose-700 hover:bg-rose-200">x</button>
  `;
  row.querySelector('[data-remove-modifier-option]')?.addEventListener('click', () => {
    row.remove();
    if (!optionsContainer.querySelector('[data-modifier-option-name]')) {
      createModifierOptionRow(groupEl, { name: '', price: 0 });
    }
  });
  optionsContainer.appendChild(row);
}

function createModifierGroupBlock(group = {}) {
  const container = document.getElementById('modifier-groups-builder');
  if (!container) return;
  if (container.querySelector('p')) container.innerHTML = '';
  const groupEl = document.createElement('div');
  groupEl.className = 'border border-slate-200 rounded-md p-3 space-y-2';
  groupEl.innerHTML = `
    <div class="flex items-center justify-between gap-2">
      <input
        type="text"
        data-modifier-group-name
        placeholder="Group name (e.g. Add-ons, Sweetness)"
        value="${escapeAttr(group.group || '')}"
        class="flex-1 px-2 py-1.5 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      <label class="text-xs text-slate-700 flex items-center gap-1">
        <input type="checkbox" data-modifier-group-required ${group.is_required ? 'checked' : ''} />
        Required
      </label>
      <button type="button" data-remove-modifier-group class="text-xs px-2 py-1.5 rounded bg-rose-100 text-rose-700 hover:bg-rose-200">Remove</button>
    </div>
    <div class="space-y-2" data-modifier-options-container></div>
    <button type="button" data-add-modifier-option class="text-xs px-2 py-1.5 rounded bg-slate-100 text-slate-700 hover:bg-slate-200">+ Add Option</button>
  `;
  groupEl.querySelector('[data-add-modifier-option]')?.addEventListener('click', () => {
    createModifierOptionRow(groupEl, { name: '', price: 0 });
  });
  groupEl.querySelector('[data-remove-modifier-group]')?.addEventListener('click', () => {
    groupEl.remove();
    if (!container.querySelector('[data-modifier-group-name]')) {
      container.innerHTML = '<p class="text-xs text-slate-500">No modifier groups yet.</p>';
    }
  });
  container.appendChild(groupEl);

  const options = Array.isArray(group.options) && group.options.length ? group.options : [{ name: '', price: 0 }];
  options.forEach((opt) => createModifierOptionRow(groupEl, opt));
}

function collectModifiersConfigFromBuilder() {
  const groups = [];
  document.querySelectorAll('#modifier-groups-builder [data-modifier-group-name]').forEach((input) => {
    const groupEl = input.closest('.border');
    if (!groupEl) return;
    const groupName = (input.value || '').trim();
    const isRequired = !!groupEl.querySelector('[data-modifier-group-required]')?.checked;
    const options = [];
    groupEl.querySelectorAll('[data-modifier-option-name]').forEach((nameInput) => {
      const row = nameInput.closest('.grid');
      const optionName = (nameInput.value || '').trim();
      const priceInput = row?.querySelector('[data-modifier-option-price]');
      const price = Number(priceInput?.value || 0);
      if (!optionName) return;
      options.push({ name: optionName, price: Number.isFinite(price) ? price : 0 });
    });
    if (!groupName || !options.length) return;
    groups.push({ group: groupName, is_required: isRequired, options });
  });
  return groups;
}

function resetModifiersBuilder() {
  const container = document.getElementById('modifier-groups-builder');
  if (container) container.innerHTML = '<p class="text-xs text-slate-500">No modifier groups yet.</p>';
}

function bindModifiersBuilderEvents() {
  const addGroupBtn = document.getElementById('btn-add-modifier-group');
  if (!addGroupBtn) return;
  addGroupBtn.addEventListener('click', () => createModifierGroupBlock());
}

function populateCategorySelect(categories) {
  const select = document.getElementById('item-category');
  const currentValue = select.value;
  select.innerHTML = '<option value="">Select category</option>';
  categories.forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });
  if (currentValue) select.value = currentValue;
}

async function loadMenuData() {
  try {
    const [categories, menuItems] = await Promise.all([fetchCategories(), fetchMenuItems()]);
    renderCategories(categories);
    renderMenuItems(menuItems);
    populateCategorySelect(categories);
  } catch (e) {
    console.error(e);
    document.getElementById('categories-list').innerHTML = '<li class="text-red-600">Error loading categories.</li>';
    document.getElementById('menu-items-list').innerHTML = '<li class="text-red-600">Error loading menu items.</li>';
  }
}

document.getElementById('form-category').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('category-name');
  const name = input.value.trim();
  if (!name) return;
  try {
    const res = await fetch(`${API_BASE}/api/categories/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify({ name }),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Failed to create category');
      return;
    }
    input.value = '';
    await loadMenuData();
  } catch (err) {
    console.error(err);
    alert('Failed to create category');
  }
});

document.getElementById('item-image-file').addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      headers: { ...window.auth.getAuthHeaders() },
      body: fd,
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Upload failed');
      return;
    }
    document.getElementById('item-image-url').value = data.url || '';
  } catch (err) {
    console.error(err);
    alert('Upload failed');
  }
  e.target.value = '';
});

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('item-name').value.trim();
  const price = parseFloat(document.getElementById('item-price').value);
  const description = document.getElementById('item-description').value.trim() || null;
  const categoryId = document.getElementById('item-category').value;
  const imageUrl = document.getElementById('item-image-url').value.trim() || null;
  const imageFile = document.getElementById('item-image-file').files?.[0];
  const modifiersConfig = collectModifiersConfigFromBuilder();
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  if (imageFile && !imageUrl) {
    if (window.toast) window.toast.error('Please wait for image upload to finish.');
    else alert('Please wait for image upload to finish.');
    return;
  }
  const btn = document.getElementById('btn-submit-menu-item');
  btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/menu-items/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify({
        name,
        price,
        category_id: parseInt(categoryId, 10),
        description,
        image_url: imageUrl,
        modifiers_config: modifiersConfig,
      }),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(Array.isArray(data.detail) ? data.detail.map((x) => x.msg || x).join(', ') : (data.detail || 'Failed to create menu item'));
      return;
    }
    document.getElementById('item-name').value = '';
    document.getElementById('item-price').value = '';
    document.getElementById('item-description').value = '';
    document.getElementById('item-image-url').value = '';
    document.getElementById('item-category').value = '';
    document.getElementById('item-image-file').value = '';
    resetModifiersBuilder();
    await loadMenuData();
  } catch (err) {
    console.error(err);
    alert('Failed to create menu item');
  } finally {
    btn.disabled = false;
  }
});

// —— Live updates via WebSocket (auto-refresh Cashier list when new batches arrive) ——
function connectCounterWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.event === 'new_order_batch' && msg.data) {
        // A new batch was submitted (new order or add-on). Refresh the tables list.
        loadUnpaidOrders();
        // If we are currently viewing this table, refresh the receipt too.
        const data = msg.data;
        if (selectedOrderId != null && data.order_id === selectedOrderId) {
          fetchActiveOrderByTable(data.table_id || data.table_number)
            .then((order) => selectOrder(order))
            .catch(() => {});
        }
      }
      if (msg.event === 'order_updated' && msg.data && msg.data.status) {
        // Status changes (e.g. completed) can affect which tables are active; refresh list.
        loadUnpaidOrders();
      }
      if (msg.event === 'table_status_changed') {
        // Keep admin table management view in sync with occupancy updates.
        if (panelTables && !panelTables.classList.contains('hidden')) {
          loadTableManagementData();
        }
      }
      if (
        msg.event === 'menu_item_added' ||
        msg.event === 'menu_item_availability_toggled' ||
        msg.event === 'menu_item_deleted'
      ) {
        if (panelMenu && !panelMenu.classList.contains('hidden')) {
          loadMenuData();
        }
      }
    } catch (err) {
      console.error('Counter WebSocket message error:', err);
    }
  };

  ws.onclose = () => {
    setTimeout(connectCounterWebSocket, 3000);
  };
  ws.onerror = () => {};
}

// Initial load only when authenticated (avoids 401s if redirecting to login)
if (window.auth && window.auth.getToken()) {
  bindModifiersBuilderEvents();
  loadUnpaidOrders();
  loadMenuData();
  connectCounterWebSocket();
}
