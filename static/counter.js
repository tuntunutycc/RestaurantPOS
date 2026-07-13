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
let usersState = [];
let selectedUserId = null;
let rootAdminsState = [];
let selectedAdminId = null;
let zonesState = [];
let addTableZoneId = null;
let editTableId = null;
let menuItemsCache = [];
let categoriesCache = [];
let activeMenuCategoryId = null;

function setActiveMainTab(panel) {
  document.querySelectorAll('.tab-btn[data-target-panel]').forEach((btn) => {
    btn.classList.remove('active');
  });
  if (!panel || !panel.id) return;
  const activeBtn = document.querySelector(`.tab-btn[data-target-panel="${panel.id}"]`);
  if (activeBtn) activeBtn.classList.add('active');
}

function showPanel(panel) {
  if (!panel) return;
  if (panelDashboard) panelDashboard.classList.add('hidden');
  panelCashier.classList.add('hidden');
  panelMenu.classList.add('hidden');
  if (panelUsers) panelUsers.classList.add('hidden');
  if (panelAdmins) panelAdmins.classList.add('hidden');
  if (panelAuditLogs) panelAuditLogs.classList.add('hidden');
  if (panelTables) panelTables.classList.add('hidden');

  panel.classList.remove('hidden');
  setActiveMainTab(panel);

  if (panelDashboard && panel === panelDashboard) {
    loadDashboardSummary();
  } else if (panel === panelCashier) {
    loadUnpaidOrders();
  } else if (panel === panelMenu) {
    loadMenuData();
  } else if (panelUsers && panel === panelUsers) {
    loadUsers();
  } else if (panelAdmins && panel === panelAdmins) {
    loadRootAdmins();
  } else if (panelAuditLogs && panel === panelAuditLogs) {
    loadAuditLogs();
  } else if (panelTables && panel === panelTables) {
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
  if (nextTab === 'reports') {
    syncSalesReportPeriodInputs();
    if (!hasLoadedSalesReportsTab) {
      loadSalesPeriodReport();
      hasLoadedSalesReportsTab = true;
    } else {
      renderSalesReportMetrics();
    }
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
if (tabAdmins && panelAdmins) tabAdmins.addEventListener('click', () => showPanel(panelAdmins));
if (tabAuditLogs && panelAuditLogs) tabAuditLogs.addEventListener('click', () => showPanel(panelAuditLogs));
if (tabTables && panelTables) tabTables.addEventListener('click', () => showPanel(panelTables));
window.addEventListener('DOMContentLoaded', () => {
  setSalesHistoryDefaultDates();
  setStaffFilterDefaultDate();
  setSalesReportDefaultDates();
  bindSalesHistoryFilters();
  bindStaffBreakdownFilters();
  bindIncentivesFilters();
  bindSalesReportControls();
  bindDashboardSubTabs();
  initCashierNameInput();
  initCashierPrinterSelect();
});

const CASHIER_PRINTER_STORAGE_KEY = 'selectedCashierPrinterId';
const CASHIER_NAME_STORAGE_KEY = 'currentCashierName';

function getCurrentCashierName() {
  const input = document.getElementById('cashier-name-input');
  const fromInput = (input && input.value ? String(input.value) : '').trim();
  if (fromInput) return fromInput;
  return (localStorage.getItem(CASHIER_NAME_STORAGE_KEY) || '').trim();
}

function initCashierNameInput() {
  const input = document.getElementById('cashier-name-input');
  if (!input) return;
  const stored = (localStorage.getItem(CASHIER_NAME_STORAGE_KEY) || '').trim();
  if (stored) input.value = stored;
  const persist = () => {
    const value = String(input.value || '').trim();
    if (value) localStorage.setItem(CASHIER_NAME_STORAGE_KEY, value);
    else localStorage.removeItem(CASHIER_NAME_STORAGE_KEY);
  };
  input.addEventListener('change', persist);
  input.addEventListener('blur', persist);
}
async function initCashierPrinterSelect() {
  const select = document.getElementById('cashier-printer-select');
  if (!select) return;

  const applyStored = () => {
    const stored = localStorage.getItem(CASHIER_PRINTER_STORAGE_KEY);
    if (stored && [...select.options].some((o) => o.value === stored)) {
      select.value = stored;
    }
  };

  select.addEventListener('change', () => {
    const value = select.value;
    if (value) {
      localStorage.setItem(CASHIER_PRINTER_STORAGE_KEY, value);
    } else {
      localStorage.removeItem(CASHIER_PRINTER_STORAGE_KEY);
    }
  });

  try {
    const res = await fetch(`${API_BASE}/api/printers?role=cashier`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) return;
    const printers = await res.json();
    select.innerHTML = '';
    if (!Array.isArray(printers) || printers.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Default';
      select.appendChild(opt);
      return;
    }
    printers.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = String(p.id);
      const host = (p.host || '').trim();
      opt.textContent = host ? `${p.name} (${host})` : p.name;
      select.appendChild(opt);
    });
    applyStored();
    if (select.value) {
      localStorage.setItem(CASHIER_PRINTER_STORAGE_KEY, select.value);
    }
  } catch (e) {
    console.error('Failed to load cashier printers', e);
  }
}

function getSelectedCashierPrinterId() {
  const select = document.getElementById('cashier-printer-select');
  if (select && select.value) return Number(select.value);
  const stored = localStorage.getItem(CASHIER_PRINTER_STORAGE_KEY);
  if (stored && /^\d+$/.test(stored)) return Number(stored);
  return null;
}

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
  if (tabMenu) tabMenu.classList.remove('hidden');
  applyMenuPanelRoleVisibility(normalizedRole);
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
let selectedOrderVisibleItems = [];
/** @type {{ type: 'table'|'takeaway', id: number }|null} */
let cashierCheckoutSource = null;
let cashierZones = [];
let cashierActiveZoneId = null;
let hourlyChart = null;
let topItemsChart = null;
let dailySalesChart = null;
let monthlySalesChart = null;
let hasLoadedSalesHistoryTab = false;
let hasLoadedSalesReportsTab = false;
let salesPeriodReportCache = null;
let overviewSummaryCache = null;
let overviewPaymentCache = null;
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

function isMenuAdminPanelRole(role) {
  const normalized = String(role || getCounterUserRole()).toLowerCase();
  return normalized === 'admin' || normalized === 'root';
}

function applyMenuPanelRoleVisibility(role) {
  const normalized = String(role || getCounterUserRole()).toLowerCase();
  const isAdminPanel = isMenuAdminPanelRole(normalized);
  document.querySelectorAll('[data-menu-admin-only]').forEach((el) => {
    el.classList.toggle('hidden', !isAdminPanel);
  });
  const menuItemsSection = document.getElementById('menu-items-section');
  if (menuItemsSection) {
    menuItemsSection.classList.toggle('md:col-span-2', !isAdminPanel);
  }
  const cashierHint = document.getElementById('menu-items-cashier-hint');
  if (cashierHint) {
    cashierHint.classList.toggle('hidden', isAdminPanel);
  }
  const menuTitle = document.getElementById('menu-items-section-title');
  if (menuTitle) {
    menuTitle.textContent = isAdminPanel ? 'Menu Items' : 'Stock Availability';
  }
  if (menuItemsCache && menuItemsCache.length) {
    refreshMenuItemsView();
  }
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
    if (section === 'staff') visible = isRoot || isAdmin;
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
    if (widget === 'waiter-breakdown') visible = isRoot || isAdmin;
    el.classList.toggle('hidden', !visible);
  });

  const pmTodayHeading = document.getElementById('pm-today-heading');
  if (pmTodayHeading) {
    pmTodayHeading.textContent = isCashier ? 'My Checkout Sales (Today)' : "Today's Sales";
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

function formatMonthInputValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function setSalesReportDefaultDates() {
  const today = new Date();
  const dayInput = document.getElementById('sales-report-date');
  const monthInput = document.getElementById('sales-report-month');
  if (dayInput && !dayInput.value) dayInput.value = formatDateInputValue(today);
  if (monthInput && !monthInput.value) monthInput.value = formatMonthInputValue(today);
}

function syncSalesReportPeriodInputs() {
  const periodEl = document.getElementById('sales-report-period');
  const dayWrap = document.getElementById('sales-report-day-wrap');
  const monthWrap = document.getElementById('sales-report-month-wrap');
  if (!periodEl || !dayWrap || !monthWrap) return;
  const isMonthly = periodEl.value === 'monthly';
  dayWrap.classList.toggle('hidden', isMonthly);
  monthWrap.classList.toggle('hidden', !isMonthly);
}

function moneyOrZero(value) {
  const n = Number(value);
  return formatMoney(Number.isFinite(n) ? n : 0);
}

function renderSalesReportMetrics() {
  const data = salesPeriodReportCache || {};
  const netEl = document.getElementById('sales-report-net');
  const taxEl = document.getElementById('sales-report-tax');
  const grossEl = document.getElementById('sales-report-gross');
  const ordersEl = document.getElementById('sales-report-orders');
  const cashEl = document.getElementById('sales-report-cash');
  const mobileEl = document.getElementById('sales-report-mobile');
  if (netEl) netEl.textContent = moneyOrZero(data.subtotal_revenue);
  if (taxEl) taxEl.textContent = moneyOrZero(data.total_tax);
  if (grossEl) grossEl.textContent = moneyOrZero(data.grand_total_revenue);
  if (ordersEl) ordersEl.textContent = String(Math.max(0, Math.floor(Number(data.total_orders) || 0)));
  if (cashEl) cashEl.textContent = moneyOrZero(data.total_cash);
  if (mobileEl) mobileEl.textContent = moneyOrZero(data.total_mobile);
}

async function loadSalesPeriodReport() {
  const statusEl = document.getElementById('sales-report-status');
  const periodEl = document.getElementById('sales-report-period');
  const dayInput = document.getElementById('sales-report-date');
  const monthInput = document.getElementById('sales-report-month');
  if (!periodEl) return;
  const period = periodEl.value === 'monthly' ? 'monthly' : 'daily';
  const dateValue = period === 'monthly' ? (monthInput?.value || '') : (dayInput?.value || '');
  if (!dateValue) {
    if (statusEl) statusEl.textContent = 'Choose a date or month first.';
    return;
  }
  if (statusEl) statusEl.textContent = 'Loading…';
  const params = new URLSearchParams({ period, date: dateValue });
  const res = await fetch(`${API_BASE}/api/reports/sales?${params.toString()}`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    salesPeriodReportCache = null;
    renderSalesReportMetrics();
    if (statusEl) {
      statusEl.textContent = typeof body.detail === 'string' ? body.detail : 'Failed to load sales report.';
    }
    return;
  }
  salesPeriodReportCache = body;
  renderSalesReportMetrics();
  if (statusEl) {
    statusEl.textContent = `Showing ${body.period} report for ${body.date}. Net + Tax = Gross.`;
  }
}

function bindSalesReportControls() {
  const periodEl = document.getElementById('sales-report-period');
  const loadBtn = document.getElementById('btn-load-sales-report');
  if (periodEl) {
    periodEl.addEventListener('change', () => {
      syncSalesReportPeriodInputs();
    });
  }
  if (loadBtn) {
    loadBtn.addEventListener('click', () => {
      loadSalesPeriodReport().catch((err) => console.error(err));
    });
  }
  syncSalesReportPeriodInputs();
}

function renderOverviewSummaryMetrics() {
  const netEl = document.getElementById('kpi-net-sales');
  const taxEl = document.getElementById('kpi-total-tax');
  const salesEl = document.getElementById('kpi-total-sales');
  const ordersEl = document.getElementById('kpi-total-orders');
  const avgEl = document.getElementById('kpi-average-order-value');
  if (!salesEl || !ordersEl || !avgEl) return;
  const data = overviewSummaryCache || {};
  const orders = Math.max(0, Math.floor(Number(data.total_orders) || 0));
  const grand = Number(data.grand_total_revenue ?? data.total_sales) || 0;
  const tax = Number(data.total_tax) || 0;
  const net = Number(data.subtotal_revenue ?? (grand - tax)) || 0;
  const avg = orders > 0 ? grand / orders : 0;
  if (netEl) netEl.textContent = moneyOrZero(net);
  if (taxEl) taxEl.textContent = moneyOrZero(tax);
  salesEl.textContent = moneyOrZero(grand);
  ordersEl.textContent = String(orders);
  avgEl.textContent = moneyOrZero(avg);
}

function renderOverviewPaymentMetrics() {
  const todayNetEl = document.getElementById('pm-today-net');
  const todayTaxEl = document.getElementById('pm-today-tax');
  const todayTotalEl = document.getElementById('pm-today-total');
  const todayCashEl = document.getElementById('pm-today-cash');
  const todayMobileEl = document.getElementById('pm-today-mobile');
  const monthNetEl = document.getElementById('pm-month-net');
  const monthTaxEl = document.getElementById('pm-month-tax');
  const monthTotalEl = document.getElementById('pm-month-total');
  const monthCashEl = document.getElementById('pm-month-cash');
  const monthMobileEl = document.getElementById('pm-month-mobile');
  if (!todayTotalEl || !todayCashEl || !todayMobileEl) return;

  const today = (overviewPaymentCache && overviewPaymentCache.today) || {};
  const month = (overviewPaymentCache && overviewPaymentCache.month) || {};
  const todayGrand = Number(today.grand_total_revenue ?? today.total) || 0;
  const todayTax = Number(today.total_tax) || 0;
  const todayNet = Number(today.subtotal_revenue ?? (todayGrand - todayTax)) || 0;
  const monthGrand = Number(month.grand_total_revenue ?? month.total) || 0;
  const monthTax = Number(month.total_tax) || 0;
  const monthNet = Number(month.subtotal_revenue ?? (monthGrand - monthTax)) || 0;

  if (todayNetEl) todayNetEl.textContent = moneyOrZero(todayNet);
  if (todayTaxEl) todayTaxEl.textContent = moneyOrZero(todayTax);
  todayTotalEl.textContent = moneyOrZero(todayGrand);
  todayCashEl.textContent = moneyOrZero(today.cash);
  todayMobileEl.textContent = moneyOrZero(today.mobile_money);
  if (monthNetEl) monthNetEl.textContent = moneyOrZero(monthNet);
  if (monthTaxEl) monthTaxEl.textContent = moneyOrZero(monthTax);
  if (monthTotalEl) monthTotalEl.textContent = moneyOrZero(monthGrand);
  if (monthCashEl) monthCashEl.textContent = moneyOrZero(month.cash);
  if (monthMobileEl) monthMobileEl.textContent = moneyOrZero(month.mobile_money);
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

function formatApiDetail(data, fallback = 'Request failed') {
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((entry) => entry.msg || JSON.stringify(entry)).join('; ');
  }
  if (data.detail != null) return String(data.detail);
  return fallback;
}

async function apiJsonRequest(url, options = {}) {
  const {
    method = 'GET',
    body,
    fallbackMessage = 'Request failed',
    auth = true,
  } = options;
  const headers = {};
  if (body != null) headers['Content-Type'] = 'application/json';
  if (auth && window.auth?.getAuthHeaders) {
    Object.assign(headers, window.auth.getAuthHeaders());
  }
  const res = await fetch(url, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (window.auth?.checkUnauthorized?.(res)) {
    throw new Error('Session expired. Please log in again.');
  }
  if (!res.ok) {
    throw new Error(formatApiDetail(data, fallbackMessage));
  }
  return data;
}

function buildMenuItemPayloadFromForm() {
  const name = document.getElementById('item-name')?.value.trim() || '';
  const price = parseFloat(document.getElementById('item-price')?.value);
  const discountPriceRaw = document.getElementById('item-discount-price')?.value.trim() ?? '';
  const discountPrice = discountPriceRaw === '' ? null : parseFloat(discountPriceRaw);
  const takeawayPriceRaw = document.getElementById('item-takeaway-price')?.value.trim() ?? '';
  const takeawayPrice = takeawayPriceRaw === '' ? null : parseFloat(takeawayPriceRaw);
  const taxType = String(document.getElementById('item-tax-type')?.value || 'none');
  const taxValueRaw = document.getElementById('item-tax-value')?.value.trim() ?? '0';
  const taxValue = taxType === 'none' ? 0 : parseFloat(taxValueRaw || '0');
  const description = document.getElementById('item-description')?.value.trim() || null;
  const categoryId = parseInt(document.getElementById('item-category')?.value, 10);
  const imageUrl = document.getElementById('item-image-url')?.value.trim() || null;
  const isPromoted = !!document.getElementById('item-is-promoted')?.checked;

  if (!name) throw new Error('Item name is required.');
  if (Number.isNaN(price) || price < 0) throw new Error('Enter a valid price (0 or greater).');
  if (!categoryId || Number.isNaN(categoryId)) throw new Error('Select a category.');
  if (discountPrice !== null && (Number.isNaN(discountPrice) || discountPrice < 0)) {
    throw new Error('Discount price must be a valid number (0 or greater).');
  }
  if (takeawayPrice !== null && (Number.isNaN(takeawayPrice) || takeawayPrice < 0)) {
    throw new Error('Takeaway price must be a valid number (0 or greater).');
  }
  if (taxType !== 'none' && (Number.isNaN(taxValue) || taxValue < 0)) {
    throw new Error('Tax value must be a valid number (0 or greater).');
  }

  return {
    name,
    price,
    discount_price: discountPrice,
    discount_type: 'none',
    discount_value: 0,
    takeaway_price: takeawayPrice,
    tax_type: taxType,
    tax_value: taxValue,
    category_id: categoryId,
    description,
    image_url: imageUrl,
    is_available: true,
    is_promoted: isPromoted,
    modifiers_config: [],
  };
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

  overviewSummaryCache = null;
  renderOverviewSummaryMetrics();

  try {
    const res = await fetch(`${API_BASE}/api/reports/summary/today`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Failed to load dashboard summary');

    overviewSummaryCache = data;
    renderOverviewSummaryMetrics();
  } catch (err) {
    console.error(err);
    if (window.toast) window.toast.error('Failed to load dashboard summary');
  }

  await loadPaymentMethodBreakdown();

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

async function loadPaymentMethodBreakdown() {
  const todayTotalEl = document.getElementById('pm-today-total');
  const todayCashEl = document.getElementById('pm-today-cash');
  const todayMobileEl = document.getElementById('pm-today-mobile');
  if (!todayTotalEl || !todayCashEl || !todayMobileEl) return;

  overviewPaymentCache = null;
  renderOverviewPaymentMetrics();

  try {
    const res = await fetch(`${API_BASE}/api/analytics/sales-breakdown`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Failed to load payment breakdown');

    overviewPaymentCache = data;
    renderOverviewPaymentMetrics();
  } catch (err) {
    console.error(err);
  }
}

function setCheckoutPaymentMethod(method) {
  const normalized =
    method === 'mobile_money' ? 'mobile_money' : method === 'split' ? 'split' : 'cash';
  const hidden = document.getElementById('payment-method');
  if (hidden) hidden.value = normalized;
  document.querySelectorAll('.payment-method-btn').forEach((btn) => {
    const isActive = btn.getAttribute('data-payment-method') === normalized;
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    btn.classList.toggle('border-emerald-500', isActive);
    btn.classList.toggle('bg-emerald-50', isActive);
    btn.classList.toggle('text-emerald-900', isActive);
    btn.classList.toggle('border-slate-200', !isActive);
    btn.classList.toggle('bg-white', !isActive);
    btn.classList.toggle('text-slate-700', !isActive);
  });
  const singleBlock = document.getElementById('checkout-single-tender-block');
  const splitBlock = document.getElementById('checkout-split-block');
  const singleChangeRow = document.getElementById('checkout-single-change-row');
  const isSplit = normalized === 'split';
  if (singleBlock) singleBlock.classList.toggle('hidden', isSplit);
  if (splitBlock) splitBlock.classList.toggle('hidden', !isSplit);
  if (singleChangeRow) singleChangeRow.classList.toggle('hidden', isSplit);
  if (isSplit) {
    const total = Number.isFinite(selectedOrderTotal) ? selectedOrderTotal : 0;
    const cashEl = document.getElementById('split-cash-amount');
    const mobileEl = document.getElementById('split-mobile-amount');
    if (mobileEl && !mobileEl.value) mobileEl.value = '0';
    if (cashEl && !cashEl.value) cashEl.value = String(total || '');
  }
  recalculateCheckoutTotals();
  updateCheckoutConfirmEnabled();
}

let splitAutofillLock = false;

function parseMoneyInput(el) {
  const n = parseFloat(el?.value || '0');
  return Number.isFinite(n) && n >= 0 ? roundMoney(n) : 0;
}

function getSplitPaymentAmounts() {
  return {
    cash: parseMoneyInput(document.getElementById('split-cash-amount')),
    mobile: parseMoneyInput(document.getElementById('split-mobile-amount')),
  };
}

function updateCheckoutConfirmEnabled() {
  const btn = document.getElementById('btn-process-payment');
  if (!btn) return;
  const method = document.getElementById('payment-method')?.value || 'cash';
  const total = Number.isFinite(selectedOrderTotal) ? selectedOrderTotal : 0;
  if (selectedOrderId == null) {
    btn.disabled = true;
    return;
  }
  if (method === 'split') {
    const { cash, mobile } = getSplitPaymentAmounts();
    btn.disabled = roundMoney(cash + mobile) < total;
    return;
  }
  const tendered = parseFloat(document.getElementById('amount-tendered')?.value || '0');
  btn.disabled = Number.isNaN(tendered) || tendered < total;
}

function updateSplitChangeDueDisplay(finalTotal) {
  const cash = parseMoneyInput(document.getElementById('split-cash-amount'));
  const mobile = parseMoneyInput(document.getElementById('split-mobile-amount'));
  const dueBox = document.getElementById('split-change-due-box');
  const dueEl = document.getElementById('split-change-due');
  const changeSpan = document.getElementById('change-amount');
  const paid = roundMoney(cash + mobile);
  // Change is excess cash after mobile covers its share (same as backend).
  const remainingAfterMobile = roundMoney(Math.max(finalTotal - mobile, 0));
  const changeDue = roundMoney(cash - remainingAfterMobile);
  const insufficient = paid < finalTotal;

  let label = formatMoney(0);
  if (insufficient) label = t('insufficient', 'Insufficient');
  else label = formatMoney(Math.max(changeDue, 0));

  if (dueEl) dueEl.textContent = label;
  if (changeSpan) changeSpan.textContent = label;
  if (dueBox) {
    const hasChange = !insufficient && changeDue > 0;
    dueBox.classList.toggle('border-emerald-300', hasChange);
    dueBox.classList.toggle('bg-emerald-50', hasChange);
    dueBox.classList.toggle('border-slate-200', !hasChange);
    dueBox.classList.toggle('bg-slate-50', !hasChange);
    if (dueEl) {
      dueEl.classList.toggle('text-emerald-700', hasChange);
      dueEl.classList.toggle('text-slate-800', !hasChange);
    }
  }
}

function initPaymentMethodToggle() {
  document.querySelectorAll('.payment-method-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      setCheckoutPaymentMethod(btn.getAttribute('data-payment-method'));
    });
  });
  const cashEl = document.getElementById('split-cash-amount');
  const mobileEl = document.getElementById('split-mobile-amount');
  // Cash tendered: manual override allowed (overpay → Change Due). Do not rewrite mobile.
  if (cashEl) {
    cashEl.addEventListener('input', () => {
      recalculateCheckoutTotals();
      updateCheckoutConfirmEnabled();
    });
  }
  // Mobile entered → auto-fill Cash with exact remaining balance.
  if (mobileEl) {
    mobileEl.addEventListener('input', () => {
      if (splitAutofillLock) return;
      splitAutofillLock = true;
      const total = Number.isFinite(selectedOrderTotal) ? selectedOrderTotal : 0;
      const mobile = parseFloat(mobileEl.value || '0');
      if (cashEl && Number.isFinite(mobile) && mobile >= 0) {
        cashEl.value = String(roundMoney(Math.max(total - mobile, 0)));
      }
      splitAutofillLock = false;
      recalculateCheckoutTotals();
      updateCheckoutConfirmEnabled();
    });
  }
  setCheckoutPaymentMethod('cash');
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

function computeOrderLineTaxTotal(items) {
  return roundMoney((items || []).reduce((sum, item) => {
    const unitTax = Number(item?.unit_tax_at_sale ?? 0);
    const qty = Number(item?.quantity) || 0;
    return sum + unitTax * qty;
  }, 0));
}

function syncTaxValueFieldState() {
  const taxTypeEl = document.getElementById('item-tax-type');
  const taxValueEl = document.getElementById('item-tax-value');
  if (!taxTypeEl || !taxValueEl) return;
  const isNone = String(taxTypeEl.value || 'none') === 'none';
  taxValueEl.disabled = isNone;
  if (isNone) taxValueEl.value = '0';
}

function recalculateCheckoutTotals() {
  const subtotal = Number.isFinite(selectedOrderSubtotal) ? selectedOrderSubtotal : 0;
  const { type, value } = getCheckoutDiscountState();
  const discountAmount = roundMoney(calculateOrderDiscountAmount(subtotal, type, value));
  const taxAmount = computeOrderLineTaxTotal(selectedOrderVisibleItems);
  const finalTotal = roundMoney(Math.max(subtotal - discountAmount, 0));

  const subtotalEl = document.getElementById('receipt-subtotal');
  const discountEl = document.getElementById('receipt-discount-amount');
  const taxEl = document.getElementById('receipt-tax-amount');
  const grandTotalEl = document.getElementById('receipt-grand-total');
  if (subtotalEl) subtotalEl.textContent = formatMoney(subtotal);
  if (discountEl) discountEl.textContent = formatMoneyNegative(discountAmount);
  if (taxEl) taxEl.textContent = formatMoney(taxAmount);
  if (grandTotalEl) grandTotalEl.textContent = `${t('grand_total', 'Grand Total')}: ${formatMoney(finalTotal)}`;

  selectedOrderTotal = finalTotal;

  const method = document.getElementById('payment-method')?.value || 'cash';
  const changeSpan = document.getElementById('change-amount');
  if (method === 'split') {
    updateSplitChangeDueDisplay(finalTotal);
    updateCheckoutConfirmEnabled();
    return finalTotal;
  }

  const amountInput = document.getElementById('amount-tendered');
  const tendered = parseFloat(amountInput?.value || '0');
  const change = tendered - finalTotal;
  if (!changeSpan) {
    updateCheckoutConfirmEnabled();
    return finalTotal;
  }
  if (Number.isNaN(change)) changeSpan.textContent = formatMoney(0);
  else if (change >= 0) changeSpan.textContent = formatMoney(change);
  else changeSpan.textContent = t('insufficient', 'Insufficient');
  updateCheckoutConfirmEnabled();
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
  if (window.tableDisplay?.displayTableName) {
    return window.tableDisplay.displayTableName(table);
  }
  const raw = table?.name || table?.name_or_number || `#${table?.id ?? ''}`;
  return String(raw).replace(/^table\s+/i, '').trim() || raw;
}

function renderCashierZoneTabs() {
  const tabs = document.getElementById('cashier-zone-tabs');
  if (!tabs) return;
  if (!cashierZones.length) {
    tabs.innerHTML = '<span class="text-slate-500 text-sm">No zones</span>';
    return;
  }
  const allTab = `
      <button
        type="button"
        data-cashier-zone-id=""
        class="cashier-zone-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${
          cashierActiveZoneId == null
            ? 'bg-blue-600 text-white'
            : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
        }"
      >
        ${escapeHtml(t('all', 'All'))}
      </button>`;
  tabs.innerHTML = allTab + cashierZones
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
      const zoneAttr = btn.getAttribute('data-cashier-zone-id');
      cashierActiveZoneId = zoneAttr === '' || zoneAttr == null ? null : parseInt(zoneAttr, 10);
      renderCashierZoneTabs();
      renderCashierTablesGrid();
    });
  });
}

function getCashierActiveZoneTables() {
  if (cashierActiveZoneId == null) {
    return cashierZones.flatMap((z) => z.tables || []);
  }
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
      const statusLabel = window.tableDisplay?.displayTableStatus
        ? window.tableDisplay.displayTableStatus(table.status)
        : table.status;
      const statusTypography = window.tableDisplay?.tableStatusTypographyClass
        || 'text-[10px] font-normal leading-tight normal-case text-slate-600';
      return `
        <button
          type="button"
          data-cashier-table-id="${table.id}"
          data-cashier-table-name="${escapeHtml(cashierTableName(table))}"
          data-cashier-table-status="${escapeHtml(table.status)}"
          class="cashier-table-card border-2 rounded-md p-2 text-left ${color} hover:shadow ${
            cashierCheckoutSource?.type === 'table' && Number(cashierCheckoutSource.id) === Number(table.id)
              ? 'ring-2 ring-blue-600 ring-offset-1'
              : ''
          }"
        >
          <div class="font-medium text-slate-800 text-sm">${escapeHtml(cashierTableName(table))}</div>
          <div class="${statusTypography}">${escapeHtml(statusLabel)}</div>
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
        selectOrder(order, { type: 'table', id: tableId, name: tableName });
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
        class="w-full text-left border border-orange-200 rounded-md p-2 bg-orange-50 hover:bg-orange-100 ${
          cashierCheckoutSource?.type === 'takeaway' && Number(cashierCheckoutSource.id) === Number(o.id)
            ? 'ring-2 ring-orange-500 ring-offset-1'
            : ''
        }"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-medium text-orange-800">${escapeHtml(cashierOrderDisplayLabel(o))}</span>
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
      if (order) selectOrder(order, { type: 'takeaway', id: orderId });
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
        if (cashierActiveZoneId != null && !cashierZones.some((z) => z.id === cashierActiveZoneId)) {
          cashierActiveZoneId = null;
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

function clearCheckoutSelection() {
  selectedOrderId = null;
  selectedTableNumber = null;
  selectedOrderTotal = 0;
  selectedOrderSubtotal = 0;
  selectedOrderVisibleItems = [];
  cashierCheckoutSource = null;
  document.getElementById('receipt-container')?.classList.add('hidden');
  document.getElementById('receipt-placeholder')?.classList.remove('hidden');
  if (cashierZones.length) renderCashierTablesGrid();
  document.querySelectorAll('#cashier-takeaway-orders [data-takeaway-order-id]').forEach((btn) => {
    btn.classList.remove('ring-2', 'ring-orange-500', 'ring-offset-1');
  });
}

function handleRemoteOrderClosed(data) {
  if (!data) return;
  const status = String(data.status || '').toLowerCase();
  const orderId = data.order_id != null ? data.order_id : data.id;
  loadUnpaidOrders();
  if (
    orderId != null &&
    selectedOrderId != null &&
    Number(orderId) === Number(selectedOrderId) &&
    (status === 'cancelled' || status === 'paid')
  ) {
    clearCheckoutSelection();
  }
}

function selectOrder(order, source = null) {
  if (!order) return;
  selectedOrderId = order.id;
  selectedTableNumber = order.table_number;
  if (source?.type && source?.id != null) {
    cashierCheckoutSource = {
      type: source.type,
      id: Number(source.id),
      name: source.name != null ? String(source.name) : undefined,
    };
  } else if (String(order.order_type || '').toLowerCase() === 'takeaway') {
    cashierCheckoutSource = { type: 'takeaway', id: Number(order.id) };
  } else if (order.table_id != null) {
    cashierCheckoutSource = { type: 'table', id: Number(order.table_id) };
  } else {
    cashierCheckoutSource = null;
  }
  const visibleItems = (order.items || []).filter((i) => String(i?.item_status || '').toLowerCase() !== 'cancelled');
  selectedOrderVisibleItems = visibleItems;
  selectedOrderSubtotal = visibleItems.reduce((sum, i) => sum + (Number(i.subtotal) || 0), 0);
  selectedOrderTotal = selectedOrderSubtotal;
  document.getElementById('receipt-placeholder')?.classList.add('hidden');
  const container = document.getElementById('receipt-container');
  if (container) container.classList.remove('hidden');
  const checkoutHeaderEl = document.getElementById('checkout-header');
  if (checkoutHeaderEl) {
    checkoutHeaderEl.textContent = `${t('checkout', 'Checkout')} - ${cashierOrderDisplayLabel(order, cashierCheckoutSource)}`;
  }
  const itemsRows = visibleItems
    .map(
      (i) =>
        `<tr><td class="py-1">${escapeHtml(i.menu_item_name)}</td><td class="py-1 text-right">${i.quantity}</td><td class="py-1 text-right">${formatMoney(Number(i.subtotal))}</td></tr>`
    )
    .join('');
  const receiptContent = document.getElementById('receipt-content');
  if (receiptContent) {
    receiptContent.innerHTML = `
    <table class="w-full text-sm text-slate-700">
      <thead><tr class="border-b border-slate-200"><th class="text-left py-1">${escapeHtml(t('item', 'Item'))}</th><th class="text-right py-1">${escapeHtml(t('qty', 'Qty'))}</th><th class="text-right py-1">${escapeHtml(t('subtotal', 'Subtotal'))}</th></tr></thead>
      <tbody>${itemsRows}</tbody>
    </table>
  `;
  }
  const servedByEl = document.getElementById('receipt-served-by');
  if (servedByEl) servedByEl.textContent = orderServedByLabel(order);
  const amountInput = document.getElementById('amount-tendered');
  const changeSpan = document.getElementById('change-amount');
  const discountTypeSelect = document.getElementById('checkout-discount-type');
  const discountValueInput = document.getElementById('checkout-discount-value');
  if (amountInput) amountInput.value = '';
  if (changeSpan) changeSpan.textContent = formatMoney(0);
  const splitCash = document.getElementById('split-cash-amount');
  const splitMobile = document.getElementById('split-mobile-amount');
  if (splitCash) splitCash.value = '';
  if (splitMobile) splitMobile.value = '';
  if (discountTypeSelect) discountTypeSelect.value = 'none';
  if (discountValueInput) {
    discountValueInput.value = '';
    discountValueInput.disabled = true;
  }
  setCheckoutPaymentMethod('cash');
  recalculateCheckoutTotals();
  if (cashierZones.length) renderCashierTablesGrid();
  document.querySelectorAll('#cashier-takeaway-orders [data-takeaway-order-id]').forEach((btn) => {
    const id = Number(btn.getAttribute('data-takeaway-order-id'));
    const active = cashierCheckoutSource?.type === 'takeaway' && Number(cashierCheckoutSource.id) === id;
    btn.classList.toggle('ring-2', active);
    btn.classList.toggle('ring-orange-500', active);
    btn.classList.toggle('ring-offset-1', active);
  });
  document.getElementById('pane-checkout')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Dynamic change calculation and payment processing
const amountInputEl = document.getElementById('amount-tendered');
const changeSpanEl = document.getElementById('change-amount');
const discountTypeEl = document.getElementById('checkout-discount-type');
const discountValueEl = document.getElementById('checkout-discount-value');

initPaymentMethodToggle();

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
  const paymentMethodInput = document.getElementById('payment-method');
  const issueReceiptEl = document.getElementById('checkout-issue-receipt');
  const tendered = parseFloat((amountInput && amountInput.value) || '0');
  const { type: discountType, value: discountValue } = getCheckoutDiscountState();
  const currentFinalTotal = recalculateCheckoutTotals();
  const method = paymentMethodInput ? paymentMethodInput.value || 'cash' : 'cash';
  const issueReceipt = issueReceiptEl ? !!issueReceiptEl.checked : true;
  const payload = {
    discount_type: discountType === 'none' ? null : discountType,
    discount_value: discountType === 'none' ? 0 : discountValue,
    issue_receipt: issueReceipt,
  };

  if (method === 'split') {
    const cash = parseMoneyInput(document.getElementById('split-cash-amount'));
    const mobile = parseMoneyInput(document.getElementById('split-mobile-amount'));
    if (roundMoney(cash + mobile) < currentFinalTotal) {
      await dialogAlert(t('amount_less_than_total', 'Amount tendered is less than total.'), 'error', t('error', 'Error'));
      return;
    }
    payload.payment_method = 'split';
    payload.cash_amount = cash;
    payload.mobile_money_amount = mobile;
    payload.amount_tendered = cash;
  } else {
    if (Number.isNaN(tendered) || tendered <= 0) {
      await dialogAlert(t('enter_valid_amount_tendered', 'Enter a valid amount tendered.'), 'error', t('error', 'Error'));
      return;
    }
    if (tendered < currentFinalTotal) {
      await dialogAlert(t('amount_less_than_total', 'Amount tendered is less than total.'), 'error', t('error', 'Error'));
      return;
    }
    payload.payment_method = method;
    payload.amount_tendered = tendered;
  }

  if (issueReceipt) {
    const printerId = getSelectedCashierPrinterId();
    if (printerId != null) payload.printer_id = printerId;
  }
  const cashierName = getCurrentCashierName();
  if (cashierName) payload.cashier_name = cashierName;

  btn.disabled = true;
  btn.textContent = t('processing', 'Processing...');
  try {
    const res = await fetch(`${API_BASE}/api/orders/${selectedOrderId}/checkout`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify(payload),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      await dialogAlert(data.detail || t('payment_failed', 'Payment failed'), 'error', t('error', 'Error'));
      return;
    }
    await dialogAlert(t('payment_success', 'Payment processed successfully.'), 'success', t('success', 'Success'));
    if (data.warning && window.toast) {
      window.toast.error(
        t(
          'receipt_printer_offline',
          'Checkout successful, but receipt printer is offline!'
        )
      );
    }

    clearCheckoutSelection();
    // Reload grid from backend after payment.
    loadUnpaidOrders();
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

async function fetchUsers() {
  return apiJsonRequest(`${API_BASE}/api/admin/users`, {
    fallbackMessage: 'Failed to fetch users',
  }).then((data) => {
    if (!Array.isArray(data)) {
      throw new Error('Invalid users response from server');
    }
    return data;
  });
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
  const list = Array.isArray(users) ? users : [];
  usersState = list;
  const tbody = document.getElementById('users-table-body');
  if (!tbody) return;
  const staffRoles = new Set(['cashier', 'waiter', 'account']);
  const visibleUsers = list.filter((u) =>
    staffRoles.has(String(u?.role || '').toLowerCase())
  );
  if (!visibleUsers.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="py-3 text-slate-500">No users</td></tr>';
    return;
  }
  tbody.innerHTML = visibleUsers
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
async function fetchRootAdmins() {
  const data = await apiJsonRequest(`${API_BASE}/api/root/admins`, {
    fallbackMessage: 'Failed to fetch admin accounts',
  });
  return Array.isArray(data) ? data : [];
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
  const titleEl = document.getElementById('admin-form-title');
  const usernameEl = document.getElementById('admin-username');
  const passwordEl = document.getElementById('admin-password');
  const deleteBtn = document.getElementById('btn-delete-admin');
  const resetPwBtn = document.getElementById('btn-reset-admin-password');
  if (idEl) idEl.value = '';
  if (titleEl) titleEl.textContent = 'Create Admin';
  if (usernameEl) usernameEl.value = '';
  if (passwordEl) passwordEl.value = '';
  if (deleteBtn) deleteBtn.classList.add('hidden');
  if (resetPwBtn) resetPwBtn.classList.add('hidden');
  syncAdminFormMode(false);
}

async function loadRootAdmins() {
  try {
    const admins = await fetchRootAdmins();
    renderRootAdmins(admins);
  } catch (e) {
    console.error(e);
    const tbody = document.getElementById('admins-table-body');
    const message = e?.message || 'Error loading admins.';
    if (tbody) tbody.innerHTML = `<tr><td colspan="2" class="py-3 text-red-600">${escapeHtml(message)}</td></tr>`;
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
  const pinEl = document.getElementById('user-pin');
  if (!roleEl) return;
  const PIN_ROLES = ['account', 'cashier', 'waiter'];
  const isPinRole = PIN_ROLES.includes(roleEl.value);
  if (pinWrap) pinWrap.classList.toggle('hidden', !isPinRole);
  if (pinEl) pinEl.required = isPinRole;
}

async function loadUsers() {
  try {
    const users = await fetchUsers();
    renderUsers(users);
  } catch (e) {
    console.error(e);
    const tbody = document.getElementById('users-table-body');
    const message = e?.message || 'Error loading users.';
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="4" class="py-3 text-red-600">${escapeHtml(message)}</td></tr>`;
    }
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
      await apiJsonRequest(url, {
        method,
        body: payload,
        fallbackMessage: 'Failed to save user',
      });
      if (window.toast) window.toast.success('User saved successfully.');
      resetUserForm();
      await loadUsers();
    } catch (err) {
      console.error(err);
      await dialogAlert(formatUserSaveError(err.message) || 'Failed to save user', 'error', 'Save User');
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
      await apiJsonRequest(url, {
        method,
        body: payload,
        fallbackMessage: 'Failed to save admin',
      });
      if (window.toast) window.toast.success('Admin saved successfully.');
      resetAdminForm();
      await loadRootAdmins();
    } catch (err) {
      console.error(err);
      await dialogAlert(err.message || 'Failed to save admin', 'error', 'Save Admin');
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
async function fetchTableGrid() {
  const res = await fetch(`${API_BASE}/api/tables/grid?_ts=${Date.now()}`, {
    cache: 'no-store',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth?.checkUnauthorized?.(res)) {
    throw new Error('Session expired. Please log in again.');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatApiDetail(data, 'Failed to fetch table grid'));
  }
  if (!Array.isArray(data)) {
    throw new Error('Invalid table grid response');
  }
  return data;
}

async function createZoneByName(zoneName) {
  return apiJsonRequest(`${API_BASE}/api/zones`, {
    method: 'POST',
    body: { name: zoneName },
    fallbackMessage: 'Failed to create zone',
  });
}

async function createTableInZone(zoneId, tableName) {
  const parsedZoneId = Number(zoneId);
  if (!Number.isInteger(parsedZoneId) || parsedZoneId <= 0) {
    throw new Error('Invalid zone. Please reload and try again.');
  }
  const name = String(tableName || '').trim();
  if (!name) {
    throw new Error('Please enter a table name.');
  }
  return apiJsonRequest(`${API_BASE}/api/tables`, {
    method: 'POST',
    body: { name, zone_id: parsedZoneId, status: 'available' },
    fallbackMessage: 'Failed to create table',
  });
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
  if (window.tableDisplay?.displayTableName) {
    return window.tableDisplay.displayTableName(t);
  }
  const raw = t?.name || t?.name_or_number || `#${t?.id}`;
  return String(raw).replace(/^table\s+/i, '').trim() || raw;
}

function tableRawName(t) {
  return t?.name || t?.name_or_number || '';
}

function formatTakeawayOrderLabel(orderId) {
  return `🛍️ ${t('takeaway', 'Takeaway')} #${orderId}`;
}

function isTakeawayOrder(order) {
  if (!order) return false;
  if (String(order.order_type || '').toLowerCase() === 'takeaway') return true;
  return order.table_id == null && order.table_number == null;
}

/**
 * Resolve dine-in display name. Never treat legacy integer `order.table_number`
 * as the label when the real name is non-numeric (e.g. "F1") — backend stores
 * table.id in table_number when name_or_number is not an int.
 */
function findCashierTableById(tableId) {
  const id = Number(tableId);
  if (!Number.isFinite(id)) return null;
  for (const zone of cashierZones || []) {
    const match = (zone.tables || []).find((t) => Number(t.id) === id);
    if (match) return match;
  }
  return null;
}

function resolveCashierDineInTableLabel(order, source = null) {
  if (source?.type === 'table' && source.name) {
    return cashierTableName({ name: source.name, id: source.id });
  }
  if (order?.table && (order.table.name || order.table.name_or_number)) {
    return cashierTableName(order.table);
  }
  const tableId = order?.table_id != null ? Number(order.table_id) : null;
  const fromGrid = tableId != null ? findCashierTableById(tableId) : null;
  if (fromGrid) return cashierTableName(fromGrid);

  // Numeric-only legacy names may equal table_number; prefer that string only if
  // it matches a known grid name, otherwise show #table_id.
  if (tableId != null) return `#${tableId}`;
  if (order?.table_number != null && String(order.table_number).trim() !== '') {
    return String(order.table_number);
  }
  return t('table', 'Table');
}

function cashierOrderDisplayLabel(order, source = null) {
  if (isTakeawayOrder(order)) {
    const customer = String(order?.customer_name || '').trim();
    if (customer) return `🛍️ ${customer}`;
    if (order?.id != null) return formatTakeawayOrderLabel(order.id);
    return `🛍️ ${t('takeaway', 'Takeaway')}`;
  }
  return resolveCashierDineInTableLabel(order, source);
}

function orderServedByLabel(order) {
  return order?.waiter_name || order?.served_by_name || t('unknown', 'Unknown');
}

function orderTableLabel(order) {
  return cashierOrderDisplayLabel(order, cashierCheckoutSource);
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
                    value="${escapeAttr(tableRawName(table))}"
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
    const submitBtn = kanbanZoneForm.querySelector('button[type="submit"]');
    const zoneName = (zoneNameInput && zoneNameInput.value || '').trim();
    if (!zoneName) {
      if (window.toast) window.toast.error('Enter a zone name.');
      return;
    }
    if (submitBtn) submitBtn.disabled = true;
    try {
      const created = await createZoneByName(zoneName);
      if (created && created.id != null) {
        const exists = (zonesState || []).some((z) => Number(z.id) === Number(created.id));
        if (!exists) {
          zonesState = [...(zonesState || []), { id: created.id, name: created.name, tables: [] }];
          renderTableKanbanBoard(zonesState);
        }
      }
      if (window.toast) window.toast.success('Zone created.');
      if (zoneNameInput) zoneNameInput.value = '';
      try {
        await loadTableManagementData();
      } catch (refreshErr) {
        console.error(refreshErr);
        if (window.toast) window.toast.error('Zone saved, but refresh failed. Please reload.');
      }
    } catch (err) {
      console.error(err);
      await dialogAlert(err.message || 'Failed to create zone', 'error', 'Create Zone');
    } finally {
      if (submitBtn) submitBtn.disabled = false;
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
      try {
        await createTableInZone(zoneId, tableName);
        if (window.toast) window.toast.success('Table created.');
        addTableZoneId = null;
        await loadTableManagementData();
      } catch (err) {
        console.error(err);
        await dialogAlert(err.message || 'Failed to create table', 'error', 'Create Table');
      }
      return;
    }
  });

  kanbanBoard.addEventListener('keydown', async (e) => {
    const input = e.target;
    if (!input || !input.matches || !input.matches('[data-add-table-input-id]')) return;
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const zoneId = Number(input.getAttribute('data-add-table-input-id'));
    const tableName = (input.value || '').trim();
    try {
      await createTableInZone(zoneId, tableName);
      if (window.toast) window.toast.success('Table created.');
      addTableZoneId = null;
      await loadTableManagementData();
    } catch (err) {
      console.error(err);
      await dialogAlert(err.message || 'Failed to create table', 'error', 'Create Table');
    }
  });
}

async function parseApiDetail(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((entry) => entry.msg || JSON.stringify(entry)).join('; ');
    }
    if (data.detail != null) return String(data.detail);
    return 'Request failed';
  } catch {
    return res.statusText || 'Request failed';
  }
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

async function setMenuItemAvailability(itemId, isAvailable) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}/availability`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
    body: JSON.stringify({ is_available: Boolean(isAvailable) }),
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

async function toggleMenuItemAvailability(itemId) {
  const item = (menuItemsCache || []).find((m) => Number(m.id) === Number(itemId));
  const nextAvailable = item ? item.is_available === false : true;
  return setMenuItemAvailability(itemId, nextAvailable);
}

async function deleteMenuItem(itemId) {
  const res = await fetch(`${API_BASE}/api/menu-items/${itemId}`, {
    method: 'DELETE',
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return null;
  if (!res.ok) {
    const detail = await parseApiDetail(res);
    throw new Error(detail);
  }
  const data = await res.json().catch(() => ({}));
  if (window.toast) window.toast.success('Menu item deleted.');
  return data;
}

async function updateMenuItem(itemId, payload) {
  return apiJsonRequest(`${API_BASE}/api/menu-items/${itemId}`, {
    method: 'PUT',
    body: payload,
    fallbackMessage: 'Failed to update menu item',
  }).then((data) => {
    if (window.toast) window.toast.success('Menu item updated.');
    return data;
  });
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
  const nameInput = document.getElementById('item-name');
  const priceInput = document.getElementById('item-price');
  const descriptionInput = document.getElementById('item-description');
  const categoryInput = document.getElementById('item-category');
  const imageUrlInput = document.getElementById('item-image-url');
  const imageFileInput = document.getElementById('item-image-file');
  const discountInput = document.getElementById('item-discount-price');
  const takeawayInput = document.getElementById('item-takeaway-price');
  const taxTypeInput = document.getElementById('item-tax-type');
  const taxValueInput = document.getElementById('item-tax-value');
  const promotedInput = document.getElementById('item-is-promoted');
  if (nameInput) nameInput.value = '';
  if (priceInput) priceInput.value = '';
  if (descriptionInput) descriptionInput.value = '';
  if (categoryInput) categoryInput.value = '';
  if (imageUrlInput) imageUrlInput.value = '';
  if (imageFileInput) imageFileInput.value = '';
  if (discountInput) discountInput.value = '';
  if (takeawayInput) takeawayInput.value = '';
  if (taxTypeInput) taxTypeInput.value = 'none';
  if (taxValueInput) taxValueInput.value = '0';
  if (promotedInput) promotedInput.checked = false;
  syncTaxValueFieldState();
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
  const takeawayInput = document.getElementById('item-takeaway-price');
  if (takeawayInput) takeawayInput.value = item.takeaway_price != null ? Number(item.takeaway_price) : '';
  const taxTypeInput = document.getElementById('item-tax-type');
  const taxValueInput = document.getElementById('item-tax-value');
  if (taxTypeInput) taxTypeInput.value = String(item.tax_type || 'none');
  if (taxValueInput) taxValueInput.value = Number(item.tax_value || 0);
  syncTaxValueFieldState();
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

function openCategoryEditModal(categoryId, currentName) {
  const modal = document.getElementById('category-edit-modal');
  const idEl = document.getElementById('category-edit-id');
  const nameEl = document.getElementById('category-edit-name');
  if (!modal || !idEl || !nameEl) return;
  idEl.value = String(categoryId);
  nameEl.value = currentName || '';
  modal.classList.remove('hidden');
  nameEl.focus();
  nameEl.select();
}

function closeCategoryEditModal() {
  const modal = document.getElementById('category-edit-modal');
  if (modal) modal.classList.add('hidden');
}

function bindCategoryEditModal() {
  const form = document.getElementById('category-edit-form');
  const cancelBtn = document.getElementById('category-edit-cancel');
  const modal = document.getElementById('category-edit-modal');
  if (!form || form.dataset.bound === '1') return;
  form.dataset.bound = '1';

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => closeCategoryEditModal());
  }
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeCategoryEditModal();
    });
  }
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const categoryId = Number(document.getElementById('category-edit-id')?.value);
    const nameEl = document.getElementById('category-edit-name');
    const trimmed = String(nameEl?.value || '').trim();
    if (!categoryId || !trimmed) {
      await dialogAlert('Category name cannot be empty.', 'error', 'Edit Category');
      return;
    }
    const saveBtn = document.getElementById('category-edit-save');
    if (saveBtn) saveBtn.disabled = true;
    try {
      const res = await fetch(`${API_BASE}/api/categories/${encodeURIComponent(categoryId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ name: trimmed }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      const err = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof err.detail === 'string' ? err.detail : 'Failed to update category';
        await dialogAlert(detail, 'error', 'Edit Category');
        return;
      }
      closeCategoryEditModal();
      await loadMenuData();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to update category', 'error', 'Edit Category');
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  });
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
          <div class="flex flex-wrap items-center gap-2">
            <button type="button" data-edit-category-id="${c.id}" data-category-name="${escapeAttr(c.name)}" class="text-xs px-2 py-1.5 border border-slate-300 text-slate-700 rounded-md hover:bg-slate-50 font-medium" title="Edit category name">Edit</button>
            <button type="button" data-delete-category-id="${c.id}" data-category-name="${escapeAttr(c.name)}" class="text-xs px-2 py-1.5 border border-red-200 text-red-700 rounded-md hover:bg-red-50 font-medium" title="Delete category">Delete</button>
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

  el.querySelectorAll('[data-edit-category-id]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const categoryId = Number(btn.getAttribute('data-edit-category-id'));
      const currentName = btn.getAttribute('data-category-name') || '';
      if (!categoryId) return;
      openCategoryEditModal(categoryId, currentName);
    });
  });

  el.querySelectorAll('[data-delete-category-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const categoryId = Number(btn.getAttribute('data-delete-category-id'));
      const categoryName = btn.getAttribute('data-category-name') || 'this category';
      if (!categoryId) return;
      const ok = await dialogConfirm(
        `Are you sure you want to delete "${categoryName}"?`,
        'Delete Category'
      );
      if (!ok) return;
      btn.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/api/categories/${encodeURIComponent(categoryId)}`, {
          method: 'DELETE',
          headers: { ...window.auth.getAuthHeaders() },
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        if (!res.ok) {
          const detail = await parseApiDetail(res);
          window.alert(detail);
          await dialogAlert(detail, 'error', 'Delete Category');
          return;
        }
        await res.json().catch(() => ({}));
        const categories = await fetchCategories();
        renderCategories(categories);
        populateCategorySelect(categories);
        try {
          const menuItems = await fetchMenuItems();
          menuItemsCache = menuItems || [];
          refreshMenuItemsView();
        } catch (menuErr) {
          console.error('Menu items refresh failed after category delete:', menuErr);
        }
      } catch (err) {
        console.error(err);
        await dialogAlert('Failed to delete category', 'error', 'Delete Category');
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function getCategoriesWithMenuItems() {
  const ids = new Set(menuItemsCache.map((m) => m.category_id));
  return categoriesCache.filter((c) => ids.has(c.id));
}

function renderMenuCategoryTabs() {
  const container = document.getElementById('menu-category-tabs');
  if (!container) return;
  if (
    activeMenuCategoryId != null
    && !categoriesCache.some((c) => c.id === activeMenuCategoryId)
  ) {
    activeMenuCategoryId = null;
  }
  const withItems = getCategoriesWithMenuItems();
  container.innerHTML = [
    `<button type="button" data-menu-category-key="ALL" class="menu-category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeMenuCategoryId === null ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">ALL</button>`,
    ...withItems.map(
      (c) =>
        `<button type="button" data-menu-category-key="${c.id}" class="menu-category-tab px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap ${activeMenuCategoryId === c.id ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}">${escapeHtml(c.name)}</button>`
    ),
  ].join('');
  container.querySelectorAll('.menu-category-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      filterMenu(btn.getAttribute('data-menu-category-key'));
    });
  });
}

function filterMenu(categoryKey) {
  if (categoryKey === 'ALL' || categoryKey === '' || categoryKey == null) {
    activeMenuCategoryId = null;
  } else {
    activeMenuCategoryId = Number(categoryKey);
  }
  renderMenuCategoryTabs();
  applyMenuCategoryFilter();
}

function applyMenuCategoryFilter() {
  const list = document.getElementById('menu-items-list');
  if (!list) return;
  list.querySelectorAll('[data-menu-category-id]').forEach((row) => {
    const rowCategoryId = Number(row.getAttribute('data-menu-category-id'));
    const show = activeMenuCategoryId == null || rowCategoryId === activeMenuCategoryId;
    row.classList.toggle('hidden', !show);
  });
  const visibleRows = list.querySelectorAll('[data-menu-category-id]:not(.hidden)');
  let emptyMsg = list.querySelector('[data-menu-filter-empty]');
  if (activeMenuCategoryId != null && visibleRows.length === 0) {
    if (!emptyMsg) {
      emptyMsg = document.createElement('li');
      emptyMsg.setAttribute('data-menu-filter-empty', '1');
      emptyMsg.className = 'text-slate-500 py-2';
      emptyMsg.textContent = 'No items in this category.';
      list.appendChild(emptyMsg);
    }
    emptyMsg.classList.remove('hidden');
  } else if (emptyMsg) {
    emptyMsg.classList.add('hidden');
  }
}

function refreshMenuItemsView() {
  renderMenuCategoryTabs();
  renderMenuItems(menuItemsCache);
  applyMenuCategoryFilter();
}

function renderMenuItems(items) {
  const el = document.getElementById('menu-items-list');
  const isAdminPanel = isMenuAdminPanelRole(getCounterUserRole());
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
      const adminActions = `
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
            </button>`;
      const cashierToggle = `
            <label class="inline-flex items-center gap-2 cursor-pointer select-none">
              <span class="text-xs text-slate-600">${available ? 'In Stock' : 'Sold Out'}</span>
              <input
                type="checkbox"
                role="switch"
                data-availability-switch-id="${m.id}"
                class="h-5 w-9 rounded-full appearance-none bg-slate-300 checked:bg-emerald-500 relative transition-colors cursor-pointer
                  before:content-[''] before:absolute before:top-0.5 before:left-0.5 before:h-4 before:w-4 before:rounded-full before:bg-white before:transition-transform
                  checked:before:translate-x-4"
                ${available ? 'checked' : ''}
                aria-label="${available ? 'Mark sold out' : 'Mark in stock'}"
              />
            </label>`;
      return `
        <li class="py-2 flex items-center justify-between gap-3" data-menu-category-id="${m.category_id}">
          <div class="flex items-center gap-2 min-w-0">
            ${img}
            ${priceLabel}
            ${badge}
            ${isAdminPanel ? promotedBadge : ''}
          </div>
          <div class="flex items-center gap-2 flex-wrap justify-end">
            ${isAdminPanel ? adminActions : cashierToggle}
          </div>
        </li>
      `;
    })
    .join('');

  if (isAdminPanel) {
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
      const confirmed = await dialogConfirm(
        'Remove this menu item from ordering? Past orders and reports are kept.',
        'Delete Menu Item'
      );
      if (!confirmed) return;
      btn.disabled = true;
      try {
        await deleteMenuItem(itemId);
        await loadMenuData();
      } catch (err) {
        console.error(err);
        const message = err.message || 'Failed to delete menu item';
        window.alert(message);
        await dialogAlert(message, 'error', 'Delete Menu Item');
        btn.disabled = false;
      }
    });
  });
  } else {
    el.querySelectorAll('[data-availability-switch-id]').forEach((input) => {
      input.addEventListener('change', async () => {
        const itemId = Number(input.getAttribute('data-availability-switch-id'));
        if (!itemId) return;
        const nextAvailable = input.checked;
        input.disabled = true;
        try {
          await setMenuItemAvailability(itemId, nextAvailable);
          await loadMenuData();
        } catch (err) {
          console.error(err);
          input.checked = !nextAvailable;
          await dialogAlert(err.message || 'Failed to update availability', 'error', 'Stock Availability');
          input.disabled = false;
        }
      });
    });
  }
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

const predefinedInstructionForm = document.getElementById('form-predefined-instruction');
if (predefinedInstructionForm) {
  predefinedInstructionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('predefined-instruction-input');
    const text = String(input?.value || '').trim();
    if (!text) return;
    try {
      const res = await fetch(`${API_BASE}/api/predefined-instructions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ text }),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await dialogAlert(err.detail || 'Failed to add tag', 'error', 'Quick Tags');
        return;
      }
      if (input) input.value = '';
      await loadPredefinedInstructionsAdmin();
      await dialogAlert('Tag added.', 'success', 'Quick Tags');
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to add tag', 'error', 'Quick Tags');
    }
  });
}

const kitchenPrinterForm = document.getElementById('form-kitchen-printers');
if (kitchenPrinterForm) {
  kitchenPrinterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const backend = String(document.getElementById('printer-backend')?.value || 'file').trim();
    const renderMode = String(document.getElementById('printer-render-mode')?.value || 'text').trim();
    const paperWidth = Number(document.getElementById('printer-paper-width')?.value || 576);
    const payload = {
      backend,
      render_mode: renderMode,
      paper_width_px: paperWidth,
      routes: [],
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
      await dialogAlert('Print mode saved.', 'success', 'Printer Settings');
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
  } catch (err) {
    console.error(err);
  }
}

function openPrinterModal(printer = null) {
  const modal = document.getElementById('printer-modal');
  if (!modal) return;
  const title = document.getElementById('printer-modal-title');
  const idEl = document.getElementById('printer-edit-id');
  const nameEl = document.getElementById('printer-form-name');
  const hostEl = document.getElementById('printer-form-host');
  const portEl = document.getElementById('printer-form-port');
  const roleEl = document.getElementById('printer-form-role');
  const activeEl = document.getElementById('printer-form-active');
  if (printer) {
    if (title) title.textContent = 'Edit Printer';
    if (idEl) idEl.value = String(printer.id);
    if (nameEl) nameEl.value = printer.name || '';
    if (hostEl) hostEl.value = printer.host || '';
    if (portEl) portEl.value = printer.port || 9100;
    if (roleEl) roleEl.value = printer.role || 'kitchen';
    if (activeEl) activeEl.checked = printer.is_active !== false;
  } else {
    if (title) title.textContent = 'Add Printer';
    if (idEl) idEl.value = '';
    if (nameEl) nameEl.value = '';
    if (hostEl) hostEl.value = '';
    if (portEl) portEl.value = 9100;
    if (roleEl) roleEl.value = 'cashier';
    if (activeEl) activeEl.checked = true;
  }
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

function closePrinterModal() {
  const modal = document.getElementById('printer-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

function escapePrinterHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadPrintersAdmin() {
  const tbody = document.getElementById('printers-table-body');
  if (!tbody) return;
  try {
    const res = await fetch(`${API_BASE}/api/printers`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) throw new Error('Failed to load printers');
    const printers = await res.json();
    if (!Array.isArray(printers) || printers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="px-3 py-4 text-slate-500">No printers yet. Add one to get started.</td></tr>';
      return;
    }
    tbody.innerHTML = printers
      .map(
        (p) => `
      <tr data-printer-id="${p.id}">
        <td class="px-3 py-2 font-medium text-slate-800">${escapePrinterHtml(p.name)}</td>
        <td class="px-3 py-2 text-slate-600">${escapePrinterHtml(p.role)}</td>
        <td class="px-3 py-2 text-slate-600">${escapePrinterHtml(p.host || '—')}</td>
        <td class="px-3 py-2 text-slate-600">${escapePrinterHtml(p.port || 9100)}</td>
        <td class="px-3 py-2 text-slate-600">${p.is_active ? 'Yes' : 'No'}</td>
        <td class="px-3 py-2 text-right space-x-2 whitespace-nowrap">
          <button type="button" class="printer-edit-btn text-blue-600 hover:underline" data-id="${p.id}">Edit</button>
          <button type="button" class="printer-delete-btn text-red-600 hover:underline" data-id="${p.id}">Delete</button>
        </td>
      </tr>`
      )
      .join('');

    tbody.querySelectorAll('.printer-edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = Number(btn.getAttribute('data-id'));
        const printer = printers.find((x) => x.id === id);
        if (printer) openPrinterModal(printer);
      });
    });
    tbody.querySelectorAll('.printer-delete-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-id'));
        const ok = await dialogConfirm('Delete this printer?', 'Delete Printer');
        if (!ok) return;
        try {
          const delRes = await fetch(`${API_BASE}/api/printers/${id}`, {
            method: 'DELETE',
            headers: { ...window.auth.getAuthHeaders() },
          });
          if (window.auth && window.auth.checkUnauthorized(delRes)) return;
          if (!delRes.ok) {
            const err = await delRes.json().catch(() => ({}));
            await dialogAlert(err.detail || 'Failed to delete printer', 'error', 'Printers');
            return;
          }
          await loadPrintersAdmin();
        } catch (err) {
          console.error(err);
          await dialogAlert('Failed to delete printer', 'error', 'Printers');
        }
      });
    });
  } catch (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="6" class="px-3 py-4 text-red-600">Error loading printers.</td></tr>';
  }
}

const btnAddPrinter = document.getElementById('btn-add-printer');
if (btnAddPrinter) btnAddPrinter.addEventListener('click', () => openPrinterModal(null));
const printerModalCancel = document.getElementById('printer-modal-cancel');
if (printerModalCancel) printerModalCancel.addEventListener('click', closePrinterModal);
const printerModal = document.getElementById('printer-modal');
if (printerModal) {
  printerModal.addEventListener('click', (e) => {
    if (e.target === printerModal) closePrinterModal();
  });
}
const printerModalSave = document.getElementById('printer-modal-save');
if (printerModalSave) {
  printerModalSave.addEventListener('click', async () => {
    const id = String(document.getElementById('printer-edit-id')?.value || '').trim();
    const name = String(document.getElementById('printer-form-name')?.value || '').trim();
    const host = String(document.getElementById('printer-form-host')?.value || '').trim();
    const port = Number(document.getElementById('printer-form-port')?.value || 9100);
    const role = String(document.getElementById('printer-form-role')?.value || 'kitchen').trim();
    const isActive = !!document.getElementById('printer-form-active')?.checked;
    if (!name) {
      await dialogAlert('Name is required.', 'error', 'Printers');
      return;
    }
    const payload = {
      name,
      host: host || null,
      port: port || 9100,
      role,
      is_active: isActive,
    };
    try {
      const url = id ? `${API_BASE}/api/printers/${id}` : `${API_BASE}/api/printers`;
      const method = id ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify(payload),
      });
      if (window.auth && window.auth.checkUnauthorized(res)) return;
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await dialogAlert(err.detail || 'Failed to save printer', 'error', 'Printers');
        return;
      }
      closePrinterModal();
      await loadPrintersAdmin();
    } catch (err) {
      console.error(err);
      await dialogAlert('Failed to save printer', 'error', 'Printers');
    }
  });
}

async function loadPredefinedInstructionsAdmin() {
  const listEl = document.getElementById('predefined-instructions-list');
  if (!listEl) return;
  try {
    const res = await fetch(`${API_BASE}/api/predefined-instructions`, {
      headers: { ...window.auth.getAuthHeaders() },
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    if (!res.ok) throw new Error('Failed to load instruction tags');
    const tags = await res.json();
    renderPredefinedInstructionsList(Array.isArray(tags) ? tags : []);
  } catch (err) {
    console.error(err);
    listEl.innerHTML = '<li class="text-red-600">Error loading instruction tags.</li>';
  }
}

function renderPredefinedInstructionsList(tags) {
  const listEl = document.getElementById('predefined-instructions-list');
  if (!listEl) return;
  if (!tags.length) {
    listEl.innerHTML = '<li class="text-slate-500">No quick tags yet. Add one above.</li>';
    return;
  }
  listEl.innerHTML = tags.map((tag) => `
    <li class="flex items-center justify-between gap-2 border border-slate-200 rounded-md px-3 py-2">
      <span>${escapeHtml(tag.text)}</span>
      <button type="button" data-delete-instruction-id="${tag.id}" class="text-sm text-rose-600 hover:text-rose-800">Delete</button>
    </li>
  `).join('');
  listEl.querySelectorAll('[data-delete-instruction-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-delete-instruction-id');
      if (!id) return;
      try {
        const res = await fetch(`${API_BASE}/api/predefined-instructions/${id}`, {
          method: 'DELETE',
          headers: { ...window.auth.getAuthHeaders() },
        });
        if (window.auth && window.auth.checkUnauthorized(res)) return;
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          await dialogAlert(err.detail || 'Failed to delete tag', 'error', 'Quick Tags');
          return;
        }
        await loadPredefinedInstructionsAdmin();
      } catch (err) {
        console.error(err);
        await dialogAlert('Failed to delete tag', 'error', 'Quick Tags');
      }
    });
  });
}

async function loadMenuData() {
  const isMenuAdmin = isMenuAdminPanelRole(getCounterUserRole());
  if (isMenuAdmin) {
    try {
      await loadKitchenPrinterSettings();
    } catch (e) {
      console.error('Kitchen printer settings failed:', e);
    }
    try {
      await loadPrintersAdmin();
    } catch (e) {
      console.error('Printers admin failed:', e);
    }
    try {
      await loadPredefinedInstructionsAdmin();
    } catch (e) {
      console.error('Predefined instructions failed:', e);
    }
  }

  const [categoriesResult, menuItemsResult] = await Promise.allSettled([
    fetchCategories(),
    fetchMenuItems(),
  ]);

  if (categoriesResult.status === 'fulfilled') {
    categoriesCache = categoriesResult.value || [];
    renderCategories(categoriesCache);
    populateCategorySelect(categoriesCache);
  } else {
    console.error(categoriesResult.reason);
    const categoriesList = document.getElementById('categories-list');
    if (categoriesList) {
      categoriesList.innerHTML = '<li class="text-red-600">Error loading categories.</li>';
    }
  }

  if (menuItemsResult.status === 'fulfilled') {
    menuItemsCache = menuItemsResult.value || [];
    refreshMenuItemsView();
  } else {
    console.error(menuItemsResult.reason);
    const menuList = document.getElementById('menu-items-list');
    if (menuList) {
      menuList.innerHTML = '<li class="text-red-600">Error loading menu items.</li>';
    }
  }
}

document.getElementById('form-category').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('category-name');
  const routeSelect = document.getElementById('category-printer-route');
  const name = input.value.trim();
  if (!name) {
    await dialogAlert('Category name is required.', 'error', 'Create Category');
    return;
  }
  const routeValue = routeSelect ? String(routeSelect.value || '').trim() : '';
  const payload = { name };
  if (routeValue) payload.printer_route = routeValue;
  try {
    await apiJsonRequest(`${API_BASE}/api/categories/`, {
      method: 'POST',
      body: payload,
      fallbackMessage: 'Failed to create category',
    });
    if (window.toast) window.toast.success('Category created.');
    input.value = '';
    if (routeSelect) routeSelect.value = '';
    await loadMenuData();
  } catch (err) {
    console.error(err);
    await dialogAlert(err.message || 'Failed to create category', 'error', 'Create Category');
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

document.getElementById('item-tax-type')?.addEventListener('change', syncTaxValueFieldState);

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = document.getElementById('form-menu-item');
  const imageFile = document.getElementById('item-image-file').files?.[0];
  const editItemId = Number(document.getElementById('menu-edit-item-id').value || 0);
  const isEditMode = form?.getAttribute('data-mode') === 'edit' && !!editItemId;
  const imageUrl = document.getElementById('item-image-url').value.trim() || null;
  if (imageFile && !imageUrl) {
    await dialogAlert('Please wait for image upload to finish.', 'error', 'Upload In Progress');
    return;
  }
  const btn = document.getElementById('btn-submit-menu-item');
  btn.disabled = true;
  try {
    const payload = buildMenuItemPayloadFromForm();
    if (isEditMode) {
      delete payload.is_available;
      await updateMenuItem(editItemId, payload);
    } else {
      await apiJsonRequest(`${API_BASE}/api/menu-items/`, {
        method: 'POST',
        body: payload,
        fallbackMessage: 'Failed to create menu item',
      });
      if (window.toast) window.toast.success('Menu item created.');
    }
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
        loadUnpaidOrders();
        const data = msg.data;
        const tableRef = data.table_id || data.table_number;
        const isTakeawayBatch = String(data.order_type || '').toLowerCase() === 'takeaway' || (!tableRef && data.order_id);
        if (selectedOrderId != null && data.order_id === selectedOrderId && (tableRef || isTakeawayBatch)) {
          if (isTakeawayBatch && !tableRef) {
            fetch(`${API_BASE}/api/orders/${data.order_id}/details`, {
              headers: { ...window.auth.getAuthHeaders() },
            })
              .then((res) => (res.ok ? res.json() : null))
              .then((order) => order && selectOrder(order))
              .catch(() => {});
          } else {
            fetchActiveOrderByTable(tableRef)
              .then((order) => selectOrder(order))
              .catch(() => {});
          }
        }
      }
      if (msg.event === 'order_updated' && msg.data && msg.data.status) {
        const status = String(msg.data.status || '').toLowerCase();
        if (status === 'cancelled' || status === 'paid') {
          handleRemoteOrderClosed(msg.data);
        } else {
          loadUnpaidOrders();
        }
      }
      if (msg.event === 'order_cancelled' && msg.data) {
        handleRemoteOrderClosed(msg.data);
      }
      if (msg.event === 'order_completed' && msg.data) {
        handleRemoteOrderClosed(msg.data);
      }
      if (msg.event === 'takeaways_updated') {
        const status = String(msg.data?.status || '').toLowerCase();
        if (status === 'cancelled' || status === 'paid') {
          handleRemoteOrderClosed(msg.data || {});
        } else {
          loadUnpaidOrders();
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
bindCategoryEditModal();
if (
  window.auth &&
  window.auth.getToken() &&
  ['cashier', 'admin', 'root'].includes(String(window.auth.getUser?.()?.role || '').toLowerCase())
) {
  loadUnpaidOrders();
  loadMenuData();
  connectCounterWebSocket();
}
