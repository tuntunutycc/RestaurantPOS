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

// —— Cashier / Billing ——
let selectedOrderId = null;

async function fetchAllOrders() {
  const res = await fetch(`${API_BASE}/api/orders/`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

function loadUnpaidOrders() {
  const list = document.getElementById('orders-list');
  list.innerHTML = '<li class="text-slate-500">Loading…</li>';
  fetchAllOrders()
    .then((orders) => {
      const unpaid = orders.filter((o) => o.status !== 'paid');
      if (!unpaid.length) {
        list.innerHTML = '<li class="text-slate-500">No unpaid orders.</li>';
        return;
      }
      list.innerHTML = unpaid
        .map(
          (o) =>
            `<li><button type="button" class="order-row w-full text-left px-3 py-2 rounded bg-white shadow border border-slate-200 hover:bg-slate-50" data-order-id="${o.id}">Table ${escapeHtml(String(o.table_number))} — #${o.id} (${escapeHtml(o.status)})</button></li>`
        )
        .join('');
      list.querySelectorAll('.order-row').forEach((btn) => {
        btn.addEventListener('click', () => selectOrder(unpaid.find((x) => x.id === parseInt(btn.dataset.orderId, 10))));
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
  document.getElementById('receipt-placeholder').classList.add('hidden');
  const container = document.getElementById('receipt-container');
  container.classList.remove('hidden');
  const itemsRows = (order.items || [])
    .map(
      (i) =>
        `<tr><td class="py-1">${escapeHtml(i.menu_item_name)}</td><td class="py-1 text-right">${i.quantity}</td><td class="py-1 text-right">$${Number(i.subtotal).toFixed(2)}</td></tr>`
    )
    .join('');
  document.getElementById('receipt-content').innerHTML = `
    <p class="text-slate-600 mb-2"><strong>Order #${order.id}</strong></p>
    <p class="text-slate-600 mb-4">Table ${order.table_number}</p>
    <table class="w-full text-sm text-slate-700 mb-4">
      <thead><tr class="border-b border-slate-200"><th class="text-left py-1">Item</th><th class="text-right py-1">Qty</th><th class="text-right py-1">Subtotal</th></tr></thead>
      <tbody>${itemsRows}</tbody>
    </table>
    <p class="text-lg font-semibold text-slate-800 border-t border-slate-200 pt-2">Grand Total: $${Number(order.total_amount).toFixed(2)}</p>
  `;
}

document.getElementById('btn-process-payment').addEventListener('click', async () => {
  if (selectedOrderId == null) return;
  const btn = document.getElementById('btn-process-payment');
  btn.disabled = true;
  btn.textContent = 'Processing…';
  try {
    const res = await fetch(`${API_BASE}/api/orders/${selectedOrderId}/pay`, { method: 'PUT' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Payment failed');
      return;
    }
    alert('Payment processed successfully.');
    selectedOrderId = null;
    document.getElementById('receipt-container').classList.add('hidden');
    document.getElementById('receipt-placeholder').classList.remove('hidden');
    loadUnpaidOrders();
  } catch (e) {
    console.error(e);
    alert('Payment failed');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Process Payment';
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
    .map((m) => `<li class="py-1">${escapeHtml(m.name)} — $${Number(m.price).toFixed(2)}</li>`)
    .join('');
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

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('item-name').value.trim();
  const price = parseFloat(document.getElementById('item-price').value);
  const categoryId = document.getElementById('item-category').value;
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  try {
    const res = await fetch(`${API_BASE}/api/menu-items/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, price, category_id: parseInt(categoryId, 10) }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Failed to create menu item');
      return;
    }
    document.getElementById('item-name').value = '';
    document.getElementById('item-price').value = '';
    document.getElementById('item-category').value = '';
    await loadMenuData();
  } catch (err) {
    console.error(err);
    alert('Failed to create menu item');
  }
});

// Initial load
loadUnpaidOrders();
loadMenuData();
