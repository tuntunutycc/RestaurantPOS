(function () {
  if (!window.auth || !window.auth.requireAuth() || !window.auth.requireRole(["account"])) return;
  window.auth.renderNav("pos-nav");

  const ACCOUNT_MAX_DAYS = 90;
  const ACCOUNT_ACCESS_DENIED_MSG =
    "Access denied. Accountant access is strictly limited to the last 90 days of financial data.";
  const fmt = (n) => (window.formatCurrency ? window.formatCurrency(n) : String(n));
  let dailyChart = null;
  let monthlyChart = null;
  let activeAccountTab = "overview";

  function formatDateInput(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function parseDateOnly(value) {
    if (!value) return null;
    const d = new Date(`${value}T00:00:00`);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function daysInclusive(start, end) {
    const ms = end.getTime() - start.getTime();
    return Math.floor(ms / 86400000) + 1;
  }

  function getOldestAllowedDate() {
    const oldest = new Date();
    oldest.setDate(oldest.getDate() - (ACCOUNT_MAX_DAYS - 1));
    oldest.setHours(0, 0, 0, 0);
    return oldest;
  }

  function applyDatePickerBounds() {
    const today = formatDateInput(new Date());
    const minDate = formatDateInput(getOldestAllowedDate());
    const startEl = document.getElementById("account-start-date");
    const endEl = document.getElementById("account-end-date");
    if (startEl) {
      startEl.min = minDate;
      startEl.max = today;
    }
    if (endEl) {
      endEl.min = minDate;
      endEl.max = today;
    }
  }

  function validateDateRange(startStr, endStr) {
    const start = parseDateOnly(startStr);
    const end = parseDateOnly(endStr);
    if (!start || !end) {
      return { ok: false, message: "Please select both start and end dates." };
    }
    if (start > end) {
      return { ok: false, message: "Start date cannot be after end date." };
    }
    const span = daysInclusive(start, end);
    if (span > ACCOUNT_MAX_DAYS) {
      return { ok: false, message: ACCOUNT_ACCESS_DENIED_MSG };
    }
    const oldest = getOldestAllowedDate();
    if (start < oldest) {
      return { ok: false, message: ACCOUNT_ACCESS_DENIED_MSG };
    }
    return { ok: true, start: startStr, end: endStr };
  }

  function showRangeError(message) {
    const errEl = document.getElementById("account-range-error");
    if (!errEl) return;
    errEl.textContent = message;
    errEl.classList.remove("hidden");
  }

  function hideRangeError() {
    const errEl = document.getElementById("account-range-error");
    if (errEl) errEl.classList.add("hidden");
  }

  function handleReportApiError(res, data) {
    const detail = typeof data?.detail === "string" ? data.detail : "";
    if (res.status === 400 || res.status === 403) {
      if (detail) {
        showRangeError(detail);
        return detail;
      }
      showRangeError(ACCOUNT_ACCESS_DENIED_MSG);
      return ACCOUNT_ACCESS_DENIED_MSG;
    }
    return detail || "Failed to load reports";
  }

  function renderCashierList(elId, rows) {
    const el = document.getElementById(elId);
    if (!el) return;
    if (!rows.length) {
      el.textContent = "No data for selected period";
      return;
    }
    el.innerHTML = rows
      .map(
        (r) =>
          `<div class="flex justify-between py-1 border-b border-slate-100"><span>${r.username} (${r.role})</span><span>${fmt(r.total_sales)} · ${r.order_count} orders</span></div>`
      )
      .join("");
  }

  async function loadSummary() {
    const res = await fetch("/api/reports/summary/today", { headers: window.auth.getAuthHeaders() });
    if (window.auth.checkUnauthorized(res)) return;
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("kpi-total-sales").textContent = fmt(data.total_sales);
    document.getElementById("kpi-total-orders").textContent = data.total_orders;
    document.getElementById("kpi-average-order-value").textContent = fmt(data.average_order_value);
  }

  async function loadCashierSalesToday() {
    const today = new Date().toISOString().slice(0, 10);
    const res = await fetch(`/api/reports/sales/by-cashier?start_date=${today}&end_date=${today}`, {
      headers: window.auth.getAuthHeaders(),
    });
    if (window.auth.checkUnauthorized(res)) return;
    const el = document.getElementById("cashier-sales-today");
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      if (el) el.textContent = handleReportApiError(res, data);
      return;
    }
    renderCashierList("cashier-sales-today", await res.json());
  }

  async function loadDailyChart(start, end) {
    const canvas = document.getElementById("account-daily-chart");
    if (!canvas || !window.Chart) return;
    const params = new URLSearchParams({ start_date: start, end_date: end });
    const res = await fetch(`/api/reports/daily-sales?${params}`, { headers: window.auth.getAuthHeaders() });
    if (window.auth.checkUnauthorized(res)) return;
    const rows = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(handleReportApiError(res, rows));
    const data = Array.isArray(rows) ? rows : [];
    if (dailyChart) dailyChart.destroy();
    dailyChart = new Chart(canvas, {
      type: "line",
      data: {
        labels: data.map((r) => r.date),
        datasets: [{ label: "Sales", data: data.map((r) => r.total), borderColor: "#2563eb", tension: 0.2, fill: false }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { ticks: { callback: (v) => fmt(v) } } },
      },
    });
  }

  async function loadMonthlyChart(year) {
    const canvas = document.getElementById("account-monthly-chart");
    if (!canvas || !window.Chart) return;
    const res = await fetch(`/api/reports/monthly-sales?year=${year}`, { headers: window.auth.getAuthHeaders() });
    if (window.auth.checkUnauthorized(res)) return;
    const rows = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(handleReportApiError(res, rows));
    const data = Array.isArray(rows) ? rows : [];
    if (monthlyChart) monthlyChart.destroy();
    monthlyChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.map((r) => r.month),
        datasets: [{ label: "Sales", data: data.map((r) => r.total), backgroundColor: "#0ea5e9", borderRadius: 6 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { ticks: { callback: (v) => fmt(v) } } },
      },
    });
  }

  async function loadCashierSalesRange(start, end) {
    const params = new URLSearchParams({ start_date: start, end_date: end });
    const res = await fetch(`/api/reports/sales/by-cashier?${params}`, { headers: window.auth.getAuthHeaders() });
    if (window.auth.checkUnauthorized(res)) return;
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      document.getElementById("cashier-sales-range").textContent = handleReportApiError(res, data);
      return;
    }
    renderCashierList("cashier-sales-range", await res.json());
  }

  async function applyHistoryFilters() {
    const startInput = document.getElementById("account-start-date");
    const endInput = document.getElementById("account-end-date");
    const yearInput = document.getElementById("account-year");
    const check = validateDateRange(startInput?.value, endInput?.value);
    if (!check.ok) {
      showRangeError(check.message);
      return;
    }
    hideRangeError();
    try {
      await Promise.all([
        loadDailyChart(check.start, check.end),
        loadMonthlyChart(Number(yearInput?.value) || new Date().getFullYear()),
        loadCashierSalesRange(check.start, check.end),
      ]);
    } catch (e) {
      showRangeError(e.message || ACCOUNT_ACCESS_DENIED_MSG);
    }
  }

  function setDefaultHistoryDates() {
    const today = new Date();
    const start = new Date(today);
    start.setDate(today.getDate() - 29);
    const startEl = document.getElementById("account-start-date");
    const endEl = document.getElementById("account-end-date");
    const yearEl = document.getElementById("account-year");
    if (endEl) endEl.value = formatDateInput(today);
    if (startEl) startEl.value = formatDateInput(start);
    if (yearEl) yearEl.value = String(today.getFullYear());
    applyDatePickerBounds();
  }

  function applyAccountTab(tab) {
    activeAccountTab = tab;
    document.querySelectorAll("[data-account-tab-btn]").forEach((btn) => {
      const key = btn.getAttribute("data-account-tab-btn");
      const active = key === tab;
      btn.classList.toggle("border-blue-600", active);
      btn.classList.toggle("text-blue-700", active);
      btn.classList.toggle("font-semibold", active);
      btn.classList.toggle("border-transparent", !active);
      btn.classList.toggle("text-slate-500", !active);
      btn.classList.toggle("font-medium", !active);
    });
    document.querySelectorAll("[data-account-tab-content]").forEach((section) => {
      section.classList.toggle("hidden", section.getAttribute("data-account-tab-content") !== tab);
    });
    if (tab === "history") applyHistoryFilters();
  }

  document.querySelectorAll("[data-account-tab-btn]").forEach((btn) => {
    btn.addEventListener("click", () => applyAccountTab(btn.getAttribute("data-account-tab-btn")));
  });

  const applyBtn = document.getElementById("btn-account-apply-filter");
  if (applyBtn) applyBtn.addEventListener("click", applyHistoryFilters);

  setDefaultHistoryDates();
  loadSummary();
  loadCashierSalesToday();
})();
