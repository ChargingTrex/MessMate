/**
 * MessMate Student Home (home.js)
 * ---------------------------------
 * Progressive enhancement: real-time clock, day switcher, active meal
 * detection, meal filter pills, ticker, scroll-to-top, and double-tap guard.
 * The reaction buttons remain real submit buttons so the page works without JS.
 *
 * The server decides what a card's reaction slot shows (rated / closed /
 * other day); this file only mirrors that decision when the clock moves or
 * the day switcher runs, so a student never taps a button the server would
 * refuse.
 */

document.addEventListener("DOMContentLoaded", function () {

  // Dish names come from the spreadsheet, which anyone with edit access can
  // type HTML into. Everything that reaches innerHTML goes through this.
  function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }
  const li = (text, cls) => `<li${cls ? ` class="${cls}"` : ""}>${esc(text)}</li>`;

  // A meal arrives as [{category, dishes: [...]}] (sheets.menu_groups). The
  // cards show the category beside its dishes; the spotlight only names dishes.
  function groupItem(group) {
    const dishes = esc((group.dishes || []).join(", "));
    return group.category
      ? `<li><span class="menu-cat">${esc(group.category)}</span> <span class="menu-dish">${dishes}</span></li>`
      : `<li>${dishes}</li>`;
  }
  const dishNames = groups => (groups || []).flatMap(g => g.dishes || []);

  // The spotlight is a glance, not the menu: the first few dishes, then a count
  const SPOTLIGHT_MAX = 6;
  function spotlightItems(groups) {
    const names = dishNames(groups);
    const shown = names.slice(0, SPOTLIGHT_MAX).map(d => li(d));
    if (names.length > SPOTLIGHT_MAX) shown.push(li(`+${names.length - SPOTLIGHT_MAX} more`, "specials-more"));
    return shown.join("");
  }

  // Same markup as the template's empty state: the lead line is test API,
  // the hint says what the student can do about it.
  function emptyItem(meal, isToday) {
    const hint = isToday
      ? `You can still rate ${esc(String(meal).toLowerCase())} after you eat.`
      : "Check back on the day.";
    return `<li class="menu-empty"><span class="menu-empty-lead">Menu not published yet</span>` +
           `<span class="menu-empty-hint">${hint}</span></li>`;
  }

  // ── 0. Serving windows → can this meal be rated right now? ────────────────
  // Mirrors sheets.MEAL_OPENS and app.config["ENFORCE_MEAL_WINDOWS"]. The
  // server is the authority; this keeps the buttons honest between reloads.
  function mealIsOpen(meal, start) {
    if (window.MESSMATE_ENFORCE_WINDOWS === false) return true;
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes() >= start;
  }

  function refreshRateSlots() {
    const isToday = window.MESSMATE_SELECTED === window.MESSMATE_TODAY_ISO;
    document.querySelectorAll(".rate-slot").forEach(slot => {
      const meal = slot.dataset.meal;
      slot.classList.toggle("is-other-day", !isToday);

      const form = slot.querySelector(".rate-form");
      if (!form) return;                       // already rated: nothing to toggle
      const dateField = form.querySelector('input[name="date"]');
      if (dateField) dateField.value = window.MESSMATE_SELECTED || window.MESSMATE_TODAY_ISO;

      const window_ = MEAL_WINDOWS[meal];
      const closed = isToday && window_ && !mealIsOpen(meal, window_[0]);
      form.querySelectorAll(".rate-btn").forEach(btn => {
        if (!btn.classList.contains("rate-btn-sending")) btn.disabled = closed;
      });
      const note = form.querySelector(".rate-note-closed");
      if (note) note.hidden = !closed;
    });
  }

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
  // Matches sheets.MEAL_TIMINGS, which the cards print:
  // Breakfast 07:30–09:30, Lunch 12:00–14:30, Dinner 19:30–21:30
  const MEAL_WINDOWS = {
    Breakfast: [7 * 60 + 30, 9 * 60 + 30],
    Lunch:     [12 * 60, 14 * 60 + 30],
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

    // Buttons follow the serving windows
    refreshRateSlots();
  }

  function updateSpotlight(activeMeal) {
    const widget = document.getElementById("specialsWidget");
    const meals = window.MESSMATE_MEALS || ["Breakfast", "Lunch", "Dinner"];
    const published = (window.MESSMATE_WEEK || {})[window.MESSMATE_TODAY_ISO] || {};
    const nothingToday = meals.every(m => !(published[m] || []).length);
    if (widget && !window.MESSMATE_IS_ADMIN) {
      // With no menu, the spotlight would only repeat the cards' empty state
      // in a bigger font. The cards already say it once each.
      widget.hidden = nothingToday;
    }

    const servingDot   = document.getElementById("servingDot");
    const servingLabel = document.getElementById("servingLabel");
    const mealName     = document.getElementById("activeMealName");
    const dishesList   = document.getElementById("activeMealDishes");

    const isToday = window.MESSMATE_SELECTED === window.MESSMATE_TODAY_ISO;
    const weekData = window.MESSMATE_WEEK || {};
    const todayData = weekData[window.MESSMATE_TODAY_ISO] || {};

    if (activeMeal && isToday) {
      if (servingDot) { servingDot.className = "serving-dot"; }
      if (servingLabel) servingLabel.textContent = "Serving now";
      if (mealName)    mealName.textContent = activeMeal;

      // Show dishes for active meal from today's menu
      const dishes = todayData[activeMeal] || [];
      if (dishesList) {
        if (dishes.length > 0) {
          dishesList.innerHTML = spotlightItems(dishes);
        } else {
          dishesList.innerHTML = `<li class="specials-loading">Menu not published yet. You can still rate it after you eat.</li>`;
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
        if (servingLabel) servingLabel.textContent = "Next meal";
        if (mealName)    mealName.textContent = nextMeal;
        const dishes = isToday ? (todayData[nextMeal] || []) : [];
        if (dishesList) {
          dishesList.innerHTML = dishes.length
            ? spotlightItems(dishes)
            : `<li class="specials-loading">Menu not published</li>`;
        }
      } else {
        if (servingLabel) servingLabel.textContent = "Meals done for today";
        if (mealName)    mealName.textContent = "See you at breakfast";
        if (dishesList)  dishesList.innerHTML = `<li class="specials-loading">Tomorrow's menu is under the next day's tab.</li>`;
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

    // Update active tab (class for the stylesheet, aria-pressed for the reader)
    document.querySelectorAll(".day-tab").forEach(tab => {
      const on = tab.dataset.date === dateStr;
      tab.classList.toggle("active", on);
      tab.setAttribute("aria-pressed", on ? "true" : "false");
    });

    // The title says which day is showing; "Today's Menu" only for today
    const titleEl = document.getElementById("homeTitle");
    if (titleEl) {
      let weekday = dateStr;
      try { weekday = new Date(dateStr + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long" }); } catch (_) {}
      titleEl.textContent = dateStr === window.MESSMATE_TODAY_ISO ? "Today's Menu 🍽️" : `${weekday}'s Menu 🍽️`;
    }

    // Update menu items inside each meal card
    meals.forEach(meal => {
      const listEl = document.getElementById("menu-" + meal.toLowerCase());
      if (!listEl) return;
      const items = dayData[meal] || [];
      listEl.classList.toggle("menu-items-categorised", items.some(g => g.category));
      if (items.length > 0) {
        listEl.innerHTML = items.map(groupItem).join("");
      } else {
        listEl.innerHTML = emptyItem(meal, dateStr === window.MESSMATE_TODAY_ISO);
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
    pills.forEach(p => {
      const on = p.dataset.filter === filter;
      p.classList.toggle("active", on);
      p.setAttribute("aria-pressed", on ? "true" : "false");
    });

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
  // Built from today's published menu and the real serving times, so it never
  // announces a dish the kitchen is not serving. Unpublished meals are skipped.
  const timings = window.MESSMATE_TIMINGS || {};
  const todayMenu = (window.MESSMATE_WEEK || {})[window.MESSMATE_TODAY_ISO] || {};
  const icons = { Breakfast: "🌅", Lunch: "🍛", Dinner: "🌙" };

  const TICKER_ITEMS = [];
  (window.MESSMATE_MEALS || ["Breakfast", "Lunch", "Dinner"]).forEach(meal => {
    const dishes = dishNames(todayMenu[meal]);
    const when = timings[meal] ? ` (${timings[meal]})` : "";
    if (dishes.length) {
      TICKER_ITEMS.push(`${icons[meal] || "🍽️"} ${meal}${when}: ${dishes.join(", ")}`);
    }
  });
  TICKER_ITEMS.push(
    "📋 Rate your meal to help improve quality",
    "✅ Anonymous ratings — no login required",
    "💬 Leave a suggestion on any meal card",
    "🏆 Your feedback shapes tomorrow's menu",
    "👍 Good food? Give it a thumbs up!"
  );

  // Pause control: moving text must be stoppable by touch and keyboard, not
  // only by hovering (WCAG 2.2.2). Pausing hides nothing.
  const tickerSection = document.getElementById("tickerSection");
  const tickerPause = document.getElementById("tickerPause");
  if (tickerSection && tickerPause) {
    tickerPause.addEventListener("click", () => {
      const paused = tickerSection.classList.toggle("is-paused");
      tickerPause.setAttribute("aria-pressed", paused ? "true" : "false");
      tickerPause.textContent = paused ? "Play" : "Pause";
    });
  }

  const tickerContent = document.getElementById("tickerContent");
  if (tickerContent) {
    // Double the items to create a seamless loop
    const allItems = [...TICKER_ITEMS, ...TICKER_ITEMS];
    tickerContent.innerHTML = allItems
      .map(t => `<span class="ticker-item">${esc(t)}</span>`)
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
      // The chosen answer keeps its colour; the other two step back.
      const chosen = event.submitter;
      if (chosen && chosen.classList.contains("rate-btn")) chosen.classList.add("rate-btn-chosen");
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
  // A reload must not re-announce an old result. The banner itself stays.
  if (window.history.replaceState && window.location.search.includes("rated=")) {
    const url = new URL(window.location.href);
    ["rated", "as", "meal"].forEach(k => url.searchParams.delete(k));
    window.setTimeout(() => window.history.replaceState({}, "", url.toString()), 2500);
  }


  // ── 10. Auto-scroll active day tab into view ─────────────────────────────
  const activeTab = document.querySelector(".day-tab.active");
  if (activeTab) {
    activeTab.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }

});
