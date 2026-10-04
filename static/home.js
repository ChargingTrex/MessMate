/**
 * MessMate Student Home (home.js)
 * ---------------------------------
 * Progressive enhancement: real-time clock, day switcher, active meal
 * detection, meal filter pills, ticker, scroll-to-top, and double-tap guard.
 * The reaction buttons remain real submit buttons so the page works without JS.
 */

document.addEventListener("DOMContentLoaded", function () {

  // ── 1. Live Digital Clock ─────────────────────────────────────────────────
  const clockEl = document.getElementById("currentTime");
  function updateClock() {
    if (!clockEl) return;
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    clockEl.textContent = `${h}:${m}:${s}`;
  }
  updateClock();
  setInterval(updateClock, 1000);


  // ── 2. Active Meal Detection ──────────────────────────────────────────────
  // Breakfast: 07:30–09:30, Lunch: 12:30–14:30, Dinner: 19:30–21:30
  const MEAL_WINDOWS = {
    Breakfast: [7 * 60 + 30, 9 * 60 + 30],
    Lunch:     [12 * 60 + 30, 14 * 60 + 30],
    Dinner:    [19 * 60 + 30, 21 * 60 + 30],
  };

  function detectActiveMeal() {
    const now = new Date();
    const mins = now.getHours() * 60 + now.getMinutes();
    for (const [meal, [start, end]] of Object.entries(MEAL_WINDOWS)) {
      if (mins >= start && mins <= end) return meal;
    }
    // If no meal is currently active, return the next one
    for (const [meal, [start]] of Object.entries(MEAL_WINDOWS)) {
      if (mins < start) return null; // nothing active; 'null' used for spotlight
    }
    return null;
  }

  function highlightActiveMeal() {
    const active = detectActiveMeal();
    const meals = window.MESSMATE_MEALS || ["Breakfast", "Lunch", "Dinner"];

    meals.forEach(meal => {
      const card  = document.getElementById("mealcard-" + meal.toLowerCase());
      const badge = document.getElementById("badge-" + meal.toLowerCase());
      if (!card || !badge) return;

      if (meal === active) {
        card.classList.add("active-meal");
        badge.style.display = "inline-block";
      } else {
        card.classList.remove("active-meal");
        badge.style.display = "none";
      }
    });

    // Spotlight widget
    updateSpotlight(active);
  }

  function updateSpotlight(activeMeal) {
    const servingDot   = document.getElementById("servingDot");
    const servingLabel = document.getElementById("servingLabel");
    const mealName     = document.getElementById("activeMealName");
    const dishesList   = document.getElementById("activeMealDishes");

    const isToday = window.MESSMATE_SELECTED === window.MESSMATE_TODAY_ISO;
    const weekData = window.MESSMATE_WEEK || {};
    const todayData = weekData[window.MESSMATE_TODAY_ISO] || {};

    if (activeMeal && isToday) {
      if (servingDot) { servingDot.className = "serving-dot"; }
      if (servingLabel) servingLabel.textContent = "SERVING NOW";
      if (mealName)    mealName.textContent = activeMeal;

      // Show dishes for active meal from today's menu
      const dishes = todayData[activeMeal] || [];
      if (dishesList) {
        if (dishes.length > 0) {
          dishesList.innerHTML = dishes.map(d => `<li>${d}</li>`).join("");
        } else {
          dishesList.innerHTML = `<li class="specials-loading">Menu not published yet</li>`;
        }
      }
    } else {
      // Find next meal
      const now = new Date();
      const mins = now.getHours() * 60 + now.getMinutes();
      let nextMeal = null;
      for (const [meal, [start]] of Object.entries(MEAL_WINDOWS)) {
        if (mins < start) { nextMeal = meal; break; }
      }

      if (servingDot) { servingDot.className = "serving-dot inactive"; }
      if (nextMeal) {
        if (servingLabel) servingLabel.textContent = "NEXT MEAL";
        if (mealName)    mealName.textContent = nextMeal;
        const dishes = isToday ? (todayData[nextMeal] || []) : [];
        if (dishesList) {
          dishesList.innerHTML = dishes.length
            ? dishes.map(d => `<li>${d}</li>`).join("")
            : `<li class="specials-loading">Menu not published</li>`;
        }
      } else {
        if (servingLabel) servingLabel.textContent = "MEALS DONE FOR TODAY";
        if (mealName)    mealName.textContent = "Dinner";
        if (dishesList)  dishesList.innerHTML = `<li class="specials-loading">Come back tomorrow!</li>`;
      }
    }
  }

  highlightActiveMeal();
  // Re-check every minute so it updates without a page reload
  setInterval(highlightActiveMeal, 60 * 1000);


  // ── 3. Day Switcher ────────────────────────────────────────────────────────
  // Instant client-side switching using embedded weekly schedule data.
  window.switchDay = function (dateStr) {
    const weekData = window.MESSMATE_WEEK || {};
    const meals    = window.MESSMATE_MEALS || ["Breakfast", "Lunch", "Dinner"];
    const dayData  = weekData[dateStr] || {};

    // Update active tab
    document.querySelectorAll(".day-tab").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.date === dateStr);
    });

    // Update menu items inside each meal card
    meals.forEach(meal => {
      const listEl = document.getElementById("menu-" + meal.toLowerCase());
      if (!listEl) return;
      const items = dayData[meal] || [];
      if (items.length > 0) {
        listEl.innerHTML = items.map(i => `<li>${i}</li>`).join("");
      } else {
        listEl.innerHTML = `<li class="menu-empty">Menu not published yet</li>`;
      }
    });

    // Update displayed date
    const weekMeta = window.MESSMATE_WEEK_META || [];
    const meta = weekMeta.find(d => d.date === dateStr);
    const dateDisplayEl = document.getElementById("homeDisplayDate");
    if (meta && dateDisplayEl) {
      // Format nicely; fallback to dateStr
      try {
        const d = new Date(dateStr + "T00:00:00");
        dateDisplayEl.textContent = d.toLocaleDateString("en-IN", {
          weekday: "long", day: "numeric", month: "long", year: "numeric"
        });
      } catch (_) {
        dateDisplayEl.textContent = dateStr;
      }
    }

    // Update selected date in global
    window.MESSMATE_SELECTED = dateStr;

    // Update URL without reload (for bookmarking / back-button)
    const url = new URL(window.location.href);
    url.searchParams.set("date", dateStr);
    window.history.replaceState({}, "", url.toString());

    // Update spotlight if switching back to today
    highlightActiveMeal();
  };


  // ── 4. Meal Filter Pills ──────────────────────────────────────────────────
  window.filterMeal = function (filter) {
    const pills = document.querySelectorAll(".filter-pill");
    pills.forEach(p => p.classList.toggle("active", p.dataset.filter === filter));

    const cards = document.querySelectorAll(".meal-card");
    cards.forEach(card => {
      if (filter === "all" || card.dataset.meal === filter) {
        card.classList.remove("hidden-by-filter");
      } else {
        card.classList.add("hidden-by-filter");
      }
    });

    // Scroll to first visible card
    if (filter !== "all") {
      const target = document.querySelector(`.meal-card[data-meal="${filter}"]`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };


  // ── 5. Scroll-to-top Button ──────────────────────────────────────────────
  const scrollBtn = document.getElementById("scrollTopBtn");
  window.scrollToTop = function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  window.addEventListener("scroll", () => {
    if (!scrollBtn) return;
    if (window.scrollY > 300) {
      scrollBtn.classList.add("visible");
    } else {
      scrollBtn.classList.remove("visible");
    }
  }, { passive: true });


  // ── 6. Ticker Banner ─────────────────────────────────────────────────────
  const TICKER_ITEMS = [
    "🍽️ Mess opens at 7:30 AM for Breakfast",
    "📋 Rate your meal to help improve quality",
    "🌅 Breakfast: Idli, Sambar, Coconut Chutney",
    "✅ Anonymous ratings — no login required",
    "🍛 Lunch: 12:00 PM – 2:30 PM",
    "💬 Leave a suggestion on any meal card",
    "🌙 Dinner: 7:30 PM – 9:30 PM",
    "🏆 Your feedback shapes tomorrow's menu",
    "🔔 New menus published every morning",
    "👍 Good food? Give it a thumbs up!",
  ];

  const tickerContent = document.getElementById("tickerContent");
  if (tickerContent) {
    // Double the items to create seamless loop
    const allItems = [...TICKER_ITEMS, ...TICKER_ITEMS];
    tickerContent.innerHTML = allItems
      .map(t => `<span class="ticker-item">${t}</span>`)
      .join("");
  }


  // ── 7. Double-tap guard (original logic, preserved) ──────────────────────
  document.querySelectorAll(".rate-form").forEach(form => {
    const buttons = form.querySelectorAll(".rate-btn");
    let submitting = false;

    form.addEventListener("submit", (event) => {
      if (submitting) {
        event.preventDefault();
        return;
      }
      submitting = true;
      // CRITICAL: disable on a later tick, never synchronously here.
      // Each button is the form's submitter and carries name="rating";
      // disabling the submitter inside its own submit handler drops its
      // name/value from the payload, so the server sees no rating at all and
      // rejects every tap. The timeout lets serialization finish first.
      window.setTimeout(() => {
        buttons.forEach(btn => {
          btn.disabled = true;
          btn.classList.add("rate-btn-sending");
        });
      }, 0);
    });
  });


  // ── 8. Suggestion input focus (original logic, preserved) ────────────────
  document.querySelectorAll(".suggestion-details").forEach(details => {
    details.addEventListener("toggle", () => {
      if (details.open) {
        const input = details.querySelector(".suggestion-input");
        if (input) input.focus();
      }
    });
  });


  // ── 9. Clear ?rated= banner from URL ────────────────────────────────────
  if (window.history.replaceState && window.location.search.includes("rated=")) {
    const clean = window.location.pathname;
    window.setTimeout(() => window.history.replaceState({}, "", clean), 2500);
  }


  // ── 10. Auto-scroll active day tab into view ─────────────────────────────
  const activeTab = document.querySelector(".day-tab.active");
  if (activeTab) {
    activeTab.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }

});
