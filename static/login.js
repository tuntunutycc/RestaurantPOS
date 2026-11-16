(function () {
  const form = document.getElementById("login-form");
  const submitBtn = document.getElementById("login-submit");
  const errorEl = document.getElementById("login-error");
  const unauthorizedEl = document.getElementById("login-unauthorized");
  const PASSWORD_ROLES = ["root", "admin"];

  function deviceId() {
    return window.posDevice && window.posDevice.getDeviceId ? window.posDevice.getDeviceId() : "unknown";
  }

  function redirectForRole(role) {
    const page = window.auth.ROLE_DEFAULT_PAGE[role] || "/login";
    window.location.href = page;
  }

  fetch("/api/setup/status")
    .then((r) => r.json())
    .then((data) => {
      if (data.needs_setup) window.location.href = "/setup";
    })
    .catch(() => {});

  // Stale tokens (e.g. after DB reset / wiped sessions) used to auto-redirect to
  // /counter; APIs then returned 401 and felt like "Unauthorized". Validate first.
  function clearStoredAuthStayOnLogin() {
    localStorage.removeItem("pos_token");
    localStorage.removeItem("pos_user");
  }

  (async function resumeIfSessionValid() {
    if (!(window.auth && window.auth.getToken() && window.auth.getUser())) return;
    const user = window.auth.getUser();
    if (!PASSWORD_ROLES.includes(user.role)) {
      clearStoredAuthStayOnLogin();
      return;
    }
    try {
      const res = await fetch("/api/auth/me", {
        headers: { ...window.auth.getAuthHeaders() },
      });
      if (!res.ok) {
        clearStoredAuthStayOnLogin();
        return;
      }
      redirectForRole(user.role);
    } catch {
      clearStoredAuthStayOnLogin();
    }
  })();

  const params = new URLSearchParams(window.location.search);
  if (params.get("unauthorized") === "1" && unauthorizedEl) {
    unauthorizedEl.classList.remove("hidden");
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    if (!username || !password) return;

    if (errorEl) {
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "Signing in…";

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, device_id: deviceId() }),
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg =
          res.status === 403
            ? data.detail || "This role must use PIN login."
            : data.detail || "Login failed.";
        if (errorEl) {
          errorEl.textContent = typeof msg === "string" ? msg : "Login failed.";
          errorEl.classList.remove("hidden");
        }
        return;
      }

      if (data.access_token && data.user) {
        window.auth.setAuth(data.access_token, data.user);
        if (!PASSWORD_ROLES.includes(data.user.role)) {
          window.auth.clearAuth();
          return;
        }
        redirectForRole(data.user.role);
      }
    } catch (err) {
      if (errorEl) {
        errorEl.textContent = "Network error. Please try again.";
        errorEl.classList.remove("hidden");
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign in";
    }
  });
})();
