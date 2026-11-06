# MessMate — WCAG 2.2 Accessibility Audit

**Audited** 2026-10-05 · **Scope** 7 pages on a local instance (`127.0.0.1:5055`)
at commit `bcc3580` · **Standard** WCAG 2.2, Level A + AA (55 criteria)

---

## Conformance verdict (normative)

> **Does not conform to WCAG 2.2 Level AA.**
> Failing: **1.1.1, 1.3.1, 1.4.3, 1.4.10, 2.2.2, 3.3.2, 4.1.2** — 7 of the 55
> Level A/AA criteria.
>
> Four of the seven are **Level A**, which means the pages do not currently meet
> Level A either.

This is a findings report, not a conformance claim. A claim is yours to make and
carries legal weight.

## Audit score (informative — not a conformance claim)

**70 / 100 · Grade B** — AA with minor gaps. Weighted as follows:

| Weight | Surface | Scored | Why |
|---:|---|---:|---|
| 30 | Blocking failures | 19 | 4 chart canvases + 2 form controls have no accessible name. Keyboard reachability, focus indicators and flash safety all pass. |
| 20 | Colour & contrast | 17 | 16 of 19 applicable text/background pairs pass AA (84%). |
| 15 | Typography | 13 | No size-floor violations; survives the 1.4.12 spacing override on all 7 pages; type sizes are ad-hoc rather than a coherent scale. |
| 10 | Targets & pointer | 10 | 94 targets measured, none below the 24px floor. |
| 10 | Motion | 5 | Flash-safe and `prefers-reduced-motion` is honoured, but the ticker has no pause control. |
| 10 | Infographics & media | 3 | All four chart canvases lack a text alternative. |
| 5 | AAA headroom | 3 | Reduced-motion support earns credit; 7:1 contrast and 44px targets do not. |

The score is a progress signal for the team between sprints. Conformance is the
pass/fail verdict above; the two are not interchangeable.

---

## How this was measured

**Tooling note, stated up front:** the `wcag-audit` skill synced without its
`scripts/` and `references/` directories, so `a11y_math.py`, `audit_page.py` and
`build_dashboard.py` were unavailable. There is also no axe-core, Playwright or
Node on this machine. The WCAG arithmetic was therefore reimplemented from the
normative formulas and **self-tested against published reference values before
use** — 27/27 checks pass, including the canonical boundary greys
(`#767676` on white = 4.54:1, `#595959` on white = 7.00:1, black on white =
21.00:1). Every number below is reproducible from those formulas.

| Status | Meaning in this report |
|---|---|
| **Measured** | Read from the browser's own computed styles or geometry via Selenium/Chrome 154. |
| **Inferred** | Read from source; the runtime behaviour follows but was not observed directly. |
| **Not tested** | Requires a screen reader or disabled users. Stated, never guessed. |

Pages covered: `/`, `/home`, `/dashboard`, `/dashboard/committee`,
`/admin/login`, `/committee/login`, `/thanks`.

**Manual passes performed:** full keyboard traversal with real `Tab` dispatch;
reflow at a true 320 CSS px; the 1.4.12 text-spacing override; a
`prefers-reduced-motion` pass; colour-independence and label review from source.

**Three measurement errors were found and corrected during the audit** — they
are recorded here because they would each have produced a false finding:

1. Headless Chrome refuses to size its window below ~500 CSS px, so the first
   reflow pass silently measured 500px and reported a **false pass**. Redone
   with `Emulation.setDeviceMetricsOverride`, which is not subject to that floor.
2. Flagging `animation-name != none` under reduced motion produced 4 **false
   failures** on `/home`. The guard zeroes duration and iteration count, so the
   name survives while the motion does not. Re-measured as duration × iterations.
3. A focus probe reading computed styles immediately after `.focus()` returned
   pre-transition values (`transition: border-color 0.2s`), making every border
   look unchanged. Re-measured after the transition settles.

**Two apparent failures were investigated and dismissed:**

- `/home`'s three suggestion inputs are unreachable by `Tab` — because they sit
  inside a closed `<details>` disclosure ([home.html:223](templates/home.html#L223)).
  The `<summary>` is reachable and the input becomes focusable when opened. This
  is a correct pattern, not a defect.
- `button#submit-btn` on `/` measures 1.91:1, but it is `disabled` on load
  ([form.html:204](templates/form.html#L204)) and SC 1.4.3 exempts inactive
  components. Retained as advisory only.

**Not tested:** screen-reader output (NVDA/JAWS/VoiceOver), so 4.1.2 is assessed
from accessible names in the DOM rather than from what a screen reader announces.
1.2.x is not applicable — no audio or video. Cognitive-load and real-user
testing are out of scope for an automated-plus-manual pass.

---

## Failures

### 1 — Chart canvases have no text alternative
**SC 1.1.1 Non-text Content · Level A · Critical · Measured**

All four `<canvas>` elements carry no `role`, no `aria-label` and no fallback
content, so every number in the dashboards is unavailable to a screen-reader
user. The dashboards are the entire value of the admin surface.

| Where | Element |
|---|---|
| [dashboard.html:105](templates/dashboard.html#L105) | `<canvas id="trendChart">` |
| [dashboard.html:113](templates/dashboard.html#L113) | `<canvas id="itemChart">` |
| [committee_dashboard.html:95](templates/committee_dashboard.html#L95) | `<canvas id="dimensionChart">` |
| [committee_dashboard.html:108](templates/committee_dashboard.html#L108) | `<canvas id="committeeTrendChart">` |

Measured: `aria_label: ""`, `role: ""`, no caption, on each.

**Fix.** A chart needs a summary that carries its *finding*, not its type.
"Chart" fails 1.1.1; the sentence below passes. The figures are already in the
Jinja context, so the alternative can be generated rather than hand-written:

```html
<!-- dashboard.html — replace line 105 -->
<canvas id="trendChart" role="img"
        aria-label="Line chart: average daily rating over {{ trend_data|length }} days,
                    from {{ trend_data[0].Avg_Overall }} on {{ trend_data[0].Date }}
                    to {{ trend_data[-1].Avg_Overall }} on {{ trend_data[-1].Date }}."></canvas>

<!-- and give the same data as a table, visually hidden but available to AT -->
<table class="visually-hidden">
  <caption>Average daily rating, last {{ trend_data|length }} days</caption>
  <thead><tr><th scope="col">Date</th><th scope="col">Average</th><th scope="col">Responses</th></tr></thead>
  <tbody>
    {% for row in trend_data %}
    <tr><th scope="row">{{ row.Date }}</th><td>{{ row.Avg_Overall }}</td><td>{{ row.Response_Count }}</td></tr>
    {% endfor %}
  </tbody>
</table>
```

```css
/* style.css — a correct visually-hidden utility; `display:none` would hide it
   from assistive tech too, which defeats the purpose */
.visually-hidden {
    position: absolute; width: 1px; height: 1px;
    margin: -1px; padding: 0; border: 0;
    clip-path: inset(50%); overflow: hidden; white-space: nowrap;
}
```

---

### 2 — Two form controls have no programmatic label
**SC 1.3.1 (A), 3.3.2 (A), 4.1.2 (A) · Critical · Measured**

On `/`, the review textarea and the suggestion input have a `placeholder` and
nothing else — no `<label>`, no `aria-label`. A placeholder is not an accessible
name, and it disappears as soon as the user types, so it also fails as an
instruction.

| Where | Control | Measured |
|---|---|---|
| [form.html:192](templates/form.html#L192) | `textarea#review` | `labelled: false` |
| [form.html:199](templates/form.html#L199) | `input[name=suggestion]` | `labelled: false` |

Every other control across all seven pages is correctly labelled — `/home`
already does this well, using `aria-label="Suggestion for Breakfast (optional)"`
on the equivalent input. The fix is to match the pattern the project already uses.

```html
<!-- form.html:192 -->
<label for="review" class="field-label">
  Comments about today's lunch <span class="subtext">(optional)</span>
</label>
<textarea name="review" id="review" maxlength="150"
          aria-describedby="char-counter"
          placeholder="Any comments about today's lunch?"></textarea>

<!-- form.html:199 -->
<label for="suggestion" class="field-label">
  Suggest a dish <span class="subtext">(optional)</span>
</label>
<input type="text" name="suggestion" id="suggestion" class="suggestion-input"
       placeholder="Suggest a dish for the mess menu...">
```

`aria-describedby="char-counter"` additionally ties the live "0 / 150" counter to
the textarea, so a screen-reader user hears the remaining budget.

---

### 3 — Three text/background pairs below 4.5:1
**SC 1.4.3 Contrast (Minimum) · Level AA · Serious · Measured**

19 applicable text/background/size/weight combinations were measured from
computed styles; 16 pass. Replacement values come from a golden-section search
over lightness holding hue and saturation, so brand colour stays recognisable —
each is the *smallest* change that clears the threshold.

| Measured | Need | Pair | Size | Where | Replacement |
|---:|---:|---|---|---|---|
| **3.54:1** | 4.5 | `#888888` on `#ffffff` | 12.8px | `div#char-counter` on `/` | **`#767676`** → 4.54:1 (lightness −6.9%) |
| **4.25:1** | 4.5 | `#777777` on `#f7f9fc` | 14.4px | `.subtext`, `.subtext-line` on `/` | **`#727272`** → 4.56:1 (−1.8%) |
| **4.48:1** | 4.5 | `#777777` on `#ffffff` | 14.4px | `.subtext` on `/`, `/committee/login` | **`#767676`** → 4.54:1 (−0.2%) |

The last two are the same token failing on two different grounds. One token
change fixes both, and `#727272` clears the threshold on `#ffffff` as well
(4.78:1), so a single value covers every case:

```css
/* style.css — one replacement for both subtext failures */
:root {
    --text-muted: #727272;   /* was #777777: 4.25:1 on #f7f9fc, below the 4.5 floor */
}
.subtext, .subtext-line { color: var(--text-muted); }

/* the character counter, measured at 3.54:1 */
.char-counter { color: #767676; }   /* was #888888 */
```

Verify with the formula rather than by eye:

```js
const lum = hex => {
  const c = [1,3,5].map(i => parseInt(hex.substr(i,2),16)/255)
    .map(v => v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4));
  return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2];
};
const ratio = (a,b) => {
  const [x,y] = [lum(a), lum(b)].sort((m,n) => n-m);
  return (x + 0.05) / (y + 0.05);
};
ratio('#727272', '#f7f9fc');   // 4.56  — passes the 4.5 floor
```

---

### 4 — Horizontal scrolling at 320 CSS px
**SC 1.4.10 Reflow · Level AA · Serious · Measured**

Measured at a true 320px viewport via CDP (the window-size route cannot go below
~500px and gives a false pass).

| Page | Viewport | Content width | Verdict |
|---|---:|---:|---|
| `/home` | 320 | **351** | fail — 31px overflow |
| `/dashboard` | 320 | **341** | fail — 21px overflow |
| `/dashboard/committee` | 320 | **341** | fail — 21px overflow |
| `/`, `/admin/login`, `/committee/login`, `/thanks` | 320 | 320 | pass |

Causes, measured per element:

- **`/home`** — `div#tickerContent` is **6678px** wide, and `nav.home-nav`
  reaches `right: 351px`.
- **both dashboards** — `nav.app-topbar-nav` reaches `right: 341px`; the
  `.nav-link` for "Committee" is the trailing element.

At 256px (≈400% zoom on a 1024px screen, also required by 1.4.10) `/` fails too,
at 299px, from the `.emoji-btn` row.

```css
/* style.css — the ticker must be clipped by its own section, not by the page */
.ticker-section { overflow: hidden; max-width: 100%; }
.ticker-track   { overflow: hidden; }

/* the top bars should wrap rather than push the page wider */
@media (max-width: 420px) {
    .app-topbar-nav, .home-nav {
        flex-wrap: wrap;
        row-gap: 6px;
        max-width: 100%;
    }
    .app-topbar-inner { flex-wrap: wrap; height: auto; padding-block: 8px; }
    .emoji-row { flex-wrap: wrap; justify-content: center; }
}
```

---

### 5 — Scrolling ticker cannot be paused
**SC 2.2.2 Pause, Stop, Hide · Level A · Serious · Measured**

`div#tickerContent` runs the `tickerScroll` animation for **38s, infinite**,
starts automatically, and sits alongside other content. 2.2.2 requires a
mechanism to pause, stop or hide any motion that runs longer than 5s.

The `prefers-reduced-motion` guard at [style.css:2172](static/style.css#L2172)
is good and genuinely works (measured: 0 effectively-moving animations under
the OS setting), but it does **not** satisfy 2.2.2 — the criterion requires a
*control the user can operate*, not only an OS preference. Measured animations:

| Page | Selector | Animation | Duration | Iterations |
|---|---|---|---:|---|
| `/home` | `div#tickerContent` | `tickerScroll` | 38s | infinite |
| `/home` | `span#badge-breakfast`, `#badge-lunch` | `servingGlow` | 2.5s | infinite |
| `/home`, both dashboards, `/admin/login` | `span.live-dot` | `livePulse` | 2s | infinite |

Only the ticker exceeds 5s, so only the ticker needs the control.

```html
<!-- home.html — inside #tickerSection, before .ticker-track -->
<button type="button" id="tickerToggle" class="ticker-toggle"
        aria-pressed="false" aria-controls="tickerContent">
  Pause scrolling announcements
</button>
```

```js
/* home.js */
const toggle = document.getElementById("tickerToggle");
const content = document.getElementById("tickerContent");
if (toggle && content) {
  toggle.addEventListener("click", () => {
    const paused = content.style.animationPlayState === "paused";
    content.style.animationPlayState = paused ? "running" : "paused";
    toggle.setAttribute("aria-pressed", String(!paused));
    toggle.textContent = paused ? "Pause scrolling announcements"
                                : "Resume scrolling announcements";
  });
}
```

```css
/* style.css — 24px floor per 2.5.8, and visible focus */
.ticker-toggle {
    min-height: 24px; padding: 4px 10px;
    font-size: 0.78rem; border-radius: var(--r-pill);
    background: transparent; border: 1px solid var(--border-strong);
    color: var(--text-2); cursor: pointer;
}
.ticker-toggle:focus-visible { outline: none; box-shadow: var(--focus-ring); }
```

---

## Passing, with evidence

These were tested and pass. Recorded so the next audit does not re-litigate them.

| Criterion | Level | Evidence |
|---|---|---|
| **1.4.12** Text Spacing | AA | The override (line-height 1.5, letter-spacing 0.12em, word-spacing 0.16em, paragraph 2em) clips **0 containers across all 7 pages**. |
| **2.1.1** Keyboard | A | Every focusable element reached by real `Tab` on all 7 pages. The only two exceptions are correct: a `disabled` submit button and inputs inside a closed `<details>`. |
| **2.1.2** No Keyboard Trap | A | Focus cycles through `BODY` and wraps on every page; no trap. |
| **2.4.7** Focus Visible | AA | Every focused control shows an indicator. Pages with `body.admin-body` / `body.auth-body` get the `--focus-ring` box-shadow; others get a border-colour change measured at 3.57:1 state change. |
| **2.5.8** Target Size (Minimum) | AA | 94 targets measured; **none** below the 24px floor. The one 17px-tall element is an inline text link, which the criterion exempts. |
| **2.3.1** Three Flashes | A | No flashing content; fastest animation is a 2s pulse. |
| **3.1.1** Language of Page | A | `lang="en"` on all 7 pages. |
| **2.4.2** Page Titled | A | All 7 pages have unique, descriptive titles. |
| **2.4.1** Bypass Blocks | A | No skip link, but `<main>` landmarks plus `h1`/`h2` structure satisfy the criterion via technique H69. A skip link is still recommended below. |
| **2.3.3** Animation from Interactions | **AAA** | `prefers-reduced-motion` honoured: **0** effectively-moving animations measured under the OS setting. |

---

## Route to the highest achievable rating

### Tier 1 — Unblock → reaches Level A
| # | Fix | Criterion | Effort |
|---|---|---|---|
| 1 | Name the 4 chart canvases + add hidden data tables | 1.1.1 | ~2h |
| 2 | Label `textarea#review` and `input[name=suggestion]` | 1.3.1, 3.3.2, 4.1.2 | ~15min |
| 5 | Add the ticker pause control | 2.2.2 | ~45min |

### Tier 2 — Conform → reaches Level AA
| # | Fix | Criterion | Effort |
|---|---|---|---|
| 3 | `--text-muted: #727272`, `.char-counter: #767676` | 1.4.3 | ~10min |
| 4 | Clip the ticker; wrap both top bars under 420px | 1.4.10 | ~1h |

**Total to Level AA: roughly half a day.** Four of the five fixes are small and
localised; only the chart alternatives need real thought, because a useful
alternative has to carry the finding rather than describe the picture.

### Tier 3 — Harden → "AA + AAA where achievable"
This is the honest ceiling. Blanket AAA is not attainable and W3C says so.

| Fix | Criterion | Note |
|---|---|---|
| Give `.suggestion-input` / `textarea` the focus ring on **every** page, not only `admin-body`/`auth-body` | 2.4.13 Focus Appearance | The ring block at [style.css:2135](static/style.css#L2135) is body-class-scoped; [form.html:25](templates/form.html#L25), [committee_login.html:16](templates/committee_login.html#L16), [committee_form.html:21](templates/committee_form.html#L21) and [thanks.html:17](templates/thanks.html#L17) carry **no body class**. `#email` on `/committee/login` measures **2.77:1** state change, below the 3:1 that 2.4.13 wants, and a 1px border also misses its 2px-perimeter area requirement. Dropping the `body.admin-body` / `body.auth-body` qualifiers fixes all four pages at once. |
| Raise body text to 7:1 | 1.4.6 Contrast (Enhanced) | 11 of 20 pairs already pass. The gaps: `#ffffff` on `#2e75b6` (4.84:1), `#ffffff` on `#2563eb` (5.17:1), `#666666` on white (5.74:1). Darkening `--blue-600` to `#1d5a93` takes white-on-blue to 7.04:1. |
| Grow targets to 44px | 2.5.5 Target Size | 17 of 94 targets sit below 44px. The φ ladder from the 24px floor is **24 → 39 → 63**; 39px suits the dashboard's `.segmented-btn` (currently 31.2px) and keeps the toolbar's rhythm. |
| Add a skip link | 2.4.1 | Already passes via H69, but a skip link is cheap and helps keyboard users on the dashboards. |
| Associate form errors with their fields | 3.3.1, 3.3.3 | Error banners at [form.html:33](templates/form.html#L33), [admin_login.html:22](templates/admin_login.html#L22), [committee_login.html:24](templates/committee_login.html#L24) are plain `<div>`s. Adding `role="alert"`, plus `aria-invalid` and `aria-describedby` on the offending field, and moving focus to the banner, would strengthen error recovery. *Inferred from source; not exercised against a live validation failure.* |

---

## Reproducing this audit

```bash
# WCAG arithmetic — verify the formulas before trusting any number
python3 a11y_math.py selftest                          # 27/27 expected
python3 a11y_math.py contrast "#777777" "#f7f9fc" --size 14.4
python3 a11y_math.py fix "#777777" "#f7f9fc" --size 14.4 --level AA
python3 a11y_math.py target --w 31.2 --h 31.2 --spacing 8

# Evidence collection (needs the app running on :5055)
python3 collect.py        # computed styles, targets, labels, semantics
python3 reflow.py         # 1.4.10 at a true 320px and 256px via CDP
python3 keyboard.py       # full Tab traversal, indicators, order
python3 focusdelta.py     # 2.4.13 focus-state contrast
```

Scripts live in the audit scratchpad, not the repo. The dashboard token is read
from `.env` at runtime and redacted from every artefact written to disk — an
audit file gets shared, and a live credential must not travel with it.
