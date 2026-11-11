/**
 * Light / dark switch (theme.js)
 * -------------------------------
 * Both themes are defined in ui_config.py and served in /ui/tokens.css; the
 * theme in force is whatever <html data-theme> says, or, with no attribute,
 * the device setting (when ui_config.DEFAULT_THEME is "system") or the
 * configured default. _theme_head.html restores a saved choice before paint;
 * this file runs every [data-theme-toggle] button and saves new choices.
 */
(function () {
  const cfg = (window.MESSMATE_UI || {}).theme || {};
  const KEY = cfg.storageKey || "messmate-theme";
  const DEFAULT = cfg.default || "system";
  const root = document.documentElement;
  const prefersLight = window.matchMedia("(prefers-color-scheme: light)");

  function current() {
    const set = root.getAttribute("data-theme");
    if (set === "light" || set === "dark") return set;
    if (DEFAULT === "system") return prefersLight.matches ? "light" : "dark";
    return DEFAULT === "light" ? "light" : "dark";
  }

  function render() {
    const next = current() === "light" ? "dark" : "light";
    document.querySelectorAll("[data-theme-toggle]").forEach(btn => {
      const label = btn.querySelector(".theme-toggle-label");
      if (label) label.textContent = next === "light" ? "Light" : "Dark";
      btn.setAttribute("aria-label", `Switch to ${next} mode`);
    });
  }

  document.addEventListener("click", event => {
    const btn = event.target.closest("[data-theme-toggle]");
    if (!btn) return;
    const next = current() === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem(KEY, next); } catch (e) { /* private mode: applies for this page only */ }
    render();
    // Charts take their colours when drawn; redraw them in the new theme.
    if (window.Chart && Chart.instances && Object.keys(Chart.instances).length) {
      window.location.reload();
    }
  });

  if (prefersLight.addEventListener) prefersLight.addEventListener("change", render);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})();
