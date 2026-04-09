/**
 * Lightweight vanilla JS toast notifications (no React).
 * Usage: toast.success('Message'), toast.error('Error message')
 */
(function () {
  const CONTAINER_ID = 'toast-container';
  const DURATION_MS = 500;
  const FADE_OUT_MS = 100;

  function ensureContainer() {
    let el = document.getElementById(CONTAINER_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = CONTAINER_ID;
      el.setAttribute('aria-live', 'polite');
      el.className = 'fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm w-full pointer-events-none';
      document.body.appendChild(el);
    }
    return el;
  }

  function show(message, type) {
    const container = ensureContainer();
    const toast = document.createElement('div');
    toast.className =
      'pointer-events-auto px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white ' +
      (type === 'error'
        ? 'bg-red-600'
        : type === 'success'
          ? 'bg-emerald-600'
          : 'bg-slate-700');
    toast.textContent = message;
    container.appendChild(toast);
    const t = setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = `opacity ${FADE_OUT_MS}ms`;
      setTimeout(() => toast.remove(), FADE_OUT_MS);
    }, DURATION_MS);
    toast.addEventListener('click', () => {
      clearTimeout(t);
      toast.style.opacity = '0';
      toast.style.transition = `opacity ${FADE_OUT_MS}ms`;
      setTimeout(() => toast.remove(), FADE_OUT_MS);
    });
  }

  window.toast = {
    success: (msg) => show(msg, 'success'),
    error: (msg) => show(msg, 'error'),
    info: (msg) => show(msg, 'info'),
  };
})();
