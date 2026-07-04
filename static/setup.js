(function () {
  const form = document.getElementById("setup-form");
  const errorEl = document.getElementById("setup-error");
  const submitBtn = document.getElementById("setup-submit");

  fetch("/api/setup/status")
    .then((r) => r.json())
    .then((data) => {
      if (!data.needs_setup) window.location.href = "/login";
    })
    .catch(() => {});

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.classList.add("hidden");
    submitBtn.disabled = true;
    try {
      const res = await fetch("/api/setup/root", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value.trim(),
          password: document.getElementById("password").value,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        errorEl.textContent = data.detail || "Setup failed";
        errorEl.classList.remove("hidden");
        return;
      }
      if (window.auth && data.access_token) {
        window.auth.setAuth(data.access_token, data.user);
      }
      window.location.href = "/counter";
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
