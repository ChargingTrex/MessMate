/**
 * Shared Chart.js setup (charts.js)
 * ----------------------------------
 * Loaded before dashboard.js and committee_dashboard.js, which both used to
 * carry their own copy of this configuration inline in the template.
 *
 * Three things live here because both dashboards need them to agree:
 *   1. theming read from the CSS tokens, so the charts follow the stylesheet
 *      instead of repeating its hexes;
 *   2. axis date labels — the raw sheet dates ("2026-09-24") were rendering
 *      rotated and overlapping;
 *   3. the empty state, which previously filled a 300px canvas box with one
 *      line of italic grey text.
 */
window.MessMateCharts = (function () {

  const css = getComputedStyle(document.documentElement);
  const token = (name, fallback) => (css.getPropertyValue(name).trim() || fallback);

  const THEME = {
    text:    token("--text-muted", "#94a3b8"),
    grid:    "rgba(148, 163, 184, 0.12)",
    accent:  token("--brand-from", "#60a5fa"),
    strong:  token("--text-strong", "#f1f5f9"),
  };

  if (window.Chart) {
    Chart.defaults.color = THEME.text;
    Chart.defaults.borderColor = THEME.grid;
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.maintainAspectRatio = false;

    // Tooltips: readable on the dark shell, and not a system default box.
    Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15, 23, 36, 0.95)";
    Chart.defaults.plugins.tooltip.borderColor = "rgba(255, 255, 255, 0.14)";
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.titleColor = THEME.strong;
    Chart.defaults.plugins.tooltip.bodyColor = token("--text-3", "#cbd5e1");
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.displayColors = false;

    // Users in a task should not wait for a chart to choreograph itself in,
    // and the setting is honoured rather than ignored.
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    Chart.defaults.animation = still ? false : { duration: 240, easing: "easeOutQuart" };
  }

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** "2026-09-24" -> "24 Sep". Anything unparseable is passed straight back. */
  function shortDate(value) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
    if (!m) return value;
    return `${parseInt(m[3], 10)} ${MONTHS[parseInt(m[2], 10) - 1]}`;
  }

  /** Axis config shared by both trend charts. */
  function dateAxis() {
    return {
      ticks: {
        // Flat, not rotated: diagonal ISO dates were unreadable on a phone.
        maxRotation: 0,
        minRotation: 0,
        autoSkip: true,
        maxTicksLimit: 7,
        callback: function (_v, index) {
          return shortDate(this.getLabelForValue(index));
        }
      },
      grid: { display: false }
    };
  }

  function scoreAxis() {
    return {
      beginAtZero: true,
      min: 0,
      max: 5,
      ticks: { stepSize: 1 },
      grid: { color: THEME.grid, drawTicks: false },
      border: { display: false }
    };
  }

  /**
   * Replaces a canvas with a real empty state and collapses its box.
   * `hint` says what would make the chart appear, rather than restating that
   * it is empty.
   */
  function empty(canvas, title, hint) {
    const wrapper = canvas && canvas.parentElement;
    if (!wrapper) return;
    wrapper.classList.add("is-empty");
    wrapper.innerHTML =
      '<div class="chart-empty">' +
        '<p class="chart-empty-title"></p>' +
        '<p class="chart-empty-hint"></p>' +
      '</div>';
    wrapper.querySelector(".chart-empty-title").textContent = title;
    wrapper.querySelector(".chart-empty-hint").textContent = hint || "";
  }

  /**
   * Legend that dims the series it has switched off.
   * Chart.js strikes hidden labels through by default, which on a dark
   * surface reads as a rendering fault rather than a toggle.
   */
  function dimmedLegend(extra) {
    return Object.assign({
      display: true,
      position: "bottom",
      labels: {
        usePointStyle: true,
        pointStyle: "circle",
        boxWidth: 8,
        boxHeight: 8,
        padding: 16,
        generateLabels: function (chart) {
          const items = Chart.defaults.plugins.legend.labels.generateLabels(chart);
          items.forEach(item => {
            const on = chart.isDatasetVisible(item.datasetIndex);
            item.hidden = false;                 // suppress the strike-through
            item.fontColor = on ? THEME.strong : THEME.text;
            if (!on) {
              // A filled dot at low opacity reads as "off" without the
              // hollow-box look an unfilled swatch gives.
              item.fillStyle = "rgba(148, 163, 184, 0.35)";
              item.strokeStyle = "rgba(148, 163, 184, 0.35)";
            }
          });
          return items;
        }
      }
    }, extra || {});
  }

  /**
   * Writes a "vs the day before" line under a stat value.
   * A single number with nothing to compare it against is not yet
   * information — 3.8 is good or bad depending on yesterday. Both dashboards
   * already ship the trend series to the page, so the comparison costs no
   * extra request.
   */
  function deltaNote(elementId, series, key, opts) {
    const el = document.getElementById(elementId);
    if (!el || !Array.isArray(series) || series.length < 2) return;

    // No value today means no comparison to draw. The template already decided
    // that when it marked the stat .is-empty and rendered "--"; without this
    // the last two *available* days get compared instead, so a card reading
    // "--" was captioned "down 0.1 vs yesterday".
    const card = el.closest(".stat-card");
    const value = card && card.querySelector(".stat-value");
    if (value && value.classList.contains("is-empty")) return;

    const o = opts || {};
    const today = Number(series[series.length - 1][key]);
    const prev  = Number(series[series.length - 2][key]);
    if (!isFinite(today) || !isFinite(prev) || prev === 0) return;

    const diff = today - prev;
    const dp = o.decimals === undefined ? 1 : o.decimals;
    if (Math.abs(diff) < Math.pow(10, -dp) / 2) {
      el.textContent = "Level with yesterday";
      return;
    }
    const arrow = diff > 0 ? "\u2191" : "\u2193";
    el.textContent = `${arrow} ${Math.abs(diff).toFixed(dp)}${o.suffix || ""} vs yesterday`;
    el.style.color = diff > 0
      ? token("--ok-text", "#6ee7a0")
      : token("--danger-text", "#fca5a5");
  }

  /** Wires a two-button segmented control to a render function. */
  function segmented(aEl, bEl, aDays, bDays, render) {
    if (!aEl || !bEl) return;
    // aria-pressed is the accessible state; the `active` class mirrors it
    // for the stylesheet and the UI suites, which read the class attribute.
    const pick = (chosen, other, days) => {
      chosen.setAttribute("aria-pressed", "true");
      other.setAttribute("aria-pressed", "false");
      chosen.classList.add("active");
      other.classList.remove("active");
      render(days);
    };
    aEl.addEventListener("click", () => pick(aEl, bEl, aDays));
    bEl.addEventListener("click", () => pick(bEl, aEl, bDays));
  }

  return { THEME, shortDate, dateAxis, scoreAxis, empty, dimmedLegend, segmented, deltaNote };
})();
