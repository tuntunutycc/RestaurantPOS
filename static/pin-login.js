(function () {
  const PIN_LENGTH = 4;
  const dotsEl = document.getElementById("pin-dots");
  const errorEl = document.getElementById("pin-error");
  const btnClear = document.getElementById("btn-clear");
  const btnBack = document.getElementById("btn-back");

  let pin = "";

  function updateDots() {
    if (!dotsEl) return;
    const dots = dotsEl.querySelectorAll(".pin-dot");
    dots.forEach((dot, i) => {
      const filled = i < pin.length;
      dot.classList.toggle("bg-slate-500", filled);
      dot.classList.toggle("border-slate-500", filled);
      dot.classList.toggle("bg-transparent", !filled);
      dot.classList.toggle("border-slate-300", !filled);
    });
  }

  function showError() {
    if (errorEl) {
      errorEl.textContent = "Wrong PIN";
      errorEl.classList.remove("hidden");
    }
    if (dotsEl) dotsEl.classList.add("shake");
    setTimeout(() => {
      if (dotsEl) dotsEl.classList.remove("shake");
    }, 400);
    if (window.toast && window.toast.error) window.toast.error("Wrong PIN");
  }

  function hideError() {
    if (errorEl) errorEl.classList.add("hidden");
  }

  function clearPin() {
    pin = "";
    updateDots();
    hideError();
  }

  function submitPin() {
    if (pin.length !== PIN_LENGTH) return;
    if (dotsEl) dotsEl.setAttribute("aria-busy", "true");

    fetch("/api/auth/login-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin_code: pin }),
    })
      .then((res) => {
        if (res.status === 401) {
          clearPin();
          showError();
          return null;
        }
        if (!res.ok) return res.json().then(() => null);
        return res.json();
      })
      .then((data) => {
        if (dotsEl) dotsEl.removeAttribute("aria-busy");
        if (!data || !data.access_token || !data.user) return;
        if (window.auth) window.auth.setAuth(data.access_token, data.user);
        const role = data.user.role;
        const page =
          role === "waiter"
            ? "/waiter"
            : role === "kitchen"
              ? "/kitchen"
              : role === "cashier"
                ? "/counter"
                : "/counter";
        window.location.href = page;
      })
      .catch(() => {
        if (dotsEl) dotsEl.removeAttribute("aria-busy");
        clearPin();
        showError();
      });
  }

  function addDigit(d) {
    hideError();
    if (pin.length >= PIN_LENGTH) return;
    pin += d;
    updateDots();
    if (pin.length === PIN_LENGTH) submitPin();
  }

  function backspace() {
    hideError();
    if (pin.length === 0) return;
    pin = pin.slice(0, -1);
    updateDots();
  }

  // Already logged in → redirect by role
  if (window.auth && window.auth.getToken() && window.auth.getUser()) {
    const user = window.auth.getUser();
    const page =
      user.role === "waiter"
        ? "/waiter"
        : user.role === "kitchen"
          ? "/kitchen"
          : user.role === "cashier"
            ? "/counter"
            : "/counter";
    window.location.href = page;
    return;
  }

  // Numpad digit buttons
  document.querySelectorAll(".numpad-btn[data-digit]").forEach((btn) => {
    btn.addEventListener("click", () => addDigit(btn.dataset.digit));
  });

  if (btnClear) btnClear.addEventListener("click", clearPin);
  if (btnBack) btnBack.addEventListener("click", backspace);

  // Keyboard: 0-9, Backspace
  document.addEventListener("keydown", (e) => {
    if (e.key >= "0" && e.key <= "9") {
      e.preventDefault();
      addDigit(e.key);
    } else if (e.key === "Backspace") {
      e.preventDefault();
      backspace();
    }
  });
})();
