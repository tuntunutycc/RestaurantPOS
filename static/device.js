(function () {
  const KEY = "pos_device_id";

  function getDeviceId() {
    try {
      let id = localStorage.getItem(KEY);
      if (!id) {
        id =
          typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : "dev-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        localStorage.setItem(KEY, id);
      }
      return id;
    } catch {
      return "unknown-device";
    }
  }

  window.posDevice = { getDeviceId };
})();
