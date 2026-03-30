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
    admin: "/counter",
    waiter: "/waiter",
    cashier: "/counter",
  };

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
      '<button type="button" id="pos-logout-btn" class="px-3 py-1.5 bg-slate-600 text-white text-sm font-medium rounded hover:bg-slate-700">Logout</button>' +
      "</div>";
    const btn = document.getElementById("pos-logout-btn");
    if (btn) btn.addEventListener("click", clearAuth);
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
      if (window.toast && window.toast.error) {
        window.toast.error("You are not allowed to access that page.");
      } else {
        alert("You are not allowed to access that page.");
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
    ROLE_DEFAULT_PAGE,
  };
})();
