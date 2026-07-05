const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['cashier', 'admin', 'root'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

// —— Tab switching ——
const tabDashboard = document.getElementById('tab-dashboard');
const tabCashier = document.getElementById('tab-cashier');
const tabMenu = document.getElementById('tab-menu');
const tabUsers = document.getElementById('tab-users');
const tabAdmins = document.getElementById('tab-admins');
const tabAuditLogs = document.getElementById('tab-audit-logs');
const tabTables = document.getElementById('tab-tables');
const panelDashboard = document.getElementById('panel-dashboard');
const panelCashier = document.getElementById('panel-cashier');
const panelMenu = document.getElementById('panel-menu');
const panelUsers = document.getElementById('panel-users');
const panelAdmins = document.getElementById('panel-admins');
const panelAuditLogs = document.getElementById('panel-audit-logs');
const panelTables = document.getElementById('panel-tables');
let hasInitializedDefaultPanel = false;
let activeDashboardTab = 'overview';

function showPanel(panel) {
  if (!panel) return;
  if (panelDashboard) panelDashboard.classList.add('hidden');
  panelCashier.classList.add('hidden');
  panelMenu.classList.add('hidden');
  if (panelUsers) panelUsers.classList.add('hidden');
  if (panelAdmins) panelAdmins.classList.add('hidden');
  if (panelAuditLogs) panelAuditLogs.classList.add('hidden');
  if (panelTables) panelTables.classList.add('hidden');

  if (tabDashboard) {
    tabDashboard.classList.remove('border-blue-600', 'text-blue-600');
    tabDashboard.classList.add('border-transparent', 'text-slate-600');
  }
  tabCashier.classList.remove('border-blue-600', 'text-blue-600');
  tabCashier.classList.add('border-transparent', 'text-slate-600');
  tabMenu.classList.remove('border-blue-600', 'text-blue-600');
  tabMenu.classList.add('border-transparent', 'text-slate-600');

  if (tabUsers) {
    tabUsers.classList.remove('border-blue-600', 'text-blue-600');
    tabUsers.classList.add('border-transparent', 'text-slate-600');
  }
  if (tabAdmins) {
    tabAdmins.classList.remove('border-blue-600', 'text-blue-600');
    tabAdmins.classList.add('border-transparent', 'text-slate-600');
  }
  if (tabAuditLogs) {
    tabAuditLogs.classList.remove('border-blue-600', 'text-blue-600');
    tabAuditLogs.classList.add('border-transparent', 'text-slate-600');
  }
  if (tabTables) {
    tabTables.classList.remove('border-blue-600', 'text-blue-600');
    tabTables.classList.add('border-transparent', 'text-slate-600');
  }

  panel.classList.remove('hidden');

  if (panelDashboard && panel === panelDashboard) {
    if (tabDashboard) tabDashboard.classList.add('border-blue-600', 'text-blue-600');
    loadDashboardSummary();
  } else if (panel === panelCashier) {
    tabCashier.classList.add('border-blue-600', 'text-blue-600');
    loadUnpaidOrders();
  } else if (panel === panelMenu) {
    tabMenu.classList.add('border-blue-600', 'text-blue-600');
    loadMenuData();
  } else if (panelUsers && panel === panelUsers) {
    if (tabUsers) tabUsers.classList.add('border-blue-600', 'text-blue-600');
    loadUsers();
  } else if (panelAdmins && panel === panelAdmins) {
    if (tabAdmins) tabAdmins.classList.add('border-blue-600', 'text-blue-600');
    loadRootAdmins();
  } else if (panelAuditLogs && panel === panelAuditLogs) {
    if (tabAuditLogs) tabAuditLogs.classList.add('border-blue-600', 'text-blue-600');
    loadAuditLogs();
  } else if (panelTables && panel === panelTables) {
    if (tabTables) tabTables.classList.add('border-blue-600', 'text-blue-600');
    loadTableManagementData();
  }
}

function applyDashboardTabState(nextTab) {
  activeDashboardTab = nextTab;
  const buttons = document.querySelectorAll('[data-dashboard-tab-btn]');
  const sections = document.querySelectorAll('[data-dashboard-tab-content]');
  buttons.forEach((btn) => {
    const key = btn.getAttribute('data-dashboard-tab-btn');
    const isActive = key === nextTab;
    btn.classList.toggle('border-blue-600', isActive);
    btn.classList.toggle('text-blue-700', isActive);
    btn.classList.toggle('font-semibold', isActive);
    btn.classList.toggle('border-transparent', !isActive);
    btn.classList.toggle('text-slate-500', !isActive);
    btn.classList.toggle('font-medium', !isActive);
  });
  sections.forEach((section) => {
    const key = section.getAttribute('data-dashboard-tab-content');
    section.classList.toggle('hidden', key !== nextTab);
  });
  if (nextTab === 'overview') {
    const role = getCounterUserRole();
    if (role === 'root' || role === 'admin') {
      Promise.allSettled([loadTopItemsChart(), loadHourlyTrendChart()]).then((results) => {
        if (results.some((r) => r.status === 'rejected')) {
          console.error('Dashboard chart loading failed:', results);
        }
      });
    }
  }
  if (nextTab === 'history' && !hasLoadedSalesHistoryTab) {
    const filterBtn = document.getElementById('btn-filter-history');
    if (filterBtn) filterBtn.click();
    hasLoadedSalesHistoryTab = true;
  }
  if (nextTab === 'insights' && !hasLoadedInsightsTab) {
    Promise.allSettled([loadCategorySalesChart(), loadCancellationsReport()]).then((results) => {
      if (results.some((r) => r.status === 'rejected')) {
        console.error('Insights loading failed:', results);
      }
    });
    hasLoadedInsightsTab = true;
  }
  if (nextTab === 'staff' && !hasLoadedStaffTab) {
    setStaffFilterDefaultDate();
    Promise.allSettled([loadStaffBreakdownCharts()]).then((results) => {
      if (results.some((r) => r.status === 'rejected')) {
        console.error('Staff breakdown loading failed:', results);
      }
    });
    hasLoadedStaffTab = true;
  }
  if (nextTab === 'incentives' && !hasLoadedIncentivesTab) {
    setIncentivesDefaultDates();
    Promise.allSettled([loadPromotedIncentivesReport()]).then((results) => {
      if (results.some((r) => r.status === 'rejected')) {
        console.error('Promoted incentives loading failed:', results);
      }
    });
    hasLoadedIncentivesTab = true;
  }
}

function bindDashboardSubTabs() {
  const buttons = document.querySelectorAll('[data-dashboard-tab-btn]');
  if (!buttons.length) return;
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-dashboard-tab-btn') || 'overview';
      applyDashboardTabState(key);
    });
  });
  applyDashboardTabState('overview');
}

if (tabDashboard && panelDashboard) tabDashboard.addEventListener('click', () => showPanel(panelDashboard));
tabCashier.addEventListener('click', () => showPanel(panelCashier));
tabMenu.addEventListener('click', () => showPanel(panelMenu));
if (tabUsers && panelUsers) tabUsers.addEventListener('click', () => showPanel(panelUsers));
if (tabTables && panelTables) tabTables.addEventListener('click', () => showPanel(panelTables));
window.addEventListener('DOMContentLoaded', () => {
  setSalesHistoryDefaultDates();
  setStaffFilterDefaultDate();
  bindSalesHistoryFilters();
  bindStaffBreakdownFilters();
  bindIncentivesFilters();
  bindDashboardSubTabs();
});

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

function applyCounterTabQueryParam() {
  const tab = new URLSearchParams(window.location.search).get('tab');
  if (tab !== 'cashier' || !panelCashier) return;
  showPanel(panelCashier);
  hasInitializedDefaultPanel = true;
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete('tab');
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', url.pathname + (qs ? `?${qs}` : ''));
  } catch (_) {
    /* ignore */
  }
}

function applyAdminOnlyTabVisibility(role) {
  const normalizedRole = String(role || '').toLowerCase();
  const isAdminPanel = normalizedRole === 'admin' || normalizedRole === 'root';
  const isRoot = normalizedRole === 'root';
  const isCashier = normalizedRole === 'cashier';
  const showDashboard = isAdminPanel || isCashier;
  if (tabDashboard) tabDashboard.classList.toggle('hidden', !showDashboard);
  applyDashboardRoleVisibility(normalizedRole);
  if (tabUsers) tabUsers.classList.toggle('hidden', !isAdminPanel);
  if (tabAdmins) tabAdmins.classList.toggle('hidden', !isRoot);
  if (tabAuditLogs) tabAuditLogs.classList.toggle('hidden', !isRoot);
  if (tabTables) tabTables.classList.toggle('hidden', !isAdminPanel);
  if (tabMenu) tabMenu.classList.toggle('hidden', normalizedRole === 'cashier');
  if (!isAdminPanel && panelDashboard && !panelDashboard.classList.contains('hidden')) {
    showPanel(panelCashier);
  }
  if (!isAdminPanel && panelTables && !panelTables.classList.contains('hidden')) {
    showPanel(panelCashier);
  }
  if (!isRoot && panelAdmins && !panelAdmins.classList.contains('hidden')) {
    showPanel(isAdminPanel && panelDashboard ? panelDashboard : panelCashier);
  }
  if (!isRoot && panelAuditLogs && !panelAuditLogs.classList.contains('hidden')) {
    showPanel(isAdminPanel && panelDashboard ? panelDashboard : panelCashier);
  }
  if (!hasInitializedDefaultPanel) {
    showPanel(showDashboard && panelDashboard ? panelDashboard : panelCashier);
    hasInitializedDefaultPanel = true;
  }
  applyCounterTabQueryParam();
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
let selectedOrderSubtotal = 0;
let cashierZones = [];
let cashierActiveZoneId = null;
let menuItemsCache = [];
let hourlyChart = null;
let topItemsChart = null;
let dailySalesChart = null;
let monthlySalesChart = null;
let hasLoadedSalesHistoryTab = false;
let categoryChart = null;
let cancelledItemsChart = null;
let hasLoadedInsightsTab = false;
let staffCashierChart = null;
let staffWaiterChart = null;
let hasLoadedStaffTab = false;
let promotedIncentivesChart = null;
let hasLoadedIncentivesTab = false;

function getCounterUserRole() {
  return String(window.auth?.getUser?.()?.role || '').toLowerCase();
}

function applyDashboardRoleVisibility(role) {
  const normalized = String(role || '').toLowerCase();
  const isRoot = normalized === 'root';
  const isAdmin = normalized === 'admin';
  const isCashier = normalized === 'cashier';
  const isAdminPanel = isRoot || isAdmin;

  document.querySelectorAll('[data-role-section]').forEach((el) => {
    const section = el.getAttribute('data-role-section');
    let visible = false;
    if (section === 'staff') visible = isRoot || isAdmin || isCashier;
    else if (section === 'incentives') visible = isRoot || isAdmin;
    else if (section === 'history' || section === 'insights') visible = isAdminPanel;
    else visible = true;
    el.classList.toggle('hidden', !visible);
  });

  document.querySelectorAll('[data-role-widget]').forEach((el) => {
    const widget = el.getAttribute('data-role-widget');
    let visible = true;
    if (widget === 'admin-charts') visible = isAdminPanel;
    if (widget === 'cashier-breakdown') visible = isRoot || isAdmin;
    if (widget === 'waiter-breakdown') visible = isRoot || isAdmin || isCashier;
    el.classList.toggle('hidden', !visible);
  });

  const salesLabel = document.querySelector('#dashboard-tab-overview .border-emerald-500 p.text-sm');
  if (salesLabel) {
    salesLabel.textContent = isCashier ? 'My Checkout Sales (Today)' : "Today's Sales";
  }

  const staffCashierTitle = document.querySelector('#staff-cashier-section h3');
  if (staffCashierTitle && isCashier) {
    staffCashierTitle.textContent = 'My Checkout Sales';
  }
}

function t(key, fallback) {
  return window.i18n?.t?.(key) || fallback || key;
}

/** Chart.js axes: MMK amounts via centralized currency helpers (see static/currency.js). */
function chartMoneyTickValue(value) {
  return typeof formatMoney === 'function' ? formatMoney(Number(value)) : String(value);
}

/** Tooltip for bar/line charts whose series values are money amounts. */
function chartTooltipLabelMoney(ctx) {
  const fmt = typeof formatMoney === 'function' ? formatMoney : (v) => String(Number(v));
  const prefix = ctx.dataset?.label ? `${ctx.dataset.label}: ` : '';
  const y = ctx.parsed?.y;
  if (typeof y === 'number' && !Number.isNaN(y)) return `${prefix}${fmt(y)}`;
  const x = ctx.parsed?.x;
  if (typeof x === 'number' && !Number.isNaN(x)) return `${prefix}${fmt(x)}`;
  return `${prefix}${fmt(Number(ctx.raw ?? 0))}`;
}

/** Doughnut slices where values are MMK (e.g. category sales). */
function chartTooltipLabelMoneyDoughnut(ctx) {
  const fmt = typeof formatMoney === 'function' ? formatMoney : (v) => String(Number(v));
  const head = ctx.label ? `${ctx.label}: ` : '';
  const p = ctx.parsed;
  const n =
    typeof p === 'number' && !Number.isNaN(p)
      ? p
      : Number(p?.r ?? p?.x ?? p?.y ?? ctx.raw ?? 0);
  return `${head}${fmt(n)}`;
}

function destroyDashboardCharts() {
  if (topItemsChart) {
    topItemsChart.destroy();
    topItemsChart = null;
  }
  if (hourlyChart) {
    hourlyChart.destroy();
    hourlyChart = null;
  }
}

function setChartEmptyState(canvasId, emptyId, isEmpty) {
  const canvas = document.getElementById(canvasId);
  const emptyEl = document.getElementById(emptyId);
  if (canvas) canvas.classList.toggle('hidden', isEmpty);
  if (emptyEl) emptyEl.classList.toggle('hidden', !isEmpty);
}

function formatDateInputValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function setSalesHistoryDefaultDates() {
  const startInput = document.getElementById('filter-start-date');
  const endInput = document.getElementById('filter-end-date');
  if (!startInput || !endInput) return;
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 29);
  endInput.value = formatDateInputValue(today);
  startInput.value = formatDateInputValue(start);
}

async function loadDailySalesChart(startDate, endDate) {
  const canvas = document.getElementById('dailySalesChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const url = `${API_BASE}/api/reports/daily-sales${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url, { headers: { ...window.auth.getAuthHeaders() } });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const rows = await res.json().catch(() => []);
  if (!res.ok) throw new Error((rows && rows.detail) || 'Failed to load daily sales');

  const labels = (rows || []).map((x) => String(x.date || ''));
  const values = (rows || []).map((x) => Number(x.total || 0));
  if (dailySalesChart) dailySalesChart.destroy();
  dailySalesChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: t('total', 'Total'),
          data: values,
          backgroundColor: '#3b82f6',
          borderColor: '#2563eb',
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: chartMoneyTickValue },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: chartTooltipLabelMoney } },
      },
    },
  });
}

async function loadMonthlySalesChart(year) {
  const canvas = document.getElementById('monthlySalesChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const queryYear = Number(year) || new Date().getFullYear();
  const res = await fetch(`${API_BASE}/api/reports/monthly-sales?year=${encodeURIComponent(queryYear)}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const rows = await res.json().catch(() => []);
  if (!res.ok) throw new Error((rows && rows.detail) || 'Failed to load monthly sales');

  const labels = (rows || []).map((x) => String(x.month || ''));
  const values = (rows || []).map((x) => Number(x.total || 0));
  if (monthlySalesChart) monthlySalesChart.destroy();
  monthlySalesChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: t('total', 'Total'),
          data: values,
          borderColor: '#14b8a6',
          backgroundColor: 'rgba(20, 184, 166, 0.2)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointBackgroundColor: '#14b8a6',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: chartMoneyTickValue },
        },
      },
      plugins: {
        tooltip: { callbacks: { label: chartTooltipLabelMoney } },
      },
    },
  });
}

async function loadCategorySalesChart() {
  const canvas = document.getElementById('categorySalesChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const res = await fetch(`${API_BASE}/api/reports/category-sales`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const rows = await res.json().catch(() => []);
  if (!res.ok) throw new Error((rows && rows.detail) || 'Failed to load category sales');

  const labels = (rows || []).map((x) => String(x.category_name || t('none', 'None')));
  const values = (rows || []).map((x) => Number(x.total_sales || 0));
  if (categoryChart) categoryChart.destroy();

  categoryChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [
        {
          label: t('total', 'Total'),
          data: values,
          backgroundColor: ['#2563eb', '#0ea5e9', '#14b8a6', '#22c55e', '#f59e0b', '#8b5cf6', '#f97316'],
          borderColor: '#ffffff',
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: { label: chartTooltipLabelMoneyDoughnut } },
      },
    },
  });
}

async function loadCancellationsReport() {
  const countEl = document.getElementById('kpi-cancelled-count');
  const lostRevenueEl = document.getElementById('kpi-lost-revenue');
  const canvas = document.getElementById('cancelledItemsChart');
  if (!canvas || typeof Chart === 'undefined') return;

  const res = await fetch(`${API_BASE}/api/reports/cancellations`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data && data.detail) || 'Failed to load cancellations report');

  const totalCancelled = Number(data.total_cancelled_items || 0);
  const lostRevenue = Number(data.total_lost_revenue || 0);
  if (countEl) countEl.textContent = String(totalCancelled);
  if (lostRevenueEl) lostRevenueEl.textContent = formatMoney(lostRevenue);

  const topItems = Array.isArray(data.top_cancelled_items) ? data.top_cancelled_items : [];
  const labels = topItems.map((x) => String(x.item_name || ''));
  const values = topItems.map((x) => Number(x.count || 0));
  if (cancelledItemsChart) cancelledItemsChart.destroy();

  cancelledItemsChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: t('cancelled', 'Cancelled'),
          data: values,
          backgroundColor: 'rgba(239, 68, 68, 0.7)',
          borderColor: 'rgba(239, 68, 68, 1)',
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          ticks: { stepSize: 1, callback: (v) => String(Math.round(Number(v))) },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const q = ctx.parsed?.x ?? ctx.raw;
              return `${t('cancelled', 'Cancelled')}: ${Math.round(Number(q))}`;
            },
          },
        },
      },
    },
  });
}

function bindSalesHistoryFilters() {
  const btn = document.getElementById('btn-filter-history');
  const startInput = document.getElementById('filter-start-date');
  const endInput = document.getElementById('filter-end-date');
  if (!btn || !startInput || !endInput) return;

  btn.addEventListener('click', async () => {
    const start = startInput.value || '';
    const end = endInput.value || '';
    try {
      await loadDailySalesChart(start, end);
      const year = end ? Number(String(end).slice(0, 4)) : new Date().getFullYear();
      await loadMonthlySalesChart(year);
    } catch (err) {
      console.error('Sales history charts failed:', err);
      if (window.toast?.error) window.toast.error(err.message || 'Failed to load sales history');
    }
  });
}

function getStaffReportDateRange() {
  const startInput = document.getElementById('staff-filter-start-date');
  const endInput = document.getElementById('staff-filter-end-date');
  const startDate = startInput?.value || '';
  const endDate = endInput?.value || '';
  if (startDate && endDate && startDate > endDate) {
    throw new Error('Start date cannot be after end date.');
  }
  return { startDate, endDate };
}

function setStaffFilterDateRange(startDate, endDate) {
  const startInput = document.getElementById('staff-filter-start-date');
  const endInput = document.getElementById('staff-filter-end-date');
  if (startInput) startInput.value = startDate;
  if (endInput) endInput.value = endDate;
  updateStaffReportPeriodLabel(startDate, endDate);
}

function setStaffFilterDefaultDate() {
  const today = formatDateInputValue(new Date());
  const monthStart = formatDateInputValue(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  setStaffFilterDateRange(monthStart, today);
}

function updateStaffReportPeriodLabel(startDate, endDate) {
  const el = document.getElementById('staff-report-period');
  if (!el) return;
  if (!startDate || !endDate) {
    el.textContent = '';
    return;
  }
  el.textContent = startDate === endDate
    ? `Showing data for ${startDate}`
    : `Showing data from ${startDate} to ${endDate}`;
}

async function fetchStaffSales(endpoint, startDate, endDate) {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const res = await fetch(`${API_BASE}/api/reports/sales/${endpoint}?${params.toString()}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : `Failed to load ${endpoint}`);
  }
  return Array.isArray(data) ? data : [];
}

function renderStaffBarChart(canvasId, emptyId, rows, label) {
  const canvas = document.getElementById(canvasId);
  const emptyEl = document.getElementById(emptyId);
  if (!canvas || typeof Chart === 'undefined') return null;
  const labels = (rows || []).map((r) => `${r.username || 'User'} (${r.role || ''})`);
  const values = (rows || []).map((r) => Number(r.total_sales || 0));
  const hasData = values.some((v) => v > 0);
  if (emptyEl) emptyEl.classList.toggle('hidden', hasData);
  canvas.classList.toggle('hidden', !hasData);
  if (!hasData) return null;

  if (canvasId === 'staffCashierChart' && staffCashierChart) staffCashierChart.destroy();
  if (canvasId === 'staffWaiterChart' && staffWaiterChart) staffWaiterChart.destroy();

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label,
          data: values,
          backgroundColor: '#3b82f6',
          borderColor: '#2563eb',
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          ticks: { callback: chartMoneyTickValue },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: chartTooltipLabelMoney } },
      },
    },
  });
  return chart;
}

async function loadStaffBreakdownCharts() {
  const { startDate, endDate } = getStaffReportDateRange();
  updateStaffReportPeriodLabel(startDate, endDate);
  const role = getCounterUserRole();
  const showCashier = role === 'root' || role === 'admin';
  const showWaiter = role === 'root' || role === 'admin' || role === 'cashier';

  if (showCashier) {
    const cashierRows = await fetchStaffSales('by-cashier', startDate, endDate);
    if (cashierRows) {
      staffCashierChart = renderStaffBarChart(
        'staffCashierChart',
        'staffCashierChartEmpty',
        cashierRows,
        t('total', 'Total')
      );
    }
  }

  if (showWaiter) {
    const waiterRows = await fetchStaffSales('by-order-staff', startDate, endDate);
    if (waiterRows) {
      staffWaiterChart = renderStaffBarChart(
        'staffWaiterChart',
        'staffWaiterChartEmpty',
        waiterRows,
        t('total', 'Total')
      );
    }
  }
}

function bindStaffBreakdownFilters() {
  const load = async () => {
    try {
      await loadStaffBreakdownCharts();
    } catch (err) {
      console.error(err);
      if (window.toast?.error) window.toast.error(err.message || 'Failed to load staff reports');
    }
  };

  const btn = document.getElementById('btn-staff-filter');
  if (btn) btn.addEventListener('click', load);

  const todayBtn = document.getElementById('btn-staff-preset-today');
  if (todayBtn) {
    todayBtn.addEventListener('click', async () => {
      const today = formatDateInputValue(new Date());
      setStaffFilterDateRange(today, today);
      await load();
    });
  }

  const monthBtn = document.getElementById('btn-staff-preset-month');
  if (monthBtn) {
    monthBtn.addEventListener('click', async () => {
      const now = new Date();
      const monthStart = formatDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1));
      const today = formatDateInputValue(now);
      setStaffFilterDateRange(monthStart, today);
      await load();
    });
  }
}

function setIncentivesDefaultDates() {
  const today = formatDateInputValue(new Date());
  const start = document.getElementById('incentives-start-date');
  const end = document.getElementById('incentives-end-date');
  if (end) end.value = today;
  if (start) start.value = today;
}

function renderPromotedIncentivesTable(rows) {
  const el = document.getElementById('promoted-incentives-table');
  if (!el) return;
  if (!rows.length) {
    el.textContent = 'No promoted-item sales for this period.';
    return;
  }
  el.innerHTML = `
    <table class="w-full text-left">
      <thead>
        <tr class="border-b border-slate-200 text-slate-500">
          <th class="py-2 pr-2">Staff</th>
          <th class="py-2 pr-2">Role</th>
          <th class="py-2 pr-2">Qty</th>
          <th class="py-2">Revenue</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr class="border-b border-slate-100">
            <td class="py-2 pr-2 font-medium">${escapeHtml(r.username)}</td>
            <td class="py-2 pr-2">${escapeHtml(r.role)}</td>
            <td class="py-2 pr-2">${Number(r.quantity || 0)}</td>
            <td class="py-2">${formatMoney(Number(r.total_sales || 0))}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function loadPromotedIncentivesReport() {
  const start = document.getElementById('incentives-start-date')?.value || '';
  const end = document.getElementById('incentives-end-date')?.value || '';
  const params = new URLSearchParams();
  if (start) params.set('start_date', start);
  if (end) params.set('end_date', end);
  const res = await fetch(`${API_BASE}/api/reports/sales/promoted-by-waiter?${params.toString()}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to load promoted incentives');
  }
  const rows = Array.isArray(data) ? data : [];
  renderPromotedIncentivesTable(rows);

  const canvas = document.getElementById('promotedIncentivesChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const labels = rows.map((r) => `${r.username} (${r.role})`);
  const values = rows.map((r) => Number(r.total_sales || 0));
  if (promotedIncentivesChart) promotedIncentivesChart.destroy();
  promotedIncentivesChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Promoted sales',
        data: values,
        backgroundColor: '#f59e0b',
        borderColor: '#d97706',
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: { x: { beginAtZero: true, ticks: { callback: chartMoneyTickValue } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: chartTooltipLabelMoney } } },
    },
  });
}

function bindIncentivesFilters() {
  const btn = document.getElementById('btn-incentives-filter');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    try {
      await loadPromotedIncentivesReport();
    } catch (err) {
      console.error(err);
      if (window.toast?.error) window.toast.error(err.message || 'Failed to load incentives');
    }
  });
}

async function loadTopItemsChart() {
  const canvas = document.getElementById('topItemsChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const res = await fetch(`${API_BASE}/api/reports/top-items`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const rows = await res.json().catch(() => []);
  if (!res.ok) throw new Error((rows && rows.detail) || 'Failed to load top items');

  const labels = (rows || []).map((x) => x.item_name || x.menu_item_name || t('none', 'None'));
  const values = (rows || []).map((x) => Number(x.quantity_sold || 0));
  const palette = ['#2563eb', '#0ea5e9', '#14b8a6', '#22c55e', '#f59e0b'];
  const hasData = values.length > 0 && values.some((v) => v > 0);
  if (topItemsChart) topItemsChart.destroy();
  if (!hasData) {
    setChartEmptyState('topItemsChart', 'topItemsChartEmpty', true);
    return;
  }
  setChartEmptyState('topItemsChart', 'topItemsChartEmpty', false);

  topItemsChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [
        {
          label: t('qty', 'Qty'),
          data: values,
          backgroundColor: palette,
          borderColor: '#ffffff',
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const q = ctx.parsed ?? ctx.raw;
              return `${t('qty', 'Qty')}: ${Math.round(Number(q))}`;
            },
          },
        },
      },
    },
  });
}

async function loadHourlyTrendChart() {
  const canvas = document.getElementById('hourlyTrendChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const res = await fetch(`${API_BASE}/api/reports/hourly-trend`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const rows = await res.json().catch(() => []);
  if (!res.ok) throw new Error((rows && rows.detail) || 'Failed to load hourly trend');

  const labels = (rows || []).map((x) => String(x.hour || ''));
  const values = (rows || []).map((x) => Number(x.total ?? x.total_sales ?? 0));
  const hasData = values.length > 0 && values.some((v) => v > 0);
  if (hourlyChart) hourlyChart.destroy();
  if (!hasData) {
    setChartEmptyState('hourlyTrendChart', 'hourlyTrendChartEmpty', true);
    return;
  }
  setChartEmptyState('hourlyTrendChart', 'hourlyTrendChartEmpty', false);

  hourlyChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: t('total', 'Total'),
          data: values,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.2)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#2563eb',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'bottom' },
        tooltip: { callbacks: { label: chartTooltipLabelMoney } },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: chartMoneyTickValue },
        },
      },
    },
  });
}

async function dialogAlert(message, type = 'error', _title = 'Notice') {
  const title = type === 'success' ? t('success', 'Success') : type === 'info' ? t('info', 'Info') : t('error', 'Error');
  if (window.CustomDialog?.alert) {
    await window.CustomDialog.alert(title, message);
    return;
  }
  if (type === 'success' && window.toast?.success) {
    window.toast.success(message);
    return;
  }
  if (type === 'info' && window.toast?.info) {
    window.toast.info(message);
    return;
  }
  if (window.toast?.error) {
    window.toast.error(message);
    return;
  }
  console.warn(`[${title}] ${message}`);
}

async function dialogConfirm(message, _title = 'Confirm') {
  const title = _title || t('confirm_action', 'Confirm Action');
  if (window.CustomDialog?.confirm) {
    const result = await window.CustomDialog.confirm(title, message);
    return Boolean(result);
  }
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'fixed inset-0 z-[10000] bg-black/50 flex items-center justify-center p-4';
    const modal = document.createElement('div');
    modal.className = 'w-full max-w-md bg-white rounded-lg shadow-2xl overflow-hidden';
    modal.innerHTML = `
      <div class="px-4 py-3 border-b border-slate-200">
        <h3 class="text-base font-semibold text-slate-800">${escapeHtml(title)}</h3>
      </div>
      <div class="px-4 py-4">
        <p class="text-sm text-slate-700 leading-relaxed">${escapeHtml(message)}</p>
      </div>
      <div class="px-4 py-3 bg-slate-50 border-t border-slate-200 flex justify-end gap-2">
        <button type="button" data-confirm-cancel class="px-3 py-2 text-sm rounded-md bg-slate-200 text-slate-800 hover:bg-slate-300">
          ${escapeHtml(t('cancel', 'Cancel'))}
        </button>
        <button type="button" data-confirm-ok class="px-3 py-2 text-sm rounded-md bg-rose-600 text-white hover:bg-rose-700">
          ${escapeHtml(t('confirm_delete', 'Confirm Delete'))}
        </button>
      </div>
    `;
    const cleanup = (value) => {
      backdrop.remove();
      resolve(Boolean(value));
    };
    modal.querySelector('[data-confirm-cancel]')?.addEventListener('click', () => cleanup(false));
    modal.querySelector('[data-confirm-ok]')?.addEventListener('click', () => cleanup(true));
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) cleanup(false);
    });
    document.body.appendChild(backdrop);
    backdrop.appendChild(modal);
  });
}

async function loadDashboardSummary() {
  const salesEl = document.getElementById('kpi-total-sales');
  const ordersEl = document.getElementById('kpi-total-orders');
  const avgEl = document.getElementById('kpi-average-order-value');
  if (!salesEl || !ordersEl || !avgEl) return;

  salesEl.textContent = formatMoney(0);
  ordersEl.textContent = '0';
  avgEl.textContent = formatMoney(0);

  try {
    const res = await fetch(`${API_BASE}/api/reports/summary/today`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Failed to load dashboard summary');

    const totalSales = Number(data.total_sales) || 0;
    const totalOrders = Number(data.total_orders) || 0;
    const averageOrderValue = Number(data.average_order_value) || 0;

    salesEl.textContent = formatMoney(totalSales);
    ordersEl.textContent = String(Math.max(0, Math.floor(totalOrders)));
    avgEl.textContent = formatMoney(averageOrderValue);
  } catch (err) {
    console.error(err);
    if (window.toast) window.toast.error('Failed to load dashboard summary');
  }
  if (activeDashboardTab === 'overview') {
    const role = getCounterUserRole();
    if (role === 'root' || role === 'admin') {
      Promise.allSettled([loadTopItemsChart(), loadHourlyTrendChart()]).then((results) => {
        const hasFailure = results.some((r) => r.status === 'rejected');
        if (hasFailure) {
          console.error('Dashboard chart loading failed:', results);
        }
      });
    }
  }
}

function getCheckoutDiscountState() {
  const typeEl = document.getElementById('checkout-discount-type');
  const valueEl = document.getElementById('checkout-discount-value');
  const rawType = (typeEl?.value || 'none').toLowerCase();
  const normalizedType = rawType === 'percentage' || rawType === 'amount' ? rawType : 'none';
  const parsedValue = parseFloat(valueEl?.value || '0');
  const value = Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : 0;
  return { type: normalizedType, value };
}

function calculateOrderDiscountAmount(subtotal, discountType, discountValue) {
  const safeSubtotal = Number.isFinite(subtotal) ? subtotal : 0;
  const safeValue = Number.isFinite(discountValue) && discountValue > 0 ? discountValue : 0;
  if (discountType === 'percentage') return safeSubtotal * (safeValue / 100);
  if (discountType === 'amount') return safeValue;
  return 0;
}

function roundMoney(value) {
  const safe = Number.isFinite(value) ? value : 0;
  return Math.round(safe * 100) / 100;
}

function recalculateCheckoutTotals() {
  const subtotal = Number.isFinite(selectedOrderSubtotal) ? selectedOrderSubtotal : 0;
  const { type, value } = getCheckoutDiscountState();
  const discountAmount = roundMoney(calculateOrderDiscountAmount(subtotal, type, value));
  const taxableAmount = roundMoney(Math.max(subtotal - discountAmount, 0));
  const taxAmount = roundMoney(taxableAmount * 0.05);
  const finalTotal = roundMoney(taxableAmount + taxAmount);

  const subtotalEl = document.getElementById('receipt-subtotal');
  const discountEl = document.getElementById('receipt-discount-amount');
  const taxEl = document.getElementById('receipt-tax-amount');
  const grandTotalEl = document.getElementById('receipt-grand-total');
  if (subtotalEl) subtotalEl.textContent = formatMoney(subtotal);
  if (discountEl) discountEl.textContent = formatMoneyNegative(discountAmount);
  if (taxEl) taxEl.textContent = formatMoney(taxAmount);
  if (grandTotalEl) grandTotalEl.textContent = `${t('grand_total', 'Grand Total')}: ${formatMoney(finalTotal)}`;

  selectedOrderTotal = finalTotal;

  const amountInput = document.getElementById('amount-tendered');
  const changeSpan = document.getElementById('change-amount');
  const tendered = parseFloat(amountInput?.value || '0');
  const change = tendered - finalTotal;
  if (!changeSpan) return finalTotal;
  if (Number.isNaN(change)) changeSpan.textContent = formatMoney(0);
  else if (change >= 0) changeSpan.textContent = formatMoney(change);
  else changeSpan.textContent = t('insufficient', 'Insufficient');
  return finalTotal;
}

async function fetchCashierTableGrid() {
  const res = await fetch(`${API_BASE}/api/tables/grid`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch table grid');
  return res.json();
}

async function fetchActiveTakeawayOrders() {
  const res = await fetch(`${API_BASE}/api/orders/active-takeaways`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch active takeaway orders');
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
    grid.innerHTML = `<p class="col-span-full text-slate-500">${escapeHtml(t('no_tables_in_zone', 'No tables in this zone.'))}</p>`;
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
        await dialogAlert(t('table_is_empty', 'Table is currently empty'), 'info', t('table', 'Table'));
        return;
      }
      try {
        const order = await fetchActiveOrderByTable(tableId);
        selectOrder(order);
      } catch (e) {
        await dialogAlert(e.message || `${t('no_active_order_for_table', 'No active order found for this table.')}`, 'error', t('load_failed', 'Load Failed'));
      }
    });
  });
}

function renderTakeawayOrders(orders) {
  const container = document.getElementById('cashier-takeaway-orders');
  if (!container) return;
  const takeawayOrders = (orders || [])
    .sort((a, b) => Number(b.id || 0) - Number(a.id || 0));

  if (!takeawayOrders.length) {
    container.innerHTML = `<p class="text-slate-500 text-sm">${escapeHtml(t('no_active_takeaway_orders', 'No active takeaway orders.'))}</p>`;
    return;
  }

  container.innerHTML = takeawayOrders.map((o) => {
    const customer = String(o.customer_name || '').trim() || t('walk_in', 'Walk-in');
    const items = Array.isArray(o.items) ? o.items : [];
    const pending = items.filter((i) => String(i.item_status || '').toLowerCase() !== 'served').length;
    const served = items.filter((i) => String(i.item_status || '').toLowerCase() === 'served').length;
    return `
      <button
        type="button"
        data-takeaway-order-id="${o.id}"
        class="w-full text-left border border-orange-200 rounded-md p-2 bg-orange-50 hover:bg-orange-100"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-medium text-orange-800">${escapeHtml(t('order', 'Order'))} #${o.id}</span>
          <span class="text-xs text-orange-700">${escapeHtml(t('total', 'Total'))}: ${formatMoney(Number(o.total_amount || 0))}</span>
        </div>
        <div class="text-xs text-orange-700 mt-0.5">${escapeHtml(t('customer', 'Customer'))}: ${escapeHtml(customer)}</div>
        <div class="mt-1.5 flex gap-1">
          <span class="text-[11px] px-2 py-0.5 rounded bg-amber-100 text-amber-800">${escapeHtml(t('pending', 'Pending'))}: ${pending}</span>
          <span class="text-[11px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">${escapeHtml(t('served', 'Served'))}: ${served}</span>
        </div>
      </button>
    `;
  }).join('');

  container.querySelectorAll('[data-takeaway-order-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const orderId = Number(btn.getAttribute('data-takeaway-order-id'));
      const order = takeawayOrders.find((o) => Number(o.id) === orderId);
      if (order) selectOrder(order);
    });
  });
}

async function loadTakeawayOrders() {
  const takeaway = document.getElementById('cashier-takeaway-orders');
  if (takeaway) takeaway.innerHTML = `<p class="text-slate-500 text-sm">${escapeHtml(t('loading_takeaway_orders', 'Loading takeaway orders...'))}</p>`;
  try {
    const orders = await fetchActiveTakeawayOrders();
    renderTakeawayOrders(orders || []);
  } catch (e) {
    console.error(e);
    if (takeaway) takeaway.innerHTML = `<p class="text-red-600 text-sm">${escapeHtml(t('error_loading_takeaway_orders', 'Error loading takeaway orders.'))}</p>`;
  }
}

function loadUnpaidOrders() {
  const grid = document.getElementById('cashier-tables-grid');
  if (grid) grid.innerHTML = `<p class="col-span-full text-slate-500">${escapeHtml(t('loading_table_grid', 'Loading table grid...'))}</p>`;
  Promise.all([fetchCashierTableGrid(), fetchActiveTakeawayOrders()])
    .then(([zones, takeawayOrders]) => {
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
      renderTakeawayOrders(takeawayOrders || []);
    })
    .catch((e) => {
      console.error(e);
      if (grid) grid.innerHTML = `<p class="col-span-full text-red-600">${escapeHtml(t('error_loading_table_grid', 'Error loading table grid.'))}</p>`;
    });
}

function selectOrder(order) {
  if (!order) return;
  selectedOrderId = order.id;
  selectedTableNumber = order.table_number;
  const visibleItems = (order.items || []).filter((i) => String(i?.item_status || '').toLowerCase() !== 'cancelled');
  selectedOrderSubtotal = visibleItems.reduce((sum, i) => sum + (Number(i.subtotal) || 0), 0);
  selectedOrderTotal = selectedOrderSubtotal;
  document.getElementById('receipt-placeholder').classList.add('hidden');
  const container = document.getElementById('receipt-container');
  container.classList.remove('hidden');
  const isTakeaway = String(order.order_type || '').toLowerCase() === 'takeaway';
  const checkoutHeaderEl = document.getElementById('checkout-header');
  const customer = String(order.customer_name || '').trim() || t('walk_in', 'Walk-in');
  if (checkoutHeaderEl) {
    checkoutHeaderEl.textContent = isTakeaway
      ? `${t('checkout', 'Checkout')} - ${t('takeaway', 'Takeaway')} (${t('customer', 'Customer')}: ${customer})`
      : `${t('checkout', 'Checkout')} - ${t('table', 'Table')} ${orderTableLabel(order)}`;
  }
  const itemsRows = visibleItems
    .map(
      (i) =>
        `<tr><td class="py-1">${escapeHtml(i.menu_item_name)}</td><td class="py-1 text-right">${i.quantity}</td><td class="py-1 text-right">${formatMoney(Number(i.subtotal))}</td></tr>`
    )
    .join('');
  document.getElementById('receipt-content').innerHTML = `
    <table class="w-full text-sm text-slate-700">
      <thead><tr class="border-b border-slate-200"><th class="text-left py-1">${escapeHtml(t('item', 'Item'))}</th><th class="text-right py-1">${escapeHtml(t('qty', 'Qty'))}</th><th class="text-right py-1">${escapeHtml(t('subtotal', 'Subtotal'))}</th></tr></thead>
      <tbody>${itemsRows}</tbody>
    </table>
  `;
  const servedByEl = document.getElementById('receipt-served-by');
  if (servedByEl) servedByEl.textContent = order.served_by_name || '—';
  // Reset payment inputs for this order
  const amountInput = document.getElementById('amount-tendered');
  const changeSpan = document.getElementById('change-amount');
  const methodSelect = document.getElementById('payment-method');
  const discountTypeSelect = document.getElementById('checkout-discount-type');
  const discountValueInput = document.getElementById('checkout-discount-value');
  if (amountInput) amountInput.value = '';
  if (changeSpan) changeSpan.textContent = formatMoney(0);
  if (methodSelect) methodSelect.value = 'cash';
  if (discountTypeSelect) discountTypeSelect.value = 'none';
  if (discountValueInput) {
    discountValueInput.value = '';
    discountValueInput.disabled = true;
  }
  recalculateCheckoutTotals();
}

function renderReceiptForPrint(order) {
  try {
    const rpTable = document.getElementById('rp-table');
    const rpServedBy = document.getElementById('rp-served-by');
    const rpDatetime = document.getElementById('rp-datetime');
    const rpItems = document.getElementById('rp-items');
    const rpTotal = document.getElementById('rp-total');
    const rpSubtotal = document.getElementById('rp-subtotal');
    const rpDiscount = document.getElementById('rp-discount');
    const rpTax = document.getElementById('rp-tax');
    const rpMethod = document.getElementById('rp-method');
    const rpTendered = document.getElementById('rp-tendered');
    const rpChange = document.getElementById('rp-change');

    const isTakeaway = String(order.order_type || '').toLowerCase() === 'takeaway';
    if (rpTable) rpTable.textContent = isTakeaway
      ? `TAKEAWAY - ${String(order.customer_name || '').trim() || 'Walk-in'}`
      : `${orderTableLabel(order)}`;
    if (rpServedBy) rpServedBy.textContent = order.served_by_name || '—';
    if (rpDatetime) rpDatetime.textContent = order.created_at ? new Date(order.created_at).toLocaleString() : '';
    if (rpMethod) rpMethod.textContent = order.payment_method || '';
    if (rpTendered) rpTendered.textContent = order.amount_tendered != null ? formatMoney(Number(order.amount_tendered)) : formatMoney(0);
    if (rpChange) rpChange.textContent = order.change_amount != null ? formatMoney(Number(order.change_amount)) : formatMoney(0);

    let subtotal = 0;
    const visibleItems = (order.items || []).filter((i) => String(i?.item_status || '').toLowerCase() !== 'cancelled');
    const rows = visibleItems
      .map((item) => {
        subtotal += Number(item.subtotal) || 0;
        return `
          <div class="flex justify-between gap-2">
            <span class="flex-1">${escapeHtml(item.menu_item_name)}</span>
            <span class="text-right">× ${item.quantity}</span>
            <span class="text-right">${formatMoney(Number(item.subtotal))}</span>
          </div>
        `;
      })
      .join('');
    subtotal = roundMoney(subtotal);
    const discountType = String(order.discount_type || '').toLowerCase();
    const discountValue = Number(order.discount_value) || 0;
    const discountAmount = roundMoney(calculateOrderDiscountAmount(subtotal, discountType, discountValue));
    const taxableAmount = roundMoney(Math.max(subtotal - discountAmount, 0));
    const taxAmount = roundMoney(Number(order.tax_amount) || (taxableAmount * 0.05));
    if (rpItems) rpItems.innerHTML = rows || '<div class="text-sm text-slate-600">No items</div>';
    if (rpSubtotal) rpSubtotal.textContent = formatMoney(subtotal);
    if (rpDiscount) rpDiscount.textContent = formatMoneyNegative(discountAmount);
    if (rpTax) rpTax.textContent = formatMoney(taxAmount);
    if (rpTotal) rpTotal.textContent = formatMoney(Number(order.total_amount));
  } catch (e) {
    // Don't block checkout if printing fails.
    console.error('Receipt print rendering failed:', e);
  }
}

// Dynamic change calculation and payment processing
const amountInputEl = document.getElementById('amount-tendered');
const changeSpanEl = document.getElementById('change-amount');
const paymentMethodEl = document.getElementById('payment-method');
const discountTypeEl = document.getElementById('checkout-discount-type');
const discountValueEl = document.getElementById('checkout-discount-value');

if (amountInputEl) {
  amountInputEl.addEventListener('input', recalculateCheckoutTotals);
}

if (discountTypeEl && discountValueEl) {
  discountTypeEl.addEventListener('change', () => {
    const hasDiscount = discountTypeEl.value === 'percentage' || discountTypeEl.value === 'amount';
    discountValueEl.disabled = !hasDiscount;
    if (!hasDiscount) discountValueEl.value = '';
    recalculateCheckoutTotals();
  });
  discountValueEl.addEventListener('input', recalculateCheckoutTotals);
}

document.getElementById('btn-process-payment').addEventListener('click', async () => {
  if (selectedOrderId == null) return;
  const btn = document.getElementById('btn-process-payment');
  const amountInput = document.getElementById('amount-tendered');
  const methodSelect = document.getElementById('payment-method');
  const tendered = parseFloat((amountInput && amountInput.value) || '0');
  const { type: discountType, value: discountValue } = getCheckoutDiscountState();
  const currentFinalTotal = recalculateCheckoutTotals();

  if (Number.isNaN(tendered) || tendered <= 0) {
    await dialogAlert(t('enter_valid_amount_tendered', 'Enter a valid amount tendered.'), 'error', t('error', 'Error'));
    return;
  }
  if (tendered < currentFinalTotal) {
    await dialogAlert(t('amount_less_than_total', 'Amount tendered is less than total.'), 'error', t('error', 'Error'));
    return;
  }

  const method = methodSelect ? methodSelect.value || 'cash' : 'cash';

  btn.disabled = true;
  btn.textContent = t('processing', 'Processing...');
  try {
    const res = await fetch(`${API_BASE}/api/orders/${selectedOrderId}/checkout`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify({
        payment_method: method,
        amount_tendered: tendered,
        discount_type: discountType === 'none' ? null : discountType,
        discount_value: discountType === 'none' ? 0 : discountValue,
      }),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      await dialogAlert(data.detail || t('payment_failed', 'Payment failed'), 'error', t('error', 'Error'));
      return;
    }
    await dialogAlert(t('payment_success', 'Payment processed successfully.'), 'success', t('success', 'Success'));

    // Populate printable receipt and trigger print
    renderReceiptForPrint(data);
    window.print();

    selectedOrderId = null;
    selectedTableNumber = null;
    selectedOrderTotal = 0;
    selectedOrderSubtotal = 0;
    document.getElementById('receipt-container').classList.add('hidden');
    document.getElementById('receipt-placeholder').classList.remove('hidden');
    // Reload grid from backend after payment.
    loadUnpaidOrders();
    loadTakeawayOrders();
  } catch (e) {
    console.error(e);
    await dialogAlert(t('payment_failed', 'Payment failed'), 'error', t('error', 'Error'));
  } finally {
    btn.disabled = false;
    btn.textContent = t('confirm_payment', 'Confirm Payment');
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

function formatUserSaveError(detail) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((x) => (typeof x === 'string' ? x : x?.msg || '')).filter(Boolean);
    if (msgs.length) return msgs.join(', ');
  }
  return 'Failed to save user';
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
      const isActive = u.is_active !== false;
      const pin = u.pin_code || (isActive ? '' : '—');
      const rowClass = isActive
        ? 'border-b border-slate-100'
        : 'border-b border-slate-100 opacity-50 bg-slate-50 text-slate-500';
      const archivedBadge = isActive
        ? ''
        : '<span class="ml-2 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-slate-200 text-slate-600">Archived</span>';
      const editBtn = isActive
        ? `<button type="button" class="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded border border-slate-200 text-sm" data-edit-user-id="${u.id}">Edit</button>`
        : '<span class="text-xs text-slate-400">—</span>';
      return `
        <tr class="${rowClass}">
          <td class="py-2">${escapeHtml(u.username)}</td>
          <td class="py-2">${escapeHtml(u.role)}${archivedBadge}</td>
          <td class="py-2 font-medium">${escapeHtml(pin)}</td>
          <td class="py-2 text-right">${editBtn}</td>
        </tr>
      `;
    })
    .join('');

  tbody.querySelectorAll('[data-edit-user-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.dataset.editUserId, 10);
      const user = usersState.find((x) => x.id === id);
      if (!user || user.is_active === false) return;
      selectedUserId = user.id;
      document.getElementById('user-id').value = user.id;
      document.getElementById('user-username').value = user.username || '';
      document.getElementById('user-role').value = user.role || 'waiter';
      document.getElementById('user-pin').value = user.pin_code || '';
      document.getElementById('user-form-title').textContent = 'Edit Staff';
      document.getElementById('btn-delete-user').classList.remove('hidden');
      syncStaffRoleFields();
      renderUserPinValidationState();
    });
  });
}

function resetUserForm() {
  selectedUserId = null;
  const userIdEl = document.getElementById('user-id');
  if (userIdEl) userIdEl.value = '';
  const titleEl = document.getElementById('user-form-title');
  if (titleEl) titleEl.textContent = 'Create Staff';
  const deleteBtn = document.getElementById('btn-delete-user');
  if (deleteBtn) deleteBtn.classList.add('hidden');
  const usernameEl = document.getElementById('user-username');
  const roleEl = document.getElementById('user-role');
  const pinEl = document.getElementById('user-pin');
  const pinWarningEl = document.getElementById('user-pin-warning');
  if (usernameEl) usernameEl.value = '';
  if (roleEl) roleEl.value = 'waiter';
  if (pinEl) pinEl.value = '';
  const accountPassEl = document.getElementById('user-account-password');
  if (accountPassEl) accountPassEl.value = '';
  syncStaffRoleFields();
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

// —— Root Admin Account Management ——
let rootAdminsState = [];
let selectedAdminId = null;

async function fetchRootAdmins() {
  const res = await fetch(`${API_BASE}/api/root/admins`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to fetch admin accounts');
  }
  return res.json();
}

function renderRootAdmins(admins) {
  rootAdminsState = admins || [];
  const tbody = document.getElementById('admins-table-body');
  if (!tbody) return;
  if (!rootAdminsState.length) {
    tbody.innerHTML = '<tr><td colspan="2" class="py-3 text-slate-500">No admin accounts</td></tr>';
    return;
  }
  tbody.innerHTML = rootAdminsState
    .map((u) => {
      return `
        <tr class="border-b border-slate-100">
          <td class="py-2">${escapeHtml(u.username)}</td>
          <td class="py-2 text-right">
            <button type="button" class="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded border border-slate-200 text-sm" data-edit-admin-id="${u.id}">
              Edit
            </button>
          </td>
        </tr>
      `;
    })
    .join('');

  tbody.querySelectorAll('[data-edit-admin-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.dataset.editAdminId, 10);
      const admin = rootAdminsState.find((x) => x.id === id);
      if (!admin) return;
      selectedAdminId = admin.id;
      document.getElementById('admin-id').value = admin.id;
      document.getElementById('admin-username').value = admin.username || '';
      document.getElementById('admin-password').value = '';
      document.getElementById('admin-form-title').textContent = 'Edit Admin';
      document.getElementById('btn-delete-admin').classList.remove('hidden');
      document.getElementById('btn-reset-admin-password').classList.remove('hidden');
      syncAdminFormMode(true);
    });
  });
}

function syncAdminFormMode(isEdit) {
  const passwordEl = document.getElementById('admin-password');
  const hintEl = document.getElementById('admin-password-hint');
  if (!passwordEl) return;
  passwordEl.required = !isEdit;
  if (hintEl) {
    hintEl.textContent = isEdit
      ? 'Leave blank to keep current password.'
      : 'Min 6 characters (required for new admin).';
  }
}

function resetAdminForm() {
  selectedAdminId = null;
  const idEl = document.getElementById('admin-id');
  if (idEl) idEl.value = '';
  document.getElementById('admin-form-title').textContent = 'Create Admin';
  document.getElementById('admin-username').value = '';
  document.getElementById('admin-password').value = '';
  document.getElementById('btn-delete-admin').classList.add('hidden');
  document.getElementById('btn-reset-admin-password').classList.add('hidden');
  syncAdminFormMode(false);
}

async function loadRootAdmins() {
  try {
    const admins = await fetchRootAdmins();
    renderRootAdmins(admins);
  } catch (e) {
    console.error(e);
    const tbody = document.getElementById('admins-table-body');
    if (tbody) tbody.innerHTML = '<tr><td colspan="2" class="py-3 text-red-600">Error loading admins.</td></tr>';
  }
}

const AUDIT_ACTION_LABELS = {
  admin_create_staff: 'Admin created staff',
  admin_update_staff: 'Admin updated staff',
  admin_delete_staff: 'Admin deleted staff',
  root_create_admin: 'Root created admin',
  root_update_admin: 'Root updated admin',
  root_delete_admin: 'Root deleted admin',
  root_reset_admin_password: 'Root reset admin password',
};

function formatAuditAction(action) {
  return AUDIT_ACTION_LABELS[action] || action || '—';
}

function formatAuditTimestamp(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString();
}

function summarizeAuditUser(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return '';
  const parts = [];
  if (snapshot.username) parts.push(`@${snapshot.username}`);
  if (snapshot.role) parts.push(`role: ${snapshot.role}`);
  if (snapshot.is_deleted) parts.push('deleted');
  return parts.join(', ');
}

function formatAuditDetails(detail) {
  if (!detail || typeof detail !== 'object') return '—';
  const bits = [];
  if (detail.pin_set) bits.push('PIN assigned');
  if (detail.pin_changed) bits.push('PIN changed');
  const before = summarizeAuditUser(detail.before);
  const after = summarizeAuditUser(detail.after);
  if (before && after && before !== after) {
    bits.push(`${before} → ${after}`);
  } else if (after) {
    bits.push(after);
  } else if (before) {
    bits.push(before);
  }
  return bits.length ? bits.join(' · ') : '—';
}

function getAuditLogFilters() {
  const action = document.getElementById('audit-filter-action')?.value?.trim() || '';
  const start = document.getElementById('audit-filter-start')?.value || '';
  const end = document.getElementById('audit-filter-end')?.value || '';
  const params = new URLSearchParams();
  params.set('limit', '200');
  if (action) params.set('action', action);
  if (start) params.set('start_date', start);
  if (end) params.set('end_date', end);
  return params;
}

async function fetchAuditLogs() {
  const params = getAuditLogFilters();
  const res = await fetch(`${API_BASE}/api/root/audit-logs?${params.toString()}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) {
    throw new Error('unauthorized');
  }
  if (res.status === 403) {
    throw new Error('forbidden');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Failed to load audit logs';
    throw new Error(detail);
  }
  return Array.isArray(data) ? data : [];
}

function renderAuditLogs(rows) {
  const tbody = document.getElementById('audit-logs-table-body');
  const status = document.getElementById('audit-logs-status');
  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="py-4 px-3 text-slate-500">No audit entries match the current filters.</td></tr>';
    if (status) status.textContent = '0 entries';
    return;
  }

  tbody.innerHTML = rows
    .map((row) => {
      const actor = row.actor_username ? `${escapeHtml(row.actor_username)} (#${row.actor_user_id})` : `#${row.actor_user_id}`;
      const target = row.target_username
        ? `${escapeHtml(row.target_username)}${row.target_user_id ? ` (#${row.target_user_id})` : ''}`
        : row.target_user_id
          ? `#${row.target_user_id}`
          : '—';
      return `
        <tr class="border-b border-slate-100 align-top">
          <td class="py-3 px-3 whitespace-nowrap text-slate-600">${escapeHtml(formatAuditTimestamp(row.created_at))}</td>
          <td class="py-3 px-3">${actor}</td>
          <td class="py-3 px-3">
            <span class="inline-block px-2 py-0.5 rounded bg-slate-100 text-slate-800 text-xs font-medium">${escapeHtml(formatAuditAction(row.action))}</span>
          </td>
          <td class="py-3 px-3">${target}</td>
          <td class="py-3 px-3 text-slate-600">${escapeHtml(formatAuditDetails(row.detail_json))}</td>
        </tr>
      `;
    })
    .join('');

  if (status) {
    status.textContent = `${rows.length} entr${rows.length === 1 ? 'y' : 'ies'} loaded`;
  }
}

async function loadAuditLogs() {
  const tbody = document.getElementById('audit-logs-table-body');
  const status = document.getElementById('audit-logs-status');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="5" class="py-4 px-3 text-slate-500">Loading…</td></tr>';
  }
  if (status) status.textContent = 'Loading audit logs…';

  try {
    const rows = await fetchAuditLogs();
    renderAuditLogs(rows);
  } catch (e) {
    console.error(e);
    const msg = e.message === 'forbidden'
      ? 'Access denied. Audit logs are root-only.'
      : (e.message || 'Error loading audit logs.');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-4 px-3 text-red-600">${escapeHtml(msg)}</td></tr>`;
    }
    if (status) status.textContent = 'Failed to load';
    if (e.message === 'forbidden' && window.toast) {
      window.toast.error('Audit logs are only available to the root account.');
    }
  }
}

const btnRefreshAuditLogs = document.getElementById('btn-refresh-audit-logs');
if (btnRefreshAuditLogs) {
  btnRefreshAuditLogs.addEventListener('click', () => loadAuditLogs());
}

const btnApplyAuditFilters = document.getElementById('btn-apply-audit-filters');
if (btnApplyAuditFilters) {
  btnApplyAuditFilters.addEventListener('click', () => loadAuditLogs());
}

function syncStaffRoleFields() {
  const roleEl = document.getElementById('user-role');
  const pinWrap = document.getElementById('user-pin-wrap');
  const accountWrap = document.getElementById('user-account-password-wrap');
  const pinEl = document.getElementById('user-pin');
  if (!roleEl) return;
  const isAccount = roleEl.value === 'account';
  if (pinWrap) pinWrap.classList.toggle('hidden', isAccount);
  if (accountWrap) accountWrap.classList.toggle('hidden', !isAccount);
  if (pinEl) pinEl.required = !isAccount;
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
  const roleEl = document.getElementById('user-role');
  if (roleEl) {
    roleEl.addEventListener('change', syncStaffRoleFields);
    syncStaffRoleFields();
  }
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
    const accountPassword = document.getElementById('user-account-password')?.value || '';

    if (!username) {
      if (window.toast) window.toast.error('Username is required.');
      return;
    }
    if (role === 'account') {
      if (!userId && accountPassword.length < 6) {
        if (window.toast) window.toast.error('Account password must be at least 6 characters.');
        return;
      }
    } else if (!renderUserPinValidationState() || !pin) {
      if (window.toast) window.toast.error('PIN must be exactly 4 digits.');
      return;
    }

    const method = userId ? 'PUT' : 'POST';
    const url = userId
      ? `${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`
      : `${API_BASE}/api/admin/users`;

    const payload = { username, role };
    if (role === 'account') {
      payload.pin_code = null;
      if (accountPassword) payload.password = accountPassword;
    } else {
      payload.pin_code = pin;
    }

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify(payload),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        await dialogAlert(formatUserSaveError(data.detail), 'error', 'Save User');
        return;
      }
      if (window.toast) window.toast.success('User saved successfully.');
      resetUserForm();
      await loadUsers();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to save user', 'error', 'Save User');
    }
  });
}

const btnDeleteUser = document.getElementById('btn-delete-user');
if (btnDeleteUser) {
  btnDeleteUser.addEventListener('click', async () => {
    const userId = document.getElementById('user-id').value;
    if (!userId) return;
    const ok = await dialogConfirm('Delete this user?', 'Delete User');
    if (!ok) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
        method: 'DELETE',
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        await dialogAlert(data.detail || 'Delete failed', 'error', 'Delete User');
        return;
      }
      if (window.toast) window.toast.success('User deleted.');
      resetUserForm();
      await loadUsers();
    } catch (e) {
      console.error(e);
      await dialogAlert('Delete failed', 'error', 'Delete User');
    }
  });
}

const btnResetUser = document.getElementById('btn-reset-user');
if (btnResetUser) {
  btnResetUser.addEventListener('click', () => resetUserForm());
}

// Bind Root Admin Management UI
const adminForm = document.getElementById('admin-form');
if (adminForm) {
  adminForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const adminId = document.getElementById('admin-id').value;
    const username = document.getElementById('admin-username').value.trim().toLowerCase();
    const password = document.getElementById('admin-password').value;

    if (!username) {
      if (window.toast) window.toast.error('Username is required.');
      return;
    }
    if (!adminId && (!password || password.length < 6)) {
      if (window.toast) window.toast.error('Password must be at least 6 characters.');
      return;
    }

    const method = adminId ? 'PUT' : 'POST';
    const url = adminId
      ? `${API_BASE}/api/root/admins/${encodeURIComponent(adminId)}`
      : `${API_BASE}/api/root/admins`;
    const payload = { username, password: password || '' };

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify(payload),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === 'string' ? detail : 'Failed to save admin';
        await dialogAlert(msg, 'error', 'Save Admin');
        return;
      }
      if (window.toast) window.toast.success('Admin saved successfully.');
      resetAdminForm();
      await loadRootAdmins();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to save admin', 'error', 'Save Admin');
    }
  });
}

const btnDeleteAdmin = document.getElementById('btn-delete-admin');
if (btnDeleteAdmin) {
  btnDeleteAdmin.addEventListener('click', async () => {
    const adminId = document.getElementById('admin-id').value;
    if (!adminId) return;
    const ok = await dialogConfirm('Delete this admin account?', 'Delete Admin');
    if (!ok) return;
    try {
      const res = await fetch(`${API_BASE}/api/root/admins/${encodeURIComponent(adminId)}`, {
        method: 'DELETE',
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        await dialogAlert(data.detail || 'Delete failed', 'error', 'Delete Admin');
        return;
      }
      if (window.toast) window.toast.success('Admin deleted.');
      resetAdminForm();
      await loadRootAdmins();
    } catch (e) {
      console.error(e);
      await dialogAlert('Delete failed', 'error', 'Delete Admin');
    }
  });
}

const btnResetAdminPassword = document.getElementById('btn-reset-admin-password');
if (btnResetAdminPassword) {
  btnResetAdminPassword.addEventListener('click', async () => {
    const adminId = document.getElementById('admin-id').value;
    if (!adminId) return;
    const newPassword = window.prompt('Enter new password for this admin (min 6 characters):');
    if (!newPassword) return;
    if (newPassword.length < 6) {
      if (window.toast) window.toast.error('Password must be at least 6 characters.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/root/admins/${encodeURIComponent(adminId)}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ new_password: newPassword }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        await dialogAlert(data.detail || 'Reset failed', 'error', 'Reset Password');
        return;
      }
      if (window.toast) window.toast.success('Admin password reset.');
    } catch (e) {
      console.error(e);
      await dialogAlert('Reset failed', 'error', 'Reset Password');
    }
  });
}

const btnResetAdminForm = document.getElementById('btn-reset-admin-form');
if (btnResetAdminForm) {
  btnResetAdminForm.addEventListener('click', () => resetAdminForm());
}

syncAdminFormMode(false);

// —— Admin Table Management (Zones + Tables) ——
let zonesState = [];
let addTableZoneId = null;
let editTableId = null;

async function fetchTableGrid() {
  const res = await fetch(`${API_BASE}/api/tables/grid?_ts=${Date.now()}`, {
    cache: 'no-store',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch table grid');
  return data;
}

async function deleteTableById(tableId) {
  const res = await fetch(`${API_BASE}/api/tables/${encodeURIComponent(tableId)}`, {
    method: 'DELETE',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return { unauthorized: true };
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : 'Delete failed';
    throw new Error(detail);
  }
  return data;
}

function tableDisplayName(t) {
  return t.name || t.name_or_number || `#${t.id}`;
}

function orderTableLabel(order) {
  const isTakeaway = String(order?.order_type || '').toLowerCase() === 'takeaway';
  if (isTakeaway) return t('takeaway', 'Takeaway');
  if (order?.table_id == null && order?.table_number == null) return t('deleted_table', '[Deleted Table]');
  if (order?.table_number != null) return order.table_number;
  return t('unknown', 'Unknown');
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
                ${(() => {
                  const isEdit = editTableId === table.id;
                  if (isEdit) {
                    const zoneOptions = zonesState
                      .map((z) => `<option value="${z.id}" ${Number(z.id) === Number(table.zone_id) ? 'selected' : ''}>${escapeHtml(z.name)}</option>`)
                      .join('');
                    return `
                <div class="bg-white border border-slate-200 rounded-md px-2 py-2 space-y-2">
                  <input
                    type="text"
                    data-edit-table-input-id="${table.id}"
                    value="${escapeAttr(tableDisplayName(table))}"
                    class="w-full px-2 py-1.5 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <select
                    data-edit-table-zone-id="${table.id}"
                    class="w-full px-2 py-1.5 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    ${zoneOptions}
                  </select>
                  <div class="flex items-center justify-end gap-2">
                    <button type="button" data-save-edit-table-id="${table.id}" class="px-2 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
                    <button type="button" data-cancel-edit-table-id="${table.id}" class="px-2 py-1.5 text-xs bg-slate-200 text-slate-800 rounded hover:bg-slate-300">Cancel</button>
                  </div>
                </div>
                    `;
                  }
                  return `
                <div class="bg-white border border-slate-200 rounded-md px-2 py-1.5 flex items-center justify-between">
                  <span class="text-xs font-medium text-slate-800 truncate pr-2">${escapeHtml(tableDisplayName(table))}</span>
                  <div class="flex items-center gap-1">
                    <button type="button" data-edit-table-id="${table.id}" class="w-6 h-6 rounded bg-blue-100 text-blue-700 hover:bg-blue-200 text-xs" title="Edit table">✎</button>
                    <button type="button" data-delete-table-id="${table.id}" class="w-6 h-6 rounded bg-rose-100 text-rose-700 hover:bg-rose-200 text-xs" title="Delete table">✕</button>
                  </div>
                </div>
                  `;
                })()}
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
        await dialogAlert(data.detail || 'Failed to create zone', 'error', 'Create Zone');
        return;
      }
      if (window.toast) window.toast.success('Zone created.');
      zoneNameInput.value = '';
      await loadTableManagementData();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to create zone', 'error', 'Create Zone');
    }
  });
}

const kanbanBoard = document.getElementById('kanban-zones-board');
if (kanbanBoard) {
  kanbanBoard.addEventListener('click', async (e) => {
    const target = e.target;
    const deleteZoneBtn = target.closest('[data-delete-zone-id]');
    const deleteTableBtn = target.closest('[data-delete-table-id]');
    const editTableBtn = target.closest('[data-edit-table-id]');
    const saveEditTableBtn = target.closest('[data-save-edit-table-id]');
    const cancelEditTableBtn = target.closest('[data-cancel-edit-table-id]');
    const openAddBtn = target.closest('[data-open-add-table-zone-id]');
    const cancelAddBtn = target.closest('[data-cancel-table-zone-id]');
    const saveTableBtn = target.closest('[data-save-table-zone-id]');

    if (deleteZoneBtn) {
      const zoneId = deleteZoneBtn.getAttribute('data-delete-zone-id');
      if (!zoneId) return;
      const zone = (zonesState || []).find((z) => Number(z.id) === Number(zoneId));
      const zoneName = zone?.name || `#${zoneId}`;
      const zoneConfirm = await dialogConfirm(
        `Are you sure you want to delete Zone ${zoneName} and its tables? This action cannot be undone.`,
        'Delete Zone'
      );
      if (!zoneConfirm) return;
      try {
        const res = await fetch(`${API_BASE}/api/zones/${encodeURIComponent(zoneId)}`, {
          method: 'DELETE',
          headers: { ...window.auth.getAuthHeaders() },
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          await dialogAlert(data.detail || 'Delete failed', 'error', 'Delete Zone');
          return;
        }
        if (window.toast) window.toast.success('Zone deleted.');
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        await dialogAlert('Delete failed', 'error', 'Delete Zone');
      }
      return;
    }

    if (deleteTableBtn) {
      const tableId = deleteTableBtn.getAttribute('data-delete-table-id');
      if (!tableId) return;
      const table = (zonesState || [])
        .flatMap((z) => z.tables || [])
        .find((t) => Number(t.id) === Number(tableId));
      const tableName = table?.name || table?.name_or_number || `#${tableId}`;
      const tableConfirm = await dialogConfirm(
        `Are you sure you want to delete Table ${tableName}? This action cannot be undone.`,
        'Delete Table'
      );
      if (!tableConfirm) return;
      try {
        const result = await deleteTableById(tableId);
        if (result && result.unauthorized) return;
        // Keep UI responsive even before round-trip reload completes.
        zonesState = (zonesState || []).map((zone) => ({
          ...zone,
          tables: (zone.tables || []).filter((t) => Number(t.id) !== Number(tableId)),
        }));
        renderTableKanbanBoard(zonesState);
        if (window.toast) window.toast.success('Table deleted.');
        try {
          await loadTableManagementData();
        } catch (refreshErr) {
          console.error(refreshErr);
          if (window.toast) window.toast.error('Table list refresh failed. Please reload.');
        }
      } catch (err) {
        console.error(err);
        const message = err && err.message ? err.message : 'Delete failed';
        if (window.toast) window.toast.error(message);
        await dialogAlert(message, 'error', 'Delete Table');
      }
      return;
    }

    if (editTableBtn) {
      const tableId = Number(editTableBtn.getAttribute('data-edit-table-id'));
      if (!tableId) return;
      editTableId = tableId;
      addTableZoneId = null;
      renderTableKanbanBoard(zonesState);
      const input = document.querySelector(`[data-edit-table-input-id="${tableId}"]`);
      if (input) input.focus();
      return;
    }

    if (cancelEditTableBtn) {
      editTableId = null;
      renderTableKanbanBoard(zonesState);
      return;
    }

    if (saveEditTableBtn) {
      const tableId = Number(saveEditTableBtn.getAttribute('data-save-edit-table-id'));
      const nameInput = document.querySelector(`[data-edit-table-input-id="${tableId}"]`);
      const zoneSelect = document.querySelector(`[data-edit-table-zone-id="${tableId}"]`);
      const tableName = (nameInput && nameInput.value || '').trim();
      const zoneId = Number(zoneSelect && zoneSelect.value);
      if (!tableName || !zoneId) {
        if (window.toast) window.toast.error('Please provide table name and zone.');
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/tables/${encodeURIComponent(tableId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
          body: JSON.stringify({ name: tableName, zone_id: zoneId }),
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          await dialogAlert(data.detail || 'Failed to update table', 'error', 'Edit Table');
          return;
        }
        if (window.toast) window.toast.success('Table updated.');
        editTableId = null;
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        await dialogAlert('Failed to update table', 'error', 'Edit Table');
      }
      return;
    }

    if (openAddBtn) {
      addTableZoneId = Number(openAddBtn.getAttribute('data-open-add-table-zone-id'));
      editTableId = null;
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
          await dialogAlert(data.detail || 'Failed to create table', 'error', 'Create Table');
          return;
        }
        if (window.toast) window.toast.success('Table created.');
        addTableZoneId = null;
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        await dialogAlert('Failed to create table', 'error', 'Create Table');
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
        await dialogAlert(data.detail || 'Failed to create table', 'error', 'Create Table');
        return;
      }
      if (window.toast) window.toast.success('Table created.');
      addTableZoneId = null;
      await loadTableManagementData();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to create table', 'error', 'Create Table');
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

async function toggleMenuItemPromoted(itemId) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}/toggle-promoted`, {
    method: 'PUT',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Failed to toggle promoted flag');
  if (window.toast) {
    window.toast.success(data.is_promoted ? 'Item marked as promoted.' : 'Item unmarked as promoted.');
  }
  return data;
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

async function updateMenuItem(itemId, payload) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      Array.isArray(data.detail)
        ? data.detail.map((x) => x.msg || x).join(', ')
        : (data.detail || 'Failed to update menu item')
    );
  }
  if (window.toast) window.toast.success('Menu item updated.');
  return data;
}

function resetMenuItemFormMode() {
  const form = document.getElementById('form-menu-item');
  const title = document.getElementById('menu-form-title');
  const btn = document.getElementById('btn-submit-menu-item');
  const cancelBtn = document.getElementById('btn-cancel-menu-edit');
  const editId = document.getElementById('menu-edit-item-id');
  if (!form || !title || !btn || !cancelBtn || !editId) return;
  form.removeAttribute('data-mode');
  title.textContent = 'Add Menu Item';
  btn.textContent = 'Add Menu Item';
  btn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
  btn.classList.add('bg-emerald-600', 'hover:bg-emerald-700');
  cancelBtn.classList.add('hidden');
  editId.value = '';
  const discountInput = document.getElementById('item-discount-price');
  const promotedInput = document.getElementById('item-is-promoted');
  if (discountInput) discountInput.value = '';
  if (promotedInput) promotedInput.checked = false;
}

function startMenuItemEdit(itemId) {
  const item = menuItemsCache.find((m) => Number(m.id) === Number(itemId));
  if (!item) return;
  const title = document.getElementById('menu-form-title');
  const btn = document.getElementById('btn-submit-menu-item');
  const cancelBtn = document.getElementById('btn-cancel-menu-edit');
  const editId = document.getElementById('menu-edit-item-id');
  const form = document.getElementById('form-menu-item');
  if (!title || !btn || !cancelBtn || !editId || !form) return;

  title.textContent = 'Edit Menu Item';
  btn.textContent = 'Update Menu Item';
  btn.classList.remove('bg-emerald-600', 'hover:bg-emerald-700');
  btn.classList.add('bg-blue-600', 'hover:bg-blue-700');
  cancelBtn.classList.remove('hidden');
  form.setAttribute('data-mode', 'edit');
  editId.value = String(item.id);

  document.getElementById('item-name').value = item.name || '';
  document.getElementById('item-price').value = Number(item.price || 0);
  document.getElementById('item-discount-price').value = item.discount_price != null ? Number(item.discount_price) : '';
  document.getElementById('item-description').value = item.description || '';
  document.getElementById('item-category').value = String(item.category_id || '');
  document.getElementById('item-image-url').value = item.image_url || '';
  document.getElementById('item-image-file').value = '';
  const promotedInput = document.getElementById('item-is-promoted');
  if (promotedInput) promotedInput.checked = !!item.is_promoted;
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function printerRouteLabel(route) {
  const normalized = String(route || '').trim().toLowerCase();
  if (normalized === 'drinks') return 'Drinks';
  if (normalized === 'food') return 'Food counter';
  return 'Food counter (default)';
}

function renderCategories(categories) {
  const el = document.getElementById('categories-list');
  if (!categories.length) {
    el.innerHTML = '<li class="text-slate-500">No categories yet.</li>';
    return;
  }
  el.innerHTML = categories
    .map((c) => {
      const currentRoute = String(c.printer_route || '').trim().toLowerCase();
      return `
        <li class="py-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-100">
          <div>
            <span class="font-medium text-slate-800">${escapeHtml(c.name)}</span>
            <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">${escapeHtml(printerRouteLabel(currentRoute))}</span>
          </div>
          <div class="flex items-center gap-2">
            <select data-category-route-id="${c.id}" class="text-sm px-2 py-1 border border-slate-300 rounded-md">
              <option value="" ${currentRoute === '' ? 'selected' : ''}>Default (Food)</option>
              <option value="food" ${currentRoute === 'food' ? 'selected' : ''}>Food counter</option>
              <option value="drinks" ${currentRoute === 'drinks' ? 'selected' : ''}>Drinks</option>
            </select>
            <button type="button" data-save-category-route-id="${c.id}" class="text-xs px-2 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700">Save</button>
          </div>
        </li>
      `;
    })
    .join('');

  el.querySelectorAll('[data-save-category-route-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const categoryId = Number(btn.getAttribute('data-save-category-route-id'));
      const select = el.querySelector(`[data-category-route-id="${categoryId}"]`);
      if (!categoryId || !select) return;
      const routeValue = String(select.value || '').trim();
      const payload = routeValue ? { printer_route: routeValue } : { printer_route: null };
      btn.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/api/categories/${encodeURIComponent(categoryId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
          body: JSON.stringify(payload),
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          await dialogAlert(err.detail || 'Failed to update printer route', 'error', 'Category Printer');
          return;
        }
        await loadMenuData();
      } catch (err) {
        console.error(err);
        await dialogAlert('Failed to update printer route', 'error', 'Category Printer');
      } finally {
        btn.disabled = false;
      }
    });
  });
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
      const hasDiscount = Number(m.discount_price) > 0;
      const priceLabel = hasDiscount
        ? `<span class="truncate">${escapeHtml(m.name)} — <span class="line-through text-slate-400 text-xs">${formatMoney(Number(m.price))}</span> <span class="text-rose-600 font-semibold">${formatMoney(Number(m.discount_price))}</span></span>`
        : `<span class="truncate">${escapeHtml(m.name)} — ${formatMoney(Number(m.price))}</span>`;
      const badge = available
        ? '<span class="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Available</span>'
        : '<span class="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Sold Out</span>';
      const promoted = m.is_promoted === true;
      const promotedBadge = promoted
        ? '<span class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold">★ Promoted</span>'
        : '';
      const promoBtnLabel = promoted ? 'Unpromote' : 'Promote';
      const promoBtnClass = promoted ? 'bg-amber-700 hover:bg-amber-800' : 'bg-amber-500 hover:bg-amber-600';
      const btnLabel = available ? 'Disable' : 'Enable';
      const btnClass = available
        ? 'bg-red-600 hover:bg-red-700'
        : 'bg-emerald-600 hover:bg-emerald-700';
      return `
        <li class="py-2 flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 min-w-0">
            ${img}
            ${priceLabel}
            ${badge}
            ${promotedBadge}
          </div>
          <div class="flex items-center gap-2 flex-wrap justify-end">
            <button
              type="button"
              data-toggle-promoted-id="${m.id}"
              class="text-xs text-white px-3 py-1 rounded ${promoBtnClass}"
            >
              ${promoBtnLabel}
            </button>
            <button
              type="button"
              data-edit-menu-item-id="${m.id}"
              class="text-xs text-white px-3 py-1 rounded bg-blue-600 hover:bg-blue-700"
            >
              Edit
            </button>
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

  el.querySelectorAll('[data-toggle-promoted-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = Number(btn.getAttribute('data-toggle-promoted-id'));
      if (!itemId) return;
      btn.disabled = true;
      try {
        await toggleMenuItemPromoted(itemId);
        await loadMenuData();
      } catch (err) {
        console.error(err);
        await dialogAlert(err.message || 'Failed to update promoted flag', 'error', 'Promoted Item');
        btn.disabled = false;
      }
    });
  });

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
        await dialogAlert(err.message || 'Failed to update availability', 'error', 'Update Item');
        btn.disabled = false;
      }
    });
  });

  el.querySelectorAll('[data-edit-menu-item-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const itemId = Number(btn.getAttribute('data-edit-menu-item-id'));
      if (!itemId) return;
      startMenuItemEdit(itemId);
    });
  });

  el.querySelectorAll('[data-delete-menu-item-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = Number(btn.getAttribute('data-delete-menu-item-id'));
      if (!itemId) return;
      const confirmed = await dialogConfirm('Delete this menu item permanently?', 'Delete Menu Item');
      if (!confirmed) return;
      btn.disabled = true;
      try {
        await deleteMenuItem(itemId);
        await loadMenuData();
      } catch (err) {
        console.error(err);
        await dialogAlert(err.message || 'Failed to delete menu item', 'error', 'Delete Menu Item');
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

const kitchenPrinterForm = document.getElementById('form-kitchen-printers');
if (kitchenPrinterForm) {
  kitchenPrinterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const backend = String(document.getElementById('printer-backend')?.value || 'file').trim();
    const renderMode = String(document.getElementById('printer-render-mode')?.value || 'text').trim();
    const paperWidth = Number(document.getElementById('printer-paper-width')?.value || 576);
    const drinksHost = String(document.getElementById('printer-drinks-host')?.value || '').trim();
    const drinksPort = Number(document.getElementById('printer-drinks-port')?.value || 9100);
    const foodHost = String(document.getElementById('printer-food-host')?.value || '').trim();
    const foodPort = Number(document.getElementById('printer-food-port')?.value || 9100);
    const payload = {
      backend,
      render_mode: renderMode,
      paper_width_px: paperWidth,
      routes: [
        { route_key: 'drinks', host: drinksHost || null, port: drinksPort || 9100 },
        { route_key: 'food', host: foodHost || null, port: foodPort || 9100 },
      ],
    };
    try {
      const res = await fetch(`${API_BASE}/api/admin/kitchen-printers`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify(payload),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await dialogAlert(err.detail || 'Failed to save printer settings', 'error', 'Printer Settings');
        return;
      }
      await loadKitchenPrinterSettings();
      await dialogAlert('Printer settings saved.', 'success', 'Printer Settings');
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to save printer settings', 'error', 'Printer Settings');
    }
  });
}

async function loadKitchenPrinterSettings() {
  const form = document.getElementById('form-kitchen-printers');
  if (!form) return;
  try {
    const res = await fetch(`${API_BASE}/api/admin/kitchen-printers`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) throw new Error('Failed to load kitchen printer settings');
    const data = await res.json();
    const backendEl = document.getElementById('printer-backend');
    const renderModeEl = document.getElementById('printer-render-mode');
    const paperWidthEl = document.getElementById('printer-paper-width');
    if (backendEl) backendEl.value = data.backend || 'file';
    if (renderModeEl) renderModeEl.value = data.render_mode || 'text';
    if (paperWidthEl) paperWidthEl.value = String(data.paper_width_px || 576);
    const routeMap = Object.fromEntries((data.routes || []).map((r) => [r.route_key, r]));
    const drinks = routeMap.drinks || {};
    const food = routeMap.food || {};
    const drinksHost = document.getElementById('printer-drinks-host');
    const drinksPort = document.getElementById('printer-drinks-port');
    const foodHost = document.getElementById('printer-food-host');
    const foodPort = document.getElementById('printer-food-port');
    if (drinksHost) drinksHost.value = drinks.host || '';
    if (drinksPort) drinksPort.value = drinks.port || 9100;
    if (foodHost) foodHost.value = food.host || '';
    if (foodPort) foodPort.value = food.port || 9100;
  } catch (err) {
    console.error(err);
  }
}

async function loadMenuData() {
  try {
    await loadKitchenPrinterSettings();
    const [categories, menuItems] = await Promise.all([fetchCategories(), fetchMenuItems()]);
    menuItemsCache = menuItems || [];
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
  const routeSelect = document.getElementById('category-printer-route');
  const name = input.value.trim();
  if (!name) return;
  const routeValue = routeSelect ? String(routeSelect.value || '').trim() : '';
  const payload = { name };
  if (routeValue) payload.printer_route = routeValue;
  try {
    const res = await fetch(`${API_BASE}/api/categories/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify(payload),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      await dialogAlert(err.detail || 'Failed to create category', 'error', 'Create Category');
      return;
    }
    input.value = '';
    if (routeSelect) routeSelect.value = '';
    await loadMenuData();
  } catch (err) {
    console.error(err);
    await dialogAlert('Failed to create category', 'error', 'Create Category');
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
      await dialogAlert(data.detail || 'Upload failed', 'error', 'Upload Failed');
      return;
    }
    document.getElementById('item-image-url').value = data.url || '';
  } catch (err) {
    console.error(err);
    await dialogAlert('Upload failed', 'error', 'Upload Failed');
  }
  e.target.value = '';
});

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = document.getElementById('form-menu-item');
  const name = document.getElementById('item-name').value.trim();
  const price = parseFloat(document.getElementById('item-price').value);
  const discountPriceRaw = document.getElementById('item-discount-price').value.trim();
  const discountPrice = discountPriceRaw === '' ? null : parseFloat(discountPriceRaw);
  const description = document.getElementById('item-description').value.trim() || null;
  const categoryId = document.getElementById('item-category').value;
  const imageUrl = document.getElementById('item-image-url').value.trim() || null;
  const imageFile = document.getElementById('item-image-file').files?.[0];
  const isPromoted = !!document.getElementById('item-is-promoted')?.checked;
  const editItemId = Number(document.getElementById('menu-edit-item-id').value || 0);
  const isEditMode = form?.getAttribute('data-mode') === 'edit' && !!editItemId;
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  if (discountPrice !== null && (Number.isNaN(discountPrice) || discountPrice < 0)) return;
  if (imageFile && !imageUrl) {
    await dialogAlert('Please wait for image upload to finish.', 'error', 'Upload In Progress');
    return;
  }
  const btn = document.getElementById('btn-submit-menu-item');
  btn.disabled = true;
  try {
    if (isEditMode) {
      await updateMenuItem(editItemId, {
        name,
        price,
        discount_price: discountPrice,
        category_id: parseInt(categoryId, 10),
        description,
        image_url: imageUrl,
        is_promoted: isPromoted,
      });
    } else {
      const res = await fetch(`${API_BASE}/api/menu-items/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({
          name,
          price,
          discount_price: discountPrice,
          category_id: parseInt(categoryId, 10),
          description,
          image_url: imageUrl,
          is_promoted: isPromoted,
        }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        await dialogAlert(
          Array.isArray(data.detail) ? data.detail.map((x) => x.msg || x).join(', ') : (data.detail || 'Failed to create menu item'),
          'error',
          'Create Menu Item',
        );
        return;
      }
    }
    document.getElementById('item-name').value = '';
    document.getElementById('item-price').value = '';
    document.getElementById('item-discount-price').value = '';
    document.getElementById('item-description').value = '';
    document.getElementById('item-image-url').value = '';
    document.getElementById('item-category').value = '';
    document.getElementById('item-image-file').value = '';
    resetMenuItemFormMode();
    await loadMenuData();
  } catch (err) {
    console.error(err);
    await dialogAlert(err.message || (isEditMode ? 'Failed to update menu item' : 'Failed to create menu item'), 'error', 'Menu Item');
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('btn-cancel-menu-edit')?.addEventListener('click', () => {
  document.getElementById('item-name').value = '';
  document.getElementById('item-price').value = '';
  document.getElementById('item-discount-price').value = '';
  document.getElementById('item-description').value = '';
  document.getElementById('item-image-url').value = '';
  document.getElementById('item-category').value = '';
  document.getElementById('item-image-file').value = '';
  resetMenuItemFormMode();
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
        const tableRef = data.table_id || data.table_number;
        if (selectedOrderId != null && data.order_id === selectedOrderId && tableRef) {
          fetchActiveOrderByTable(tableRef)
            .then((order) => selectOrder(order))
            .catch(() => {});
        }
      }
      if (msg.event === 'order_updated' && msg.data && msg.data.status) {
        // Status changes (e.g. completed/cancelled) can affect which tables are active; refresh list.
        loadUnpaidOrders();
        if (
          String(msg.data.status || '').toLowerCase() === 'cancelled' &&
          selectedOrderId != null &&
          Number(msg.data.id) === Number(selectedOrderId)
        ) {
          selectedOrderId = null;
          selectedTableNumber = null;
          selectedOrderTotal = 0;
          selectedOrderSubtotal = 0;
          document.getElementById('receipt-container')?.classList.add('hidden');
          document.getElementById('receipt-placeholder')?.classList.remove('hidden');
        }
      }
      if (msg.event === 'table_grid_updated' || msg.event === 'table_status_changed') {
        loadUnpaidOrders();
        if (panelTables && !panelTables.classList.contains('hidden')) {
          loadTableManagementData();
        }
      }
      if (
        msg.event === 'menu_item_added' ||
        msg.event === 'menu_item_updated' ||
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

// Initial load only when authenticated and role-allowed.
if (
  window.auth &&
  window.auth.getToken() &&
  ['cashier', 'admin', 'root'].includes(String(window.auth.getUser?.()?.role || '').toLowerCase())
) {
  loadUnpaidOrders();
  loadMenuData();
  connectCounterWebSocket();
}
