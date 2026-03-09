const API_BASE = '';

// —— Tab switching ——
const tabCashier = document.getElementById('tab-cashier');
const tabMenu = document.getElementById('tab-menu');
const panelCashier = document.getElementById('panel-cashier');
const panelMenu = document.getElementById('panel-menu');

function showPanel(panel) {
  panelCashier.classList.add('hidden');
  panelMenu.classList.add('hidden');
  tabCashier.classList.remove('border-blue-600', 'text-blue-600');
  tabCashier.classList.add('border-transparent', 'text-slate-600');
  tabMenu.classList.remove('border-blue-600', 'text-blue-600');
  tabMenu.classList.add('border-transparent', 'text-slate-600');
  panel.classList.remove('hidden');
  if (panel === panelCashier) {
    tabCashier.classList.add('border-blue-600', 'text-blue-600');
    loadUnpaidOrders();
  } else {
    tabMenu.classList.add('border-blue-600', 'text-blue-600');
    loadMenuData();
  }
}

tabCashier.addEventListener('click', () => showPanel(panelCashier));
tabMenu.addEventListener('click', () => showPanel(panelMenu));

// —— Cashier / Billing (table-centric: one active order per table, consolidated items + grand total) ——
let selectedOrderId = null;
let selectedTableNumber = null;
let selectedOrderTotal = 0;

/** Fetch one canonical order per table (consolidated for Cashier). */
async function fetchOrdersByTable() {
  const res = await fetch(`${API_BASE}/api/orders/tables`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

async function fetchActiveOrderByTable(tableId) {
  const res = await fetch(`${API_BASE}/api/orders/active-by-table/${tableId}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `No active order for table ${tableId}`);
  }
  return res.json();
}

function loadUnpaidOrders() {
  const list = document.getElementById('orders-list');
  list.innerHTML = '<li class="text-slate-500">Loading…</li>';
  fetchOrdersByTable()
    .then((orders) => {
      if (!orders.length) {
        list.innerHTML = '<li class="text-slate-500">No active orders.</li>';
        return;
      }
      // Backend returns one order per table (canonical = all items + grand total).
      list.innerHTML = orders
        .map(
          (o) =>
            `<li><button type="button" class="order-row w-full text-left px-3 py-2 rounded bg-white shadow border border-slate-200 hover:bg-slate-50" data-table-id="${o.table_number}">Table ${escapeHtml(String(o.table_number))}</button></li>`
        )
        .join('');
      list.querySelectorAll('.order-row').forEach((btn) => {
        const tableId = parseInt(btn.dataset.tableId, 10);
        btn.addEventListener('click', async () => {
          try {
            const order = await fetchActiveOrderByTable(tableId);
            selectOrder(order);
          } catch (e) {
            if (window.toast) window.toast.error(e.message);
            else alert(e.message);
          }
        });
      });
    })
    .catch((e) => {
      console.error(e);
      list.innerHTML = '<li class="text-red-600">Error loading orders.</li>';
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
  // Reset payment inputs for this order
  const amountInput = document.getElementById('amount-tendered');
  const changeSpan = document.getElementById('change-amount');
  const methodSelect = document.getElementById('payment-method');
  if (amountInput) amountInput.value = '';
  if (changeSpan) changeSpan.textContent = '$0.00';
  if (methodSelect) methodSelect.value = 'cash';
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
  const tableNumberJustPaid = selectedTableNumber;
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ payment_method: method, amount_tendered: tendered }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (window.toast) window.toast.error(data.detail || 'Payment failed');
      else alert(data.detail || 'Payment failed');
      return;
    }
    if (window.toast) window.toast.success('Payment processed successfully.');
    else alert('Payment processed successfully.');
    selectedOrderId = null;
    selectedTableNumber = null;
    selectedOrderTotal = 0;
    document.getElementById('receipt-container').classList.add('hidden');
    document.getElementById('receipt-placeholder').classList.remove('hidden');
    // Optimistically hide this table from the list so it disappears immediately.
    if (tableNumberJustPaid != null) {
      const list = document.getElementById('orders-list');
      const btnNode = list.querySelector(
        `.order-row[data-table-id="${tableNumberJustPaid}"]`,
      );
      if (btnNode && btnNode.parentElement) {
        btnNode.parentElement.remove();
      }
      if (!list.querySelector('.order-row')) {
        list.innerHTML = '<li class="text-slate-500">No active orders.</li>';
      }
    }
    // Also reload from backend to stay in sync in case of concurrent changes.
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

async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories/`);
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`);
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
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
      return `<li class="py-2 flex items-center gap-2">${img}<span>${escapeHtml(m.name)} — $${Number(m.price).toFixed(2)}</span></li>`;
    })
    .join('');
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
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
    const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: fd });
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
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  const btn = document.getElementById('btn-submit-menu-item');
  btn.disabled = true;
  try {
    let res;
    if (imageFile) {
      const fd = new FormData();
      fd.append('name', name);
      fd.append('price', String(price));
      fd.append('category_id', categoryId);
      if (description) fd.append('description', description);
      fd.append('image', imageFile);
      res = await fetch(`${API_BASE}/api/menu-items/upload`, { method: 'POST', body: fd });
    } else {
      res = await fetch(`${API_BASE}/api/menu-items/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, price, category_id: parseInt(categoryId, 10), description: description, image_url: imageUrl }),
      });
    }
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
          fetchActiveOrderByTable(data.table_number)
            .then((order) => selectOrder(order))
            .catch(() => {});
        }
      }
      if (msg.event === 'order_updated' && msg.data && msg.data.status) {
        // Status changes (e.g. completed) can affect which tables are active; refresh list.
        loadUnpaidOrders();
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

// Initial load
loadUnpaidOrders();
loadMenuData();
connectCounterWebSocket();
