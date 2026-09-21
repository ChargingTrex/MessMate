/**
 * MessMate Student Home (home.js)
 * ---------------------------------
 * Progressive enhancement only. The reaction buttons are real submit buttons
 * carrying name="rating", so the page works with JavaScript switched off —
 * this file just stops a double tap sending two rows, and reveals the
 * suggestion box the moment someone looks like they want it.
 */

document.addEventListener("DOMContentLoaded", function () {

  document.querySelectorAll(".rate-form").forEach(form => {
    const buttons = form.querySelectorAll(".rate-btn");
    let submitting = false;

    form.addEventListener("submit", (event) => {
      // Block the second tap outright rather than relying on disabled buttons
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

  // A suggestion typed but never submitted is lost work, so opening the
  // details element keeps focus in the field ready to type.
  document.querySelectorAll(".suggestion-details").forEach(details => {
    details.addEventListener("toggle", () => {
      if (details.open) {
        const input = details.querySelector(".suggestion-input");
        if (input) input.focus();
      }
    });
  });

  // Clear the ?rated= banner from the URL so a refresh does not look like a
  // second successful submission
  if (window.history.replaceState && window.location.search.includes("rated=")) {
    const clean = window.location.pathname;
    window.setTimeout(() => window.history.replaceState({}, "", clean), 2500);
  }
});
