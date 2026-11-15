(function () {
  const API_BASE = '';
  /** @type {Record<number, any>} */
  let ordersById = {};

  (function guard() {
    if (!window.auth) return;
    if (!window.auth.requireAuth()) return;
    if (!window.auth.requireRole(['root', 'admin', 'cashier'])) return;
    window.auth.renderNav('pos-nav');
    window.auth.consumeUnauthorizedFlag();
  })();

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function formatMoney(n) {
    if (window.formatMoney) return window.formatMoney(Number(n) || 0);
    return Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function todayIsoDate() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString();
  }

  function selectedDate() {
    const el = document.getElementById('history-date');
    return (el?.value || '').trim();
  }

  async function loadHistory() {
    const date = selectedDate();
    const body = document.getElementById('history-orders-body');
    if (!date) {
      if (window.toast?.error) window.toast.error('Pick a date first.');
      return;
    }
    if (body) {
      body.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-slate-500 text-center">Loading…</td></tr>';
    }
    try {
      const res = await fetch(`${API_BASE}/api/orders/daily-history?date=${encodeURIComponent(date)}`, {
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (window.auth?.checkUnauthorized?.(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.detail || 'Failed to load order history';
        if (window.toast?.error) window.toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        if (body) body.innerHTML = `<tr><td colspan="4" class="px-4 py-6 text-red-600 text-center">${escapeHtml(String(msg))}</td></tr>`;
        return;
      }
      renderHistory(data);
    } catch (err) {
      console.error(err);
      if (window.toast?.error) window.toast.error('Failed to load order history');
      if (body) body.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-red-600 text-center">Failed to load.</td></tr>';
    }
  }

  function renderHistory(data) {
    ordersById = {};
    const orders = Array.isArray(data?.orders) ? data.orders : [];
    orders.forEach((o) => {
      ordersById[Number(o.id)] = o;
    });
    const countEl = document.getElementById('history-order-count');
    const totalEl = document.getElementById('history-grand-total');
    if (countEl) countEl.textContent = String(data.order_count ?? orders.length);
    if (totalEl) totalEl.textContent = formatMoney(data.grand_total ?? 0);

    const body = document.getElementById('history-orders-body');
    if (!body) return;
    if (!orders.length) {
      body.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-slate-500 text-center">No paid orders for this day.</td></tr>';
      return;
    }
    body.innerHTML = orders
      .map((o) => `
        <tr class="border-b border-slate-100 hover:bg-slate-50">
          <td class="px-4 py-2 font-medium">#${escapeHtml(o.id)}</td>
          <td class="px-4 py-2">${escapeHtml(formatTime(o.created_at))}</td>
          <td class="px-4 py-2 text-right">${escapeHtml(formatMoney(o.total_amount))}</td>
          <td class="px-4 py-2 text-right">
            <button type="button" data-view-order-id="${o.id}"
              class="px-3 py-1 text-xs font-medium rounded bg-slate-800 text-white hover:bg-slate-900">
              View Details
            </button>
          </td>
        </tr>`)
      .join('');

    body.querySelectorAll('[data-view-order-id]').forEach((btn) => {
      btn.addEventListener('click', () => {
        openDetail(Number(btn.getAttribute('data-view-order-id')));
      });
    });
  }

  function openDetail(orderId) {
    const order = ordersById[orderId];
    const modal = document.getElementById('history-detail-modal');
    const title = document.getElementById('history-detail-title');
    const body = document.getElementById('history-detail-body');
    if (!order || !modal || !body) return;
    if (title) title.textContent = `Order #${order.id}`;
    const typeLabel = String(order.order_type || '').toLowerCase() === 'takeaway' ? 'Takeaway' : 'Dine-in';
    const meta = [
      `<p><span class="text-slate-500">Time:</span> ${escapeHtml(formatTime(order.created_at))}</p>`,
      `<p><span class="text-slate-500">Type:</span> ${escapeHtml(typeLabel)}</p>`,
      order.customer_name ? `<p><span class="text-slate-500">Customer:</span> ${escapeHtml(order.customer_name)}</p>` : '',
      order.payment_method ? `<p><span class="text-slate-500">Payment:</span> ${escapeHtml(order.payment_method)}</p>` : '',
      `<p><span class="text-slate-500">Total:</span> <strong>${escapeHtml(formatMoney(order.total_amount))}</strong></p>`,
    ].join('');

    const items = Array.isArray(order.items) ? order.items : [];
    const itemsHtml = items.length
      ? items
          .map((item) => {
            const takeaway = item.is_takeaway
              ? '<span class="ml-2 text-[11px] font-semibold px-1.5 py-0.5 rounded bg-orange-100 text-orange-800">🛍️ ပါဆယ်</span>'
              : '';
            const mods = Array.isArray(item.selected_modifiers) ? item.selected_modifiers : [];
            const modsHtml = mods.length
              ? `<ul class="mt-1 text-xs text-slate-500 space-y-0.5">${mods
                  .map((m) => {
                    const q = Math.max(1, Math.floor(Number(m?.quantity) || 1));
                    const label = q > 1 ? `+ ${escapeHtml(m?.name || '')} ×${q}` : `+ ${escapeHtml(m?.name || '')}`;
                    const price = Number(m?.price || 0);
                    return `<li>${label}${price ? ` (${escapeHtml(formatMoney(price * q))})` : ''}</li>`;
                  })
                  .join('')}</ul>`
              : '';
            const note = item.note
              ? `<p class="mt-1 text-xs text-amber-700">Note: ${escapeHtml(item.note)}</p>`
              : '';
            return `
              <div class="border border-slate-200 rounded-md p-3">
                <div class="flex justify-between gap-2">
                  <div class="font-medium text-slate-800">${escapeHtml(item.menu_item_name)}${takeaway}</div>
                  <div class="text-right shrink-0">
                    <div class="text-xs text-slate-500">Qty ${escapeHtml(item.quantity)}</div>
                    <div class="font-semibold">${escapeHtml(formatMoney(item.subtotal))}</div>
                  </div>
                </div>
                ${modsHtml}
                ${note}
              </div>`;
          })
          .join('')
      : '<p class="text-slate-500">No line items.</p>';

    body.innerHTML = `${meta}<div class="pt-2 space-y-2">${itemsHtml}</div>`;
    modal.classList.remove('hidden');
  }

  function closeDetail() {
    document.getElementById('history-detail-modal')?.classList.add('hidden');
  }

  async function exportExcel() {
    const date = selectedDate();
    if (!date) {
      if (window.toast?.error) window.toast.error('Pick a date first.');
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/api/orders/daily-history/export?date=${encodeURIComponent(date)}`,
        { headers: { ...window.auth.getAuthHeaders() } }
      );
      if (window.auth?.checkUnauthorized?.(res)) return;
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = data.detail || 'Export failed';
        if (window.toast?.error) window.toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `order-history-${date}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      if (window.toast?.success) window.toast.success('Excel downloaded.');
    } catch (err) {
      console.error(err);
      if (window.toast?.error) window.toast.error('Export failed');
    }
  }

  document.getElementById('history-date').value = todayIsoDate();
  document.getElementById('btn-load-history')?.addEventListener('click', loadHistory);
  document.getElementById('btn-export-excel')?.addEventListener('click', exportExcel);
  document.getElementById('btn-close-history-detail')?.addEventListener('click', closeDetail);
  document.getElementById('history-detail-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeDetail();
  });

  if (window.auth?.getToken?.()) loadHistory();
})();
