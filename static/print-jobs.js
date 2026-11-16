/**
 * Failed-print indicator + Retry (specs/feature-print-queue, FR-PQ11).
 * Shared by the waiter and counter screens.
 *
 * - A red "Print failed (N)" button appears while failed slips exist.
 * - It opens a list grouped by order with a Retry button per order.
 * - The page's WebSocket handler forwards `print_job_updated` to
 *   window.printJobs.onEvent(); a slow poll covers a dropped socket.
 *
 * All job text is written with textContent: item and customer names are user input.
 */
(function () {
  const ALLOWED_ROLES = ['waiter', 'cashier', 'admin', 'root'];
  const REFRESH_DEBOUNCE_MS = 600;
  const POLL_MS = 60000;

  let jobs = [];
  let seenIds = new Set();
  let firstLoadDone = false;
  let refreshTimer = null;
  let button = null;
  let modal = null;
  let listEl = null;

  function tr(key, fallback) {
    const value = window.i18n?.t?.(key);
    return value && value !== key ? value : fallback;
  }

  function canUse() {
    const role = String(window.auth?.getUser?.()?.role || '').toLowerCase();
    return Boolean(window.auth?.getToken?.()) && ALLOWED_ROLES.includes(role);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function ensureDom() {
    if (button) return;
    button = el(
      'button',
      'hidden fixed bottom-4 left-4 z-[60] px-4 py-2 rounded-full shadow-lg bg-red-600 ' +
        'text-white text-sm font-semibold hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300'
    );
    button.type = 'button';
    button.id = 'print-failed-button';
    button.addEventListener('click', openModal);
    document.body.appendChild(button);

    modal = el('div', 'hidden fixed inset-0 z-[70] items-center justify-center bg-black/40 p-4');
    modal.id = 'print-failed-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeModal();
    });

    const panel = el('div', 'bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col');
    const header = el('div', 'px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-3');
    const title = el('h3', 'text-lg font-semibold text-slate-800');
    title.id = 'print-failed-title';
    const close = el('button', 'px-3 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-100 text-sm');
    close.type = 'button';
    close.id = 'print-failed-close';
    close.addEventListener('click', closeModal);
    header.append(title, close);

    listEl = el('div', 'p-4 space-y-3 overflow-y-auto');
    listEl.id = 'print-failed-list';
    panel.append(header, listEl);
    modal.appendChild(panel);
    document.body.appendChild(modal);
  }

  function openModal() {
    ensureDom();
    render();
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  function groupByOrder() {
    const groups = new Map();
    for (const job of jobs) {
      if (!groups.has(job.order_id)) groups.set(job.order_id, []);
      groups.get(job.order_id).push(job);
    }
    // The API lists newest first; inside one order show slips in the order they were sent.
    for (const orderJobs of groups.values()) orderJobs.sort((a, b) => a.id - b.id);
    return groups;
  }

  function slipLabel(job) {
    return job.kind === 'receipt' ? tr('print_receipt_label', 'Receipt') : job.item_label;
  }

  function render() {
    ensureDom();
    const count = jobs.length;
    button.textContent = `${tr('print_failed_button', 'Print failed')} (${count})`;
    button.classList.toggle('hidden', count === 0);

    modal.querySelector('#print-failed-title').textContent = tr(
      'print_failed_title',
      'Slips that did not print'
    );
    modal.querySelector('#print-failed-close').textContent = tr('close', 'Close');

    listEl.replaceChildren();
    if (count === 0) {
      listEl.appendChild(el('p', 'text-sm text-slate-500', tr('print_failed_empty', 'No failed slips')));
      return;
    }
    for (const [orderId, orderJobs] of groupByOrder()) {
      const card = el('div', 'border border-slate-200 rounded-lg p-3');
      const head = el('div', 'flex items-center justify-between gap-3 mb-2');
      const location = orderJobs.find((job) => job.location_label)?.location_label;
      const heading = `${tr('order', 'Order')} #${orderId}${location ? ` · ${location}` : ''}`;
      head.appendChild(el('div', 'font-semibold text-slate-800', heading));

      const retry = el(
        'button',
        'px-3 py-1.5 rounded bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 ' +
          'disabled:opacity-50 disabled:cursor-not-allowed',
        tr('print_retry', 'Retry')
      );
      retry.type = 'button';
      retry.dataset.orderId = String(orderId);
      retry.addEventListener('click', () => retryOrder(orderId, retry));
      head.appendChild(retry);
      card.appendChild(head);

      const lines = el('ul', 'space-y-1');
      for (const job of orderJobs) {
        const line = el('li', 'text-sm');
        line.appendChild(el('span', 'font-medium text-slate-700', slipLabel(job)));
        if (job.error_message) {
          line.appendChild(el('span', 'text-red-600', ` — ${job.error_message}`));
        }
        lines.appendChild(line);
      }
      card.appendChild(lines);
      listEl.appendChild(card);
    }
  }

  async function refresh() {
    if (!canUse()) return;
    let data;
    try {
      const res = await fetch('/api/print-jobs/failed', {
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (!res.ok) return;
      data = await res.json();
    } catch (err) {
      console.error('Failed print list error:', err);
      return;
    }
    jobs = Array.isArray(data) ? data : [];
    const fresh = jobs.filter((job) => !seenIds.has(job.id));
    seenIds = new Set(jobs.map((job) => job.id));
    render();
    if (jobs.length === 0) closeModal(); // nothing left to retry
    // One toast per burst, and none for failures that were already there on page load.
    if (firstLoadDone && fresh.length > 0 && window.toast) {
      const base = tr('print_failed_toast', 'A slip failed to print. Open "Print failed" to retry.');
      const first = fresh[0];
      const where = first.location_label ? `${first.location_label}: ` : '';
      window.toast.error(`${base} (${where}${slipLabel(first)}${fresh.length > 1 ? ` +${fresh.length - 1}` : ''})`);
    }
    firstLoadDone = true;
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, REFRESH_DEBOUNCE_MS);
  }

  async function retryOrder(orderId, retryButton) {
    retryButton.disabled = true;
    try {
      const res = await fetch(`/api/orders/${orderId}/retry-print`, {
        method: 'POST',
        headers: { ...window.auth.getAuthHeaders() },
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof body.detail === 'string' ? body.detail : '';
        window.toast?.error(`${tr('print_retry_error', 'Retry failed')}${detail ? `: ${detail}` : ''}`);
        return;
      }
      // If these slips fail again they must be announced again.
      for (const job of jobs) {
        if (job.order_id === orderId) seenIds.delete(job.id);
      }
      if (body.requeued > 0) {
        window.toast?.success(tr('print_retry_sent', 'Sent to the printer again'));
      } else {
        window.toast?.info(tr('print_retry_nothing', 'Nothing to reprint'));
      }
    } catch (err) {
      console.error('Retry print error:', err);
      window.toast?.error(tr('print_retry_error', 'Retry failed'));
    } finally {
      retryButton.disabled = false;
      scheduleRefresh();
    }
  }

  window.printJobs = {
    refresh,
    /** Call with the `data` of WebSocket event `print_job_updated`. */
    onEvent: scheduleRefresh,
  };

  if (canUse()) {
    refresh();
    setInterval(refresh, POLL_MS);
  }
})();
