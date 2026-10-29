/**
 * Menu editor enhancements (admin_menu.js)
 * -----------------------------------------
 * Everything here is optional: each day's form posts on its own without
 * JavaScript. With it, the page gains
 *
 *   1. unsaved-change tracking per day, and a leave-page warning;
 *   2. "Fill blanks from template" / "Use template" — the weekly template is
 *      already each field's placeholder, so filling copies it into the value;
 *   3. "Copy last week" — the previous week's stored menu, embedded by the
 *      template as window.MENU_PREV_WEEK, into every empty field;
 *   4. "Save all 7 days" — collects every field into the hidden week form
 *      (named <Meal>__<date>) and submits it as one request.
 *
 * Fill actions only ever touch EMPTY fields. Overwriting something an admin
 * typed, or something already published, would be a destructive surprise.
 */
(function () {
  const editor = document.getElementById("menu-editor");
  if (!editor) return;

  const fields = () => Array.from(editor.querySelectorAll("textarea[data-meal]"));
  const dirtyNote = document.getElementById("dirty-note");
  const saveWeek = document.getElementById("save-week");

  // Reveal the JS-only controls now that they can do something
  document.querySelectorAll("[data-js-only]").forEach(el => { el.hidden = false; });

  // ── 1. Dirty tracking ─────────────────────────────────────────────────────
  function dayOf(field) { return field.closest(".menu-day"); }

  function refreshDirty() {
    const days = new Set();
    fields().forEach(f => {
      const changed = f.value !== f.defaultValue;
      const day = dayOf(f);
      if (changed) days.add(day);
    });
    editor.querySelectorAll(".menu-day").forEach(day => {
      day.classList.toggle("is-dirty", days.has(day));
    });
    const n = days.size;
    if (dirtyNote) {
      dirtyNote.textContent = n ? `${n} day${n === 1 ? "" : "s"} with unsaved changes` : "";
    }
    if (saveWeek) saveWeek.classList.toggle("has-changes", n > 0);
    return n;
  }

  fields().forEach(f => f.addEventListener("input", refreshDirty));

  // A per-day submit saves only that day, so other dirty days would be lost
  // on the reload. Warn before the browser navigates.
  let submitting = false;
  editor.querySelectorAll("form[data-menu-day]").forEach(form => {
    form.addEventListener("submit", () => {
      const others = refreshDirty() - (form.closest(".menu-day").classList.contains("is-dirty") ? 1 : 0);
      if (others > 0 && !window.confirm(
          `${others} other day${others === 1 ? " has" : "s have"} unsaved changes that will be lost. Save just this day?`)) {
        return void event.preventDefault();
      }
      submitting = true;
    });
  });

  window.addEventListener("beforeunload", (event) => {
    if (!submitting && refreshDirty() > 0) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  // ── 2. Template fill ──────────────────────────────────────────────────────
  function setValue(field, value) {
    if (!value || field.value.trim()) return false;
    field.value = value;
    return true;
  }

  document.querySelectorAll("[data-fill-template]").forEach(btn => {
    btn.addEventListener("click", () => {
      const scope = btn.closest(".menu-day") || editor;
      let filled = 0;
      scope.querySelectorAll("textarea[data-meal]").forEach(f => {
        if (setValue(f, f.dataset.template)) filled++;
      });
      refreshDirty();
      flash(btn, filled ? `Filled ${filled}` : "Nothing empty");
    });
  });

  // ── 3. Copy last week ─────────────────────────────────────────────────────
  function shiftDate(iso, days) {
    const d = new Date(iso + "T00:00:00");
    d.setDate(d.getDate() + days);
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  const copyPrev = document.getElementById("copy-prev-week");
  if (copyPrev) {
    copyPrev.addEventListener("click", () => {
      const prev = window.MENU_PREV_WEEK || {};
      let filled = 0;
      fields().forEach(f => {
        const source = prev[shiftDate(f.dataset.date, -7)] || {};
        if (setValue(f, source[f.dataset.meal])) filled++;
      });
      refreshDirty();
      flash(copyPrev, filled ? `Copied ${filled}` : "Last week was empty");
    });
  }

  // ── 4. Save the whole week ────────────────────────────────────────────────
  const weekForm = document.getElementById("week-form");
  if (saveWeek && weekForm) {
    saveWeek.addEventListener("click", () => {
      weekForm.querySelectorAll("input[data-generated]").forEach(el => el.remove());
      fields().forEach(f => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = `${f.dataset.meal}__${f.dataset.date}`;
        input.value = f.value;
        input.dataset.generated = "1";
        weekForm.appendChild(input);
      });
      submitting = true;
      saveWeek.disabled = true;
      saveWeek.textContent = "Saving…";
      weekForm.submit();
    });
  }

  // ── Small confirmation on a button, then back to its label ───────────────
  function flash(btn, text) {
    const label = btn.dataset.label || (btn.dataset.label = btn.textContent);
    btn.textContent = text;
    window.setTimeout(() => { btn.textContent = label; }, 1600);
  }

  refreshDirty();
})();
