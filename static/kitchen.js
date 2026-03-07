const API_BASE = '';
const REFRESH_INTERVAL_MS = 5000;

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

async function fetchPendingOrders() {
  const res = await fetch(`${API_BASE}/api/orders/?status=pending`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

async function markOrderDone(orderId) {
  const res = await fetch(`${API_BASE}/api/orders/${orderId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'completed' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update order');
  }
}

function renderTicket(order) {
  const card = document.createElement('div');
  card.className = 'bg-white rounded-lg shadow-md p-4 border-l-4 border-amber-500';
  card.dataset.orderId = order.id;
  const timeStr = order.created_at ? formatTime(order.created_at) : '—';
  const itemsList = (order.items || [])
    .map(
      (item) =>
        `<li class="flex justify-between text-sm text-slate-700"><span>${escapeHtml(item.menu_item_name)}</span><span>× ${item.quantity}</span></li>`
    )
    .join('');
  card.innerHTML = `
    <div class="flex justify-between items-start mb-3">
      <div>
        <span class="font-bold text-slate-800">Table ${escapeHtml(String(order.table_number))}</span>
        <span class="text-slate-500 text-sm ml-2">${timeStr}</span>
      </div>
      <span class="text-xs font-medium text-slate-500">#${order.id}</span>
    </div>
    <ul class="space-y-1 mb-4">${itemsList}</ul>
    <button type="button" class="mark-done w-full py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700">
      Mark as Done
    </button>
  `;
  const btn = card.querySelector('.mark-done');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = '…';
    try {
      await markOrderDone(order.id);
      await loadAndRender();
    } catch (e) {
      console.error(e);
      alert(e.message || 'Failed to mark order done');
      btn.disabled = false;
      btn.textContent = 'Mark as Done';
    }
  });
  return card;
}

function render(orders) {
  const grid = document.getElementById('tickets-grid');
  if (!orders || orders.length === 0) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No pending orders.</p>';
    return;
  }
  grid.innerHTML = '';
  orders.forEach((order) => grid.appendChild(renderTicket(order)));
}

async function loadAndRender() {
  try {
    const orders = await fetchPendingOrders();
    render(orders);
  } catch (e) {
    console.error(e);
    document.getElementById('tickets-grid').innerHTML =
      '<p class="col-span-full text-red-600">Error loading orders.</p>';
  }
}

let refreshTimer = null;

async function init() {
  await loadAndRender();
  refreshTimer = setInterval(loadAndRender, REFRESH_INTERVAL_MS);
}

init();
