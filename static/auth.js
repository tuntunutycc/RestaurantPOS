/**
 * POS Authentication & Route Guards
 * - Token and user stored in localStorage (pos_token, pos_user).
 * - requireAuth(): redirect to /login if not logged in.
 * - requireRole(allowedRoles): redirect to role default page if not allowed; show "Unauthorized" when applicable.
 * - renderNav(containerId): render header with user, role, logout.
 * - getAuthHeaders(): use for fetch() calls to include JWT.
 */

(function () {
  const TOKEN_KEY = "pos_token";
  const USER_KEY = "pos_user";
  const UNAUTHORIZED_FLAG = "pos_unauthorized";

  const ROLE_DEFAULT_PAGE = {
    root: "/counter",
    admin: "/counter",
    account: "/account",
    waiter: "/waiter",
    cashier: "/counter",
  };

  const PASSWORD_ROLES = ["root", "admin"];

  function t(key, fallback) {
    return window.i18n?.t?.(key) || fallback || key;
  }

  function ensureChangePasswordModal() {
    if (document.getElementById("pos-change-password-modal")) return;

    const overlay = document.createElement("div");
    overlay.id = "pos-change-password-modal";
    overlay.className = "hidden fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4";
    overlay.innerHTML =
      '<div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">' +
      '<h2 id="pos-change-password-title" class="text-lg font-semibold text-slate-800 mb-4">Change Password</h2>' +
      '<p id="pos-change-password-error" class="hidden mb-3 p-2 text-sm text-red-700 bg-red-50 rounded"></p>' +
      '<form id="pos-change-password-form" class="space-y-4">' +
      '<div>' +
      '<label for="pos-current-password" class="block text-sm font-medium text-slate-700 mb-1" data-i18n="current_password">Current Password</label>' +
      '<input type="password" id="pos-current-password" required autocomplete="current-password" class="w-full px-3 py-2 border border-slate-300 rounded-lg" />' +
      "</div>" +
      '<div>' +
      '<label for="pos-new-password" class="block text-sm font-medium text-slate-700 mb-1" data-i18n="new_password">New Password</label>' +
      '<input type="password" id="pos-new-password" required minlength="6" autocomplete="new-password" class="w-full px-3 py-2 border border-slate-300 rounded-lg" />' +
      "</div>" +
      '<div>' +
      '<label for="pos-confirm-password" class="block text-sm font-medium text-slate-700 mb-1" data-i18n="confirm_new_password">Confirm New Password</label>' +
      '<input type="password" id="pos-confirm-password" required minlength="6" autocomplete="new-password" class="w-full px-3 py-2 border border-slate-300 rounded-lg" />' +
      "</div>" +
      '<div class="flex gap-2 justify-end pt-2">' +
      '<button type="button" id="pos-change-password-cancel" class="px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200" data-i18n="close">Close</button>' +
      '<button type="submit" id="pos-change-password-submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700" data-i18n="save">Save</button>' +
      "</div>" +
      "</form>" +
      "</div>";

    document.body.appendChild(overlay);

    const form = document.getElementById("pos-change-password-form");
    const cancelBtn = document.getElementById("pos-change-password-cancel");
    const errorEl = document.getElementById("pos-change-password-error");

    function closeModal() {
      overlay.classList.add("hidden");
      form.reset();
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }

    cancelBtn.addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorEl.classList.add("hidden");

      const currentPassword = document.getElementById("pos-current-password").value;
      const newPassword = document.getElementById("pos-new-password").value;
      const confirmPassword = document.getElementById("pos-confirm-password").value;

      if (newPassword.length < 6) {
        errorEl.textContent = t("password_min_length", "New password must be at least 6 characters.");
        errorEl.classList.remove("hidden");
        return;
      }
      if (newPassword !== confirmPassword) {
        errorEl.textContent = t("password_mismatch", "New passwords do not match.");
        errorEl.classList.remove("hidden");
        return;
      }

      const submitBtn = document.getElementById("pos-change-password-submit");
      submitBtn.disabled = true;
      try {
        const res = await fetch("/api/auth/change-password", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (checkUnauthorized(res)) return;
        if (!res.ok) {
          const detail = data.detail;
          errorEl.textContent =
            typeof detail === "string" ? detail : t("error", "Error");
          errorEl.classList.remove("hidden");
          return;
        }
        closeModal();
        const msg = t("password_changed", "Password changed successfully.");
        if (window.toast && window.toast.success) window.toast.success(msg);
        else alert(msg);
      } catch {
        errorEl.textContent = t("error", "Error");
        errorEl.classList.remove("hidden");
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function openChangePasswordModal() {
    ensureChangePasswordModal();
    const overlay = document.getElementById("pos-change-password-modal");
    const title = document.getElementById("pos-change-password-title");
    if (title) title.textContent = t("change_password", "Change Password");
    if (window.updateUILanguage) window.updateUILanguage();
    overlay.classList.remove("hidden");
    const input = document.getElementById("pos-current-password");
    if (input) input.focus();
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function setAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = "/login";
  }

  /** Returns headers object to merge into fetch() for authenticated requests. */
  function getAuthHeaders() {
    const token = getToken();
    return token ? { Authorization: "Bearer " + token } : {};
  }

  /**
   * Call on protected pages. Redirects to /login if no token.
   */
  function requireAuth() {
    if (!getToken()) {
      window.location.href = "/login";
      return false;
    }
    return true;
  }

  /**
   * Call after requireAuth(). If current user role is not in allowedRoles,
   * redirects to their default page and sets flag to show "Unauthorized".
   */
  function requireRole(allowedRoles) {
    const user = getUser();
    if (!user || !user.role) {
      clearAuth();
      return false;
    }
    if (allowedRoles.indexOf(user.role) === -1) {
      localStorage.setItem(UNAUTHORIZED_FLAG, "1");
      const defaultPage = ROLE_DEFAULT_PAGE[user.role] || "/waiter";
      window.location.href = defaultPage;
      return false;
    }
    return true;
  }

  /**
   * Call once on protected pages after requireAuth + requireRole.
   * Renders nav into the element with id containerId.
   */
  function renderNav(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const user = getUser();
    const name = (user && user.username) || "User";
    const role = (user && user.role) || "";
    const lang = window.i18n?.currentLang || "en";
    const langLabel = lang === "my" ? "မြန်မာ" : "EN";
    const showChangePassword = PASSWORD_ROLES.indexOf(role) !== -1;
    const showTakeOrders = role === "cashier" || role === "waiter";
    const changePasswordBtn = showChangePassword
      ? '<button type="button" id="pos-change-password-btn" data-i18n="change_password" class="px-3 py-1.5 bg-amber-600 text-white text-sm font-medium rounded hover:bg-amber-700">Change Password</button>'
      : "";
    const takeOrdersLink = showTakeOrders
      ? '<a href="/waiter" id="pos-take-orders-link" class="px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium rounded hover:bg-emerald-700">Take Orders</a>'
      : "";
    container.innerHTML =
      '<div class="flex flex-wrap items-center justify-between gap-2 mb-4 p-3 bg-slate-200 rounded-lg">' +
      '<div class="flex items-center gap-3">' +
      '<span class="font-medium text-slate-800">' +
      escapeHtml(name) +
      "</span>" +
      '<span class="text-sm text-slate-600">(' +
      escapeHtml(role) +
      ")</span>" +
      "</div>" +
      '<div class="flex items-center gap-2 flex-wrap justify-end">' +
      takeOrdersLink +
      changePasswordBtn +
      `<button type="button" id="pos-lang-toggle-btn" class="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-700">` +
      `${escapeHtml(langLabel)} / မြန်မာ</button>` +
      '<button type="button" id="pos-logout-btn" data-i18n="logout" class="px-3 py-1.5 bg-slate-600 text-white text-sm font-medium rounded hover:bg-slate-700">Logout</button>' +
      "</div>" +
      "</div>";
    const btn = document.getElementById("pos-logout-btn");
    if (btn) btn.addEventListener("click", clearAuth);
    const pwBtn = document.getElementById("pos-change-password-btn");
    if (pwBtn) pwBtn.addEventListener("click", openChangePasswordModal);
    const langBtn = document.getElementById("pos-lang-toggle-btn");
    if (langBtn && window.toggleLanguage) {
      langBtn.addEventListener("click", () => {
        const next = window.toggleLanguage();
        langBtn.textContent = `${next === "my" ? "မြန်မာ" : "EN"} / မြန်မာ`;
      });
    }
    if (window.updateUILanguage) window.updateUILanguage();
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  /** Call on a protected page to show "Unauthorized" toast if user was redirected from a forbidden page. */
  function consumeUnauthorizedFlag() {
    if (localStorage.getItem(UNAUTHORIZED_FLAG)) {
      localStorage.removeItem(UNAUTHORIZED_FLAG);
      const msg = window.i18n?.t?.("unauthorized_message") || "You are not allowed to access that page.";
      if (window.toast && window.toast.error) {
        window.toast.error(msg);
      } else if (window.CustomDialog?.alert) {
        window.CustomDialog.alert(window.i18n?.t?.("error") || "Error", msg);
      } else {
        console.warn(msg);
      }
    }
  }

  /** If response is 401, clear auth and redirect to login. Call after fetch(). Returns true if was 401. */
  function checkUnauthorized(res) {
    if (res && res.status === 401) {
      clearAuth();
      return true;
    }
    return false;
  }

  window.auth = {
    getToken,
    getUser,
    setAuth,
    clearAuth,
    getAuthHeaders,
    requireAuth,
    requireRole,
    renderNav,
    consumeUnauthorizedFlag,
    checkUnauthorized,
    openChangePasswordModal,
    PASSWORD_ROLES,
    ROLE_DEFAULT_PAGE,
  };
})();
