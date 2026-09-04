/**
 * MessMate Committee Rating Form (committee.js)
 * ----------------------------------------------
 * Emoji rating widget for the committee form.
 *
 * Extracted from the inline script in form.html rather than shared with it:
 * form.html is asserted against by tests/form_tests.robot, and leaving it
 * untouched keeps that suite green. Migrating the student form onto this file
 * is a clean follow-up.
 *
 * Unlike the student form — where per-item ratings are optional and only the
 * overall score gates submit — all five committee dimensions are required.
 */

document.addEventListener("DOMContentLoaded", function () {

  const form = document.getElementById("committeeForm");
  if (!form) return;

  const submitBtn = document.getElementById("submit-btn");
  const submitHint = document.getElementById("submit-hint");
  const groups = Array.from(document.querySelectorAll(".emoji-group[data-dimension]"));

  function refreshSubmitState() {
    const rated = groups.filter(group => {
      const input = document.getElementById(group.getAttribute("data-input"));
      return input && input.value !== "";
    }).length;

    const complete = rated === groups.length;
    submitBtn.disabled = !complete;

    if (submitHint) {
      submitHint.textContent = complete
        ? "Ready to submit"
        : `Rated ${rated} of ${groups.length} — rate all five areas to enable submit`;
    }
  }

  groups.forEach(group => {
    const input = document.getElementById(group.getAttribute("data-input"));
    const buttons = group.querySelectorAll(".emoji-btn");

    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");
        input.value = btn.getAttribute("data-value");
        refreshSubmitState();
      });
    });
  });

  // Character counter
  const review = document.getElementById("review");
  const counter = document.getElementById("char-counter");
  if (review && counter) {
    review.addEventListener("input", () => {
      counter.textContent = `${review.value.length} / 500`;
    });
  }

  // Prevent double submission
  form.addEventListener("submit", (e) => {
    if (submitBtn.disabled) {
      e.preventDefault();
      return;
    }
    submitBtn.textContent = "Submitting...";
    submitBtn.disabled = true;
  });

  refreshSubmitState();
});
