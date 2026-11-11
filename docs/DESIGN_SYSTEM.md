# MessMate Design System

One stylesheet (`static/style.css`), one visual language, every page. This
document is the contract: what the tokens are, which components exist, how a
page is assembled, and the rules that keep it coherent.

---

## 1. Principles

1. **Two themes, one system.** Every surface — student home, dish form,
   committee pages, admin console, dashboards — comes in two themes that
   share every token name: **dark**, the original glass shell, and **light**,
   *Ilai* (banana leaf, rice and the spice tin; reference sheet:
   `docs/ilai-design-system.html`). A component never asks which theme it is
   in; it reads tokens. A page that looks different from its neighbours in
   the same theme is a bug.
2. **Tokens, not values.** No hex colour, pixel size or easing appears below
   the token layer of the stylesheet. New needs get a new token.
3. **Components are page-agnostic.** A `.card` is a `.card` everywhere.
   Nothing is scoped to a body class; body classes only pick the rail width.
4. **Measurement, not decoration.** Colour on a number means something:
   red < 2.5, amber ≤ 3.5, green > 3.5 on a 1–5 score; 40 % / 70 % on a tap
   share. Absence (`--`) is grey and quiet, never a coloured zero.
5. **One focus ring.** Every interactive element gets `--focus-ring`. Nothing
   removes an outline without providing it.
6. **Test ids are API.** Ids, `data-*` attributes and the class names listed
   in each template's header comment are asserted by the Robot and Python
   suites. Rename nothing there without updating `tests/` and `test/`.

---

## 2. The global config: `ui_config.py`

Everything configurable about the UI is in one file, `ui_config.py`:

| What | Where it is read |
|---|---|
| `SHARED_TOKENS` — tokens both themes share (type sizes, space, radius, motion, rails) | served as `/ui/tokens.css`, loaded by every page before `style.css` |
| `THEMES` — the dark and light colour, font, shadow and chart values, one row per token with both values | same sheet: the starting theme on `:root`, the other under `:root[data-theme]`; `charts.js` reads chart colours from the computed style |
| `DEFAULT_THEME` — `"system"` (follow the device), `"dark"` or `"light"` | `tokens_css()` and `static/theme.js` |
| `FONTS_URL` — every web font either theme loads | `_theme_head.html` |
| `SCORE_BANDS` — where 1–5 turns red / amber / green | templates via `ui.score_class()`, `app.py` alerts via `ui_config.score_band()`, charts via `window.MESSMATE_UI.scoreBands` |
| `TAP_BANDS` — where "% liked" turns poor / mixed / good | templates via `ui.tap_band()` / `ui.tap_class()`, `app.py` alerts |
| `APP` — name, wordmark, tagline, institution | templates via `ui.app`, scripts via `window.MESSMATE_UI.app` |

Change a value there and it changes everywhere. `style.css` declares no
`:root` of its own.

**Switching themes.** `_theme_head.html` (in every `<head>`) loads the fonts
and the token sheet, and restores a saved choice before the page paints.
`_theme_toggle.html` is the switch in both headers; `static/theme.js` runs
it and saves the choice in `localStorage` (`THEME_STORAGE_KEY`). With no
saved choice and `DEFAULT_THEME = "system"`, the device's light / dark
setting decides. Dashboards reload on a switch so their charts redraw in the
new colours.

## 2a. Tokens (`SHARED_TOKENS` + `THEMES`)

The notes below describe the dark values. In light, surfaces are a leaf
tint over rice, text is mustard-seed ink and tamarind, the accent is banana
leaf, warnings are turmeric (darkened to read as text) and danger is
Kashmiri chilli. Headings use `--font-display` (Arima in light, the body
face in dark). Text on an accent fill is always `--on-accent`.

| Group | Tokens | Notes |
|---|---|---|
| Surfaces | `--bg-900/850/800`, `--app-gradient`, `--surface`, `--surface-hover`, `--surface-active`, `--surface-sunken`, `--chrome-bg` | Glass: translucent white over the gradient |
| Borders | `--border`, `--border-strong`, `--border-hover` | Three steps of white alpha |
| Text | `--text-strong`, `--text`, `--text-2`, `--text-3`, `--text-muted`, `--text-faint` | All pass WCAG AA on `--surface`; `--text-faint` is the floor (5.4:1) |
| Brand | `--brand-from`, `--brand-to`, `--brand-gradient` | The wordmark and the active filter pill |
| Accent | `--accent`, `--accent-strong`, `--accent-2`, `--accent-ink`, `--accent-bg`, `--accent-bg-hover`, `--accent-border`, `--accent-gradient` | `--accent-strong` is the one that carries white text |
| Semantic | `--ok*`, `--warn*`, `--danger*`, `--violet-*`, `--amber-tag*` | Each has text / bg / border variants; `--ok-glow` is the pulse ring |
| Type | `--font-sans`, `--font-mono`, `--fs-xs` … `--fs-xl`, `--fs-stat`, `--lh` | Base is 16 px; nothing user-facing goes below `--fs-xs` (11.8 px) |
| Space | `--sp-1` (4) … `--sp-8` (40) | 4 px grid |
| Rail | `--w-wide` 1200, `--w-mid` 900, `--w-narrow` 640, `--w-auth` 400, `--rail-pad` | Set per page via a body class |
| Radius | `--r-sm` 8, `--r-md` 12, `--r-lg` 16, `--r-xl` 20, `--r-pill` | Cards are `--r-lg`, controls `--r-sm`/`--r-md` |
| Elevation | `--shadow-card`, `--shadow-raised`, `--shadow-accent`, `--shadow-ok`, `--shadow-danger` | Offset + blur, never a zero-offset halo |
| Motion | `--dur` 180 ms, `--dur-slow` 240 ms, `--ease` | Honoured by `prefers-reduced-motion` |
| Other | `--focus-ring`, `--z-topbar`, `--z-float`, `--tap` 44 px | |
| Charts | `--score-red/amber/green`, `--chart-line`, `--chart-fill`, `--chart-grid`, `--chart-dim-1…5` | read by `charts.js`; `MessMateCharts.scoreColor()` applies the bands |

---

## 3. Page shells

Every page is:

```html
<head>{% set page_title = '…' %}{% include '_head.html' %}</head>
<body class="page-wide | page-mid | page-narrow | auth-body">
{% set active = 'overview' %}{% include '_topbar.html' %}
<main class="page">
  <div class="page-header">
    <div><p class="eyebrow">Section</p><h1>Title</h1><p>Supporting line</p></div>
    <div class="page-header-actions">…buttons…</div>
  </div>
  …
</main>
```

| Body class | Rail | Used by |
|---|---|---|
| `page-wide` | 1200 px | admin overview, menu editor, members, both dashboards |
| `page-mid` | 900 px | (available) |
| `home-body` | 900 px | student home — keeps its own header (`.home-header-bar`) and module styles by request, not `_topbar.html` |
| `page-narrow` | 640 px | dish form, thanks, committee login / password / review / thanks |
| `auth-body` | centred 400 px card | admin sign-in |

`admin-body`, `home-body` and `form-body` are kept as aliases of the first three.

`_topbar.html` renders one of three navigations from context: **admin**
(session), **token** (read-only `?token=` viewer), **public** (everyone else;
a signed-in committee member — pass `member` — also gets **Dashboard**).
Pass `is_admin` to the template and set `active` to one of
`overview · menu · members · students · committee · home · form`.

---

## 4. Components

### Surfaces
- `.card` — the glass panel. `.item-card` is a tighter variant for one field.
- `.card-head` — a title row with an action on the right (`h2` + `.table-action`).
- `.stat-card` — label `h3`, `.stat-value` (number) or `.stat-value-text`
  (a name), `.stat-note` (comparison, count, `sparkline()`). Colour bands:
  `.score-red` / `.score-amber` / `.score-green`; absence: `.is-empty`.
- `.chart-container` + `.canvas-wrapper` (300 px) — Chart.js reads the tokens
  through `static/charts.js`; the empty state is `MessMateCharts.empty()`.
- `.suggestions-container` + `.suggestions-list` — a bounded, keyboard-focusable
  scroll region of `.suggestion-item`s.
- `.empty-state` — dashed box with one sentence saying what would fill it.

### Buttons (one job each)
| Class | Job | Looks |
|---|---|---|
| `.submit-btn` | the primary action of a form or page | gradient, full width in forms; `.btn-inline` for a header |
| `.detail-link`, `.nav-cta` | a primary action that is a link | same gradient, inline |
| `.btn-secondary` | Save / Sign out / Copy / Prev / Next | bordered |
| `.table-action` | a per-row or per-card action | quiet until hovered; `.danger` |
| `.link-btn` | an inline text action (member sign-out) | accent text |
| `.nav-link` | navigation | borderless; `aria-current="page"` |
| `.segmented` > `.segmented-btn` | one control with parts (7 d / 30 d) | `aria-pressed` + `.active` |
| `.filter-pill` | one-of-many filter | pill; `.active` is gradient |
| `.day-tab` | date scroller | `.active`, `.day-today-badge` |
| `.rate-btn` | good / bad / skip | `.rate-good` / `.rate-bad` / `.rate-skip` |
| `.emoji-btn` | 1–5 rating | `.selected`; inside `.emoji-group`, `.small-group` |

### Inputs
`.suggestion-input`, `.dropdown`, `select`, `textarea`, `.menu-input` share one
style: sunken surface, 48 px minimum, 16 px text, accent focus. Labels are
`.item-label`; hints `.sub-label` / `.char-counter`; spacing `.field-gap`;
the submit row `.form-actions` (or `.submit-container` in long forms).

### Badges and tags
`.badge-active` / `.badge-ok`, `.badge-inactive`, `.badge-pending`;
`.feed-tag.tone-student|tap|committee`; `.count-pill` (`.is-clear`);
`.meal-active-badge`, `.day-today-badge`, `.specials-admin-tag`.

### Alerts
`.alert.error` / `.alert.success` (centred, in a form) and `.alert-home`
(left-aligned banner). `.notice-box` for an informational paragraph.
`.attention-card` > `.alert-list` > `.alert-item.level-danger|warn|info`.

### Lists and bars
- Chips: `.chip-list` (admin), `.menu-items` (home), `.specials-dishes`
  (spotlight) — same pill; `.chip-empty` / `.menu-empty` for "not published".
- `.tap-row` > `.tap-bar` > `.tap-fill.good|bad|skip` + `.tap-legend`.
- `.result-row` bars on the home spotlight (same fills).
- `.attendance-list` with `.att-mark` / `.att-state`; `.is-done` rows.
- `.feed-list` > `.feed-item` (`.feed-tag`, `.feed-text`, `.feed-when`).
- `.members-table`, `.credential-table`, `.week-grid` (`.pub-dot.on|off`).

### Macros (`templates/_macros.html`)
`score_class(score)`, `sparkline(series, key, label)`, `chips(items, empty_text)`.

---

## 5. Modules

- **Student home** (preserved verbatim from before the system, by request):
  `.home-header-bar` with `.home-nav-link` / `.home-nav-cta`, `.ticker-section`,
  `.day-tab`, `.filter-pill`, `.specials-container` (`.specials-left` /
  `.specials-right`), `.meal-card` (`.active-meal`, `.hidden-by-filter`),
  `.menu-items`, `.rate-btn`, `.suggestion-details`, `.detail-cta`,
  `.scroll-top-btn`. Scoped to `body.home-body` where it overrides a
  component; it reads the same tokens.
- **Menu editor**: `.week-nav`, `.menu-toolbar`, `.menu-grid` > `.menu-day`
  (`.menu-day-today`, `.menu-day-past`, `.menu-day-saved`, `.is-dirty`),
  `.menu-field` with `.meal-status.on|off`, `.menu-day-actions`.
- **Sign in (front door)**: `.signin-layout` (brand panel + main),
  `.signin-brand` / `.signin-wordmark` / `.signin-features`, `.signin-card`,
  `.pilot-list` > `.pilot-card` (`.pilot-avatar.tone-student|member|viewer|admin`,
  `.pilot-role`, `.pilot-email`, `.pilot-caption`, `.pilot-chevron`; `.is-picked`),
  `.pilot-note`. Pilot cards render only in `PILOT_MODE`.
- **Auth**: `.auth-card`, `.auth-brand` (the per-role admin sign-in).
- **Member + thanks**: `.member-bar`, `.thanks-container` (`.thanks-icon`,
  `.thanks-actions`).

---

## 6. Adding a page

1. Copy the shell from §3 and pick the rail width.
2. Pass `is_admin` (and `active`) from the route.
3. Build from §4 components. If a new component is needed, add it to §3 of
   the stylesheet with tokens only, and list it here.
4. Put the ids/classes the tests will use in the template's header comment.
5. Run `python test/test_smoke.py` and the Robot suites (see CONTRIBUTING.md).

---

## 7. Accessibility checklist

- 16 px base, nothing below `--fs-xs`; tap targets ≥ 44 px (`--tap`).
- Every control has a visible focus ring; every icon-only control has an
  `aria-label`; charts have `role="img"` with a text alternative.
- The ticker pauses on hover and focus and stops under reduced motion.
- Colour never carries meaning alone: bands are paired with the number,
  publication dots with visually-hidden text.
