(function () {
  const form = document.getElementById("login-form");
  const submitBtn = document.getElementById("login-submit");
  const errorEl = document.getElementById("login-error");
  const unauthorizedEl = document.getElementById("login-unauthorized");

  // If already logged in, redirect to default page by role
  if (window.auth && window.auth.getToken() && window.auth.getUser()) {
    const user = window.auth.getUser();
    const page = window.auth.ROLE_DEFAULT_PAGE[user.role] || "/counter";
    window.location.href = page;
    return;
  }

  // Show "unauthorized" message if redirected from a forbidden page
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
      const url = (typeof window !== "undefined" && window.location.origin)
        ? window.location.origin + "/api/auth/login"
        : "/api/auth/login";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json().catch(function () {
        return {};
      });

      if (!res.ok) {
        const msg = (data.detail && (typeof data.detail === "string" ? data.detail : data.detail[0]?.msg || data.detail))
          || "Login failed.";
        if (errorEl) {
          errorEl.textContent = msg;
          errorEl.classList.remove("hidden");
        }
        return;
      }

      if (data.access_token && data.user) {
        window.auth.setAuth(data.access_token, data.user);
        const page = window.auth.ROLE_DEFAULT_PAGE[data.user.role] || "/counter";
        window.location.href = page;
      } else {
        if (errorEl) {
          errorEl.textContent = "Invalid response from server.";
          errorEl.classList.remove("hidden");
        }
      }
    } catch (err) {
      if (errorEl) {
        const msg = err && err.message ? err.message : "Network error. Please try again.";
        errorEl.textContent = msg.indexOf("fetch") !== -1 ? "Cannot reach server. Check the URL and that the app is running." : msg;
        errorEl.classList.remove("hidden");
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign in";
    }
  });
})();
