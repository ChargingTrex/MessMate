/**
 * Shared admin chrome (app-shell.js)
 * -----------------------------------
 * The live clock in the top bar, which the student home has had since it was
 * built. The admin pages carry the same chrome now, so they share its script
 * rather than each page growing its own copy.
 */
(function () {
  const el = document.getElementById("appClock");
  if (!el) return;

  function tick() {
    const now = new Date();
    const pad = n => String(n).padStart(2, "0");
    el.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  }

  tick();
  setInterval(tick, 1000);
})();
