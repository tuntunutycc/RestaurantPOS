const API_BASE = '';
let kitchenMenuItems = [];
// Each entry here is a "ticket" for the kitchen: one batch of an order for a table.
let tickets = [];

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
}

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

async function fetchPendingOrders() {
  const params = new URLSearchParams([['status', 'pending'], ['status', 'open'], ['status', 'dining']]);
  const res = await fetch(`${API_BASE}/api/orders/?${params}`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

async function markOrderDone(orderId, batchNumber) {
  const res = await fetch(`${API_BASE}/api/orders/${orderId}/batches/${batchNumber}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'completed' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update order');
  }
}

function renderTicket(ticket) {
  const isAddon = (ticket.batch_number || 1) > 1;
  const card = document.createElement('div');
  card.className = isAddon
    ? 'bg-white rounded-lg shadow-md p-4 border-l-4 border-blue-500'
    : 'bg-white rounded-lg shadow-md p-4 border-l-4 border-amber-500';
  card.dataset.orderId = ticket.order_id;
  const timeStr = ticket.created_at ? formatTime(ticket.created_at) : '—';
  const headerTitle = `Table ${escapeHtml(String(ticket.table_number))} — Ticket #${ticket.batch_number || 1}`;
  const itemsList = (ticket.items || [])
    .map((item) => {
      const img = item.menu_item_image_url
        ? `<img src="${escapeAttr(item.menu_item_image_url)}" alt="" class="w-8 h-8 object-cover rounded flex-shrink-0" />`
        : '';
      return `<li class="flex items-center gap-2 text-sm text-slate-700"><span class="flex-shrink-0">${img}</span><span class="flex-1 min-w-0">${escapeHtml(item.menu_item_name)}</span><span>× ${item.quantity}</span></li>`;
    })
    .join('');
  card.innerHTML = `
    <div class="flex justify-between items-start mb-3">
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-bold text-slate-800">${headerTitle}</span>
        <span class="text-slate-500 text-sm">${timeStr}</span>
      </div>
      <span class="text-xs font-medium text-slate-500">${isAddon ? 'Add-on' : '#' + ticket.order_id}</span>
    </div>
    <ul class="space-y-1 mb-4">${itemsList}</ul>
    <button type="button" class="mark-done w-full py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700">Mark as Done</button>
  `;
  const btn = card.querySelector('.mark-done');
  if (btn) btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = '…';
    try {
      // Marks only this batch (ticket) as completed. Other batches for the same
      // table/order remain visible. KDS will update via batch_completed event.
      await markOrderDone(ticket.order_id, ticket.batch_number || 1);
    } catch (e) {
      console.error(e);
      btn.disabled = false;
      btn.textContent = 'Mark as Done';
    }
  });
  return card;
}

function renderOrders(ticketsList) {
  const grid = document.getElementById('tickets-grid');
  if (!ticketsList || ticketsList.length === 0) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No pending orders.</p>';
    return;
  }
  grid.innerHTML = '';
  ticketsList.forEach((t) => grid.appendChild(renderTicket(t)));
}

async function loadAndRender() {
  try {
    const orders = await fetchPendingOrders();
    // Expand each order into one ticket per batch_number so the kitchen sees separate rounds.
    const nextTickets = [];
    orders.forEach((order) => {
      const byBatch = new Map();
      (order.items || []).forEach((item) => {
        // Only show items from batches that are not completed.
        if (item.batch_status && item.batch_status !== 'pending') return;
        const batch = item.batch_number || 1;
        if (!byBatch.has(batch)) byBatch.set(batch, []);
        byBatch.get(batch).push(item);
      });
      byBatch.forEach((items, batch) => {
        nextTickets.push({
          ticket_id: `order-${order.id}-batch-${batch}`,
          order_id: order.id,
          table_number: order.table_number,
          batch_number: batch,
          created_at: order.created_at,
          items,
        });
      });
    });
    // Newest tickets first by created_at, then batch_number
    nextTickets.sort((a, b) => {
      if (a.created_at === b.created_at) return b.batch_number - a.batch_number;
      return new Date(b.created_at) - new Date(a.created_at);
    });
    tickets = nextTickets;
    renderOrders(tickets);
  } catch (e) {
    console.error(e);
    document.getElementById('tickets-grid').innerHTML =
      '<p class="col-span-full text-red-600">Error loading orders.</p>';
  }
}

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`);
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
}

function renderKitchenMenu() {
  const el = document.getElementById('kitchen-menu-list');
  if (!kitchenMenuItems.length) {
    el.innerHTML = '<li class="text-slate-500">No menu items.</li>';
    return;
  }
  el.innerHTML = kitchenMenuItems
    .map((m) => {
      const img = m.image_url
        ? `<img src="${escapeAttr(m.image_url)}" alt="" class="w-8 h-8 object-cover rounded inline-block mr-1 align-middle" />`
        : '';
      return `<li class="inline-flex items-center gap-1 px-2 py-1 bg-white rounded shadow text-sm text-slate-700">${img}${escapeHtml(m.name)}</li>`;
    })
    .join('');
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.event === 'menu_item_added' && msg.data) {
        const item = msg.data;
        if (!kitchenMenuItems.some((x) => x.id === item.id)) {
          kitchenMenuItems.push({
            id: item.id,
            name: item.name,
            price: item.price,
            image_url: item.image_url ?? null,
          });
          renderKitchenMenu();
        }
      }
      if (msg.event === 'new_order_batch' && msg.data) {
        // Whenever the waiter submits an order (new or add-on), reload all
        // pending/open/dining orders from the backend and rebuild tickets.
        // This guarantees the Kitchen board reflects every batch, even if
        // multiple batches exist for the same table.
        loadAndRender();
      }
      if (msg.event === 'batch_completed' && msg.data) {
        // Remove only the specific ticket (order_id + batch_number) that was marked done.
        const data = msg.data;
        tickets = tickets.filter(
          (t) => !(t.order_id === data.order_id && t.batch_number === data.batch_number),
        );
        renderOrders(tickets);
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 3000);
  ws.onerror = () => {};
}
connectWebSocket();

async function init() {
  await loadAndRender();
  try {
    kitchenMenuItems = await fetchMenuItems();
    renderKitchenMenu();
  } catch (e) {
    document.getElementById('kitchen-menu-list').innerHTML = '<li class="text-red-600">Error loading menu.</li>';
  }
}

init();
