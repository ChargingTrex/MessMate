# MessMate — Changelog

All changes to the MessMate codebase are logged here in reverse chronological 
order (newest at top). Before making any change, scroll to the bottom, copy 
the template, fill it in, and move it to the top.

## Legend
| Symbol | Meaning |
|---|---|
| ✅ Working | Tested and confirmed working |
| ⚠️ Needs Testing | Changed but not yet fully verified |
| ❌ Broke Something | This change caused a regression |

| Type | Meaning |
|---|---|
| Feature | New functionality added |
| Bug Fix | Something broken was fixed |
| Config | Environment, deployment, or settings change |
| Refactor | Code restructured, behaviour unchanged |
| Hotfix | Emergency fix for a live issue |

---

## [2026-09-24 09:00] — Sheet Schema Templates (template.csv)

**Files changed:** `template.csv` (new), `sheet_templates/*.csv` (new), `sheets.py`, `manage_committee.py`, `test/fake_sheets.py`, `test/test_smoke.py`, `README.md`, `CONTRIBUTING.md`
**Type:** Feature
**Status:** ✅ Working

### What changed
Added the full Google Sheet schema as CSV templates, so setting up a spreadsheet no longer means hand-typing 54 column headers from prose.

- `template.csv` — one row per column across all six tabs: tab name, column, target cell, the Sheets format it needs, and the notes that matter.
- `sheet_templates/<tab>.csv` — six header-only files. File > Import > Insert new sheet(s) creates each tab with the right columns and no rows to delete.

### Why
The schema was documented in three places — README prose, CONTRIBUTING, and `test/fake_sheets.py` — all hand-copied. Anyone setting up a new sheet had to transcribe headers exactly, and `get_all_records()` maps row 1 to dict keys, so a single typo silently breaks every lookup.

### Details
- Both files are generated from a new `sheets.SHEET_TEMPLATES` registry by `python manage_committee.py sheet-template`, so the repo's schema cannot drift from the code that reads the sheet.
- `test/test_smoke.py` regenerates into a temp directory and compares, failing if the committed files go stale. Verified the check actually fails when drift is injected, rather than passing vacuously.
- Added `sheets.RESPONSE_HEADERS` and `sheets.SUMMARY_HEADERS`, documenting the column order of the two original student tabs. Documentation-only: `append_response()` and `update_daily_summary_for_today()` still build rows positionally, so no write path changed.
- `test/fake_sheets.py` now imports those constants instead of keeping its own copies. The journey suites assert on column positions, so their assertions now validate the constants too — three hand-copied lists became one source.
- Date-shaped columns are flagged as needing Plain Text formatting, which is the trap that forced the six-format fallback parser in `get_today_responses()`.

### Tests
All five credential-free suites pass: smoke 35 checks across 19 features, committee checklist 59, and the committee/student/home journeys at 64/53/51 steps. `app.py`, templates and static files are untouched.

### How to revert
Delete `template.csv` and `sheet_templates/`. Remove the "Sheet template registry" block and the two header constants from `sheets.py`, the sheet-template command from `manage_committee.py`, and the "sheet templates" feature from `test/test_smoke.py`. Restore the inline header lists in `test/fake_sheets.py`.

---

## [2026-09-20 19:40] — Student Home: Daily Menu & Quick Meal Ratings

**Files changed:** `app.py`, `sheets.py`, `templates/home.html` (new), `templates/admin_menu.html` (new), `static/home.js` (new), `static/style.css`, `test/fake_sheets.py`, `test/fake_server.py`, `test/test_smoke.py`, `test/test_e2e_home.py` (new), `tests/home_tests.robot` (new), `.github/workflows/messmate_tests.yml`, `README.md`, `CONTRIBUTING.md` (new)
**Type:** Feature
**Status:** ✅ Working

### What changed
Added a student home page at `/home` showing today's breakfast, lunch and dinner with a one-tap reaction per meal — good, bad or skipped — and an optional suggestion. Added a menu editor at `/admin/menu` so the week can be published without opening the spreadsheet.

### Why
The per-dish form asks for eleven decisions. Most students will not stop for that, so the feedback that arrives skews toward people with a complaint. One tap per meal is cheap enough that ordinary days get recorded too. Showing the menu also gives students a reason to open the page before they have an opinion.

### Details
- **Two new tabs:** `menu` (Date, Breakfast, Lunch, Dinner) and `meal_ratings` (Timestamp, Date, Meal, Rating, Suggestion). Both store Date as plain text.
- **Two editors, neither authoritative:** mess staff can type into the `menu` tab, or use `/admin/menu`. Both call `save_menu_for_date()`, which upserts by date — hence Date must stay in column A.
- **Skips are counted but excluded from the score.** A meal's score is `good` as a share of those who actually ate; a student who never turned up is reporting attendance, not food quality. A meal everyone skipped scores 0 rather than dividing by zero.
- **Three taps per IP per day**, matching three meals, against one per day for the per-dish form. A student who ate breakfast and dinner has two separate things to say.
- **Kept separate from the other two layers.** Quick reactions never reach the per-dish dashboard or the committee dashboard, and never enter a 1-5 average. `/` is untouched, so printed QR codes still land on the per-dish form.
- **Unpublished days say "Menu not published yet"** rather than rendering an empty card, which would read as "the mess is closed".

### Bugs fixed, both found only by the browser suite
The Python journey suites POST fields directly and so could not see either:
- **A hidden `<input name="rating">` alongside submit buttons of the same name.** A browser sends both, the empty hidden one first, so `request.form.get("rating")` read empty and *every* tap was rejected as no choice. The feature would have shipped completely non-functional.
- **Disabling the submit button inside its own `submit` handler.** Each button is the form's submitter carrying `name="rating"`; disabling it there drops its name/value from the payload. Fixed by deferring the disable to a later tick and guarding repeat submits with a flag.

### Tests
`test/test_e2e_home.py` — 51 steps across 7 journeys. `tests/home_tests.robot` — 20 browser tests (TC180–TC199). Smoke extended to 34 checks across 18 features. Full sweep: 125 browser tests, 0 failed; 5 credential-free Python suites, all passing.

### How to revert
Delete `templates/home.html`, `templates/admin_menu.html`, `static/home.js`, `test/test_e2e_home.py`, `tests/home_tests.robot`. Remove the "STUDENT HOME" route block from `app.py` and the "Daily menu and quick meal ratings" block from `sheets.py`. Revert the appended block in `static/style.css` and the menu seeding in `test/fake_server.py`.

---

## [2026-09-04 16:00] — Food Committee Test Suites (E2E + Robot UI)

**Files changed:** `test/fake_sheets.py` (new), `test/fake_server.py` (new), `test/test_e2e_committee.py` (new), `test/test_committee.py`, `tests/committee_api_tests.robot` (new), `tests/committee_form_tests.robot` (new), `tests/committee_admin_tests.robot` (new), `tests/committee_dashboard_tests.robot` (new), `tests/resources/committee_keywords.resource`, `tests/resources/common.resource`, `tests/run_tests.sh`, `sheets.py`, `.github/workflows/messmate_tests.yml`, `TESTING.md`
**Type:** Feature
**Status:** ✅ Working

### What changed
Added a full end-to-end journey suite and four Robot Framework suites covering the Food Committee UI, all runnable without Google credentials. Fixed one real bug they exposed.

### Why
The checklist harness verified behaviours one at a time. It could not catch faults that only appear across a whole journey — a member who can sign in but whose review never reaches the dashboard, or a rotation that silently erases the outgoing term's history — and it exercised no browser at all.

### Details
- **`test/fake_sheets.py`** — the in-memory worksheet fake, extracted so the checklist harness, the journey suite, and the UI server all share one implementation. Only `get_sheet()` is replaced; the roster cache, row construction, `col_values` lookup and `update_cell` all run for real.
- **`test/fake_server.py`** — runs the real app on that fake so the UI suites need no spreadsheet and leave nothing behind. Its `POST /__test__/reset` route lives only in this file, so no test-only route ever ships in `app.py`.
- **`test/test_e2e_committee.py`** — 64 steps across 9 journeys: onboarding, a rating day, a rotation, a forgotten password, a privilege-escalation attempt, mid-session revocation, coexistence with the anonymous student flow, a week of history, and a backend outage.
- **Four Robot suites** — 105 cases over the member UI, the roster UI, the dashboard, and the HTTP surface. Renumbered into TC60–TC172 after a collision with `api_tests.robot` (TC39–TC54) was found; a duplicate check across all suites now reports none across 159 cases.
- **`common.resource`** — optional `CHROME_BINARY` / `CHROME_DRIVER` overrides, both defaulting to empty so CI behaviour is unchanged.
- **CI** — the credential-free Python suites run first and fail fast; the committee UI suites then run against the in-memory server rather than a shared test spreadsheet.

### Bug fixed
`get_committee_roster()` and five sibling functions called `get_sheet()` outside their try blocks, so an exception from the sheets layer escaped into the route and returned a 500 on the committee login page during an outage. The call now sits inside the try in all six, making the module's "never raises into a route" contract true rather than incidentally true.

### Results
105 Robot tests: 99 passed, 0 failed, 6 skipped. The skips are the Chart.js assertions, which need `cdn.jsdelivr.net`; they skip with a stated reason where that host is blocked. All six were confirmed passing by serving Chart.js locally, so only the CDN was missing, not the behaviour. Python suites: 59/59 and 64/64.

### How to revert
Delete `test/fake_sheets.py`, `test/fake_server.py`, `test/test_e2e_committee.py`, and the four `tests/committee_*.robot` files. Revert `tests/resources/common.resource` and `tests/run_tests.sh`. In `sheets.py`, move the `get_sheet()` calls back outside their try blocks (not advised — that restores the 500).

---

## [2026-09-04 12:00] — Food Committee Module & Admin Member Management

**Files changed:** `app.py`, `sheets.py`, `auth.py` (new), `csrf.py` (new), `manage_committee.py` (new), `templates/committee_*.html` (new), `templates/admin_*.html` (new), `static/committee*.js` (new), `static/style.css`, `test/test_committee.py` (new), `tests/committee_tests.robot` (new), `.github/workflows/messmate_tests.yml`, `README.md`
**Type:** Feature
**Status:** ✅ Working

### What changed
Added the SaiU Food Committee module: member login, a five-dimension rating page (taste, quality, variety, hygiene, menu) with a written review, a separate committee dashboard, and a browser UI for admins to manage the roster.

### Why
The Food Committee gives structured, attributed feedback that complements — but must not be mixed with — anonymous student ratings. A five-member committee average and a 200-student average measure different things. Committee membership rotates periodically, so admins needed to add, rotate, and reset members without a redeploy or a terminal.

### Details
- **Data:** two new tabs, `committee_members` and `committee_reviews`. Reviews store a plain-text `Date` column so filtering never parses a timestamp — the failure mode that forced the six-format fallback parser in `get_today_responses()`.
- **Auth:** session login via `werkzeug.security` scrypt hashes (no new dependency). The roster is cached for 60s to stay inside Google's 100-reads/100s quota; every write invalidates it, so a new member can sign in immediately.
- **Privilege separation:** the existing `?token=` credential still opens both read-only dashboards, but every roster mutation now requires an admin session. A query-string secret leaks into browser history, `Referer` headers, and hosting access logs — tolerable for a read-only page, not for one that can mint accounts.
- **CSRF:** added for all authenticated POSTs. Previously unnecessary (the only POST was an anonymous public form); an authenticated admin session with state-changing POSTs is exactly what CSRF exploits.
- **Member UI:** add, bulk-add from a pasted `Name, email` list (one `append_rows` call, not one per member), activate, deactivate, and password reset. Passwords are server-generated, shown once, and stored only as hashes. `Must_Change_Password` forces a rotation at first sign-in. No delete — deactivation preserves review history.
- **Rate limiting:** committee submissions are deliberately exempt from the per-IP cap. Campus Wi-Fi puts the whole committee behind one NAT address, so a per-IP rule would lock everyone out after the first submission; duplicate control is per member per day instead.
- **Verification:** `test/test_committee.py` runs 59 checks with no Google credentials, driving the real routes against an in-memory fake of the sheets layer. All pass.

### Regressions guarded
`templates/form.html`, `templates/dashboard.html`, and `static/dashboard.js` are byte-for-byte unmodified, so the existing form and dashboard suites are unaffected. No existing `sheets.py` function was changed. The app boots without any new env var — only the roster UI requires `ADMIN_PASSWORD_HASH`.

### How to revert
Delete `auth.py`, `csrf.py`, `manage_committee.py`, `test/test_committee.py`, `tests/committee_tests.robot`, `tests/resources/committee_keywords.resource`, the `committee_*`/`admin_*` templates, and `static/committee*.js`. In `app.py` remove the Food Committee section, the session/CSRF config block, and restore the inline token check on `/dashboard`. In `sheets.py` remove everything below the "Food Committee" banner. Revert the appended block in `static/style.css`.

---

## [2026-04-19 14:30] — Robot Framework Test Suite & CI Integration

**Files changed:** `tests/`, `TESTING.md`, `.github/workflows/messmate_tests.yml`, `templates/form.html`, `templates/thanks.html`
**Type:** Feature
**Status:** ✅ Working

### What changed
Implemented a comprehensive end-to-end automated testing suite using Robot Framework, added detailed documentation, and initialized GitHub Actions CI testing pipeline.

### Why
To ensure all API endpoints and UI elements continue to function smoothly during future developments, and successfully vet edge-cases, data validation, rate-limits, and DOM rendering.

### Details
- Built Form UI test suites validating conditional dropdown logic, character limits, rate triggers, and strict submissions.
- Developed Dashboard UI tests to automatically confirm stat cards logic, dynamic Chart.js rendering, and correct HTML empty states.
- Created Backend API tests asserting raw target statuses without browser latency, and verifying security checks (XSS stripping).
- Added static data attributes (`data-item`, `data-rice-row`) natively to frontend templates.

### How to revert
Delete `tests/` directory, `TESTING.md`, and the contents inside `.github/`. Remove `data-` attributes from inside `form.html` and `thanks.html`.

---

## [2026-04-19 14:00] — Google Sheets Robustness & Filtering Fixes

**Files changed:** `sheets.py`
**Type:** Bug Fix
**Status:** ✅ Working

### What changed
Hardened Google Sheets persistence to bypass internal automatic date re-formatting causing dashboard calculations to miss daily inputs.

### Why
Google Sheets randomly re-formats dynamically assigned cell timestamps based on generic regional settings causing string `startswith()` matches against today's date to silently fail, returning `0` live feedback metrics on the dashboard.

### Details
- Appended `value_input_option='RAW'` parameters natively into `append_row` commands.
- Expanded `get_today_responses()` to dynamically cycle and loop through multiple timestamp formulas matching dynamically with `datetime.strptime()` for reliable data aggregation.

### How to revert
Remove `'RAW'` designation and fallback date cycles in `sheets.py`.

---

## [2026-03-17 12:45] — Item Scores Tooltip Update

**Files changed:** `app.py`, `static/dashboard.js`
**Type:** Feature
**Status:** ✅ Working

### What changed
Updated the "Today's Item Scores" horizontal bar chart to display both the average score and the total number of student ratings for each specific food item.

### Why
To provide stakeholders with more context on how many students actually rated a particular dish, rather than just showing the average score which might be based on a single response.

### Details
- Modified `app.py` to return a dictionary for each item containing `avg` and `count`.
- Updated `dashboard.js` with a custom Chart.js tooltip callback to parse and display "Avg Score" and "Rated by X students".
- Handled edge cases where items have zero ratings.

### How to revert
Revert `item_data` in `app.py` to store raw floats and simplify the tooltip callback in `dashboard.js`.

---

## [2026-03-17 12:40] — Daily Summary Sheet Fix & Auto-Updates

**Files changed:** `sheets.py`, `app.py`, `seed_data.py`
**Type:** Bug Fix
**Status:** ✅ Working

### What changed
Implemented real-time calculation and updates for the `daily_summary` Google Sheet.

### Why
The `daily_summary` sheet was previously empty or showing zeros because no logic existed to populate it. It now updates automatically with every new feedback submission.

### Details
- Added `update_daily_summary_for_today()` in `sheets.py` to calculate averages from today's responses.
- Integrated the update call into the `/submit` route in `app.py`.
- Updated `seed_data.py` to also populate the `daily_summary` sheet when generating mock data.

### How to revert
Remove the `update_daily_summary_for_today()` calls in `app.py` and `seed_data.py`.

---

## [2026-03-17 09:45] — Trend Chart Tooltip Update

**Files changed:** `app.py`, `static/dashboard.js`
**Type:** Feature
**Status:** ✅ Working

### What changed
Updated the 7-day/30-day trend chart tooltips to show the number of responses for each day alongside the average score.

### Why
Provides better insight into the data density for each day on the trend line.

### Details
- Updated `app.py` to include `Response_Count` in the `trend_data` payload.
- Modified `dashboard.js` tooltip callback to display "Avg Score" and "Responses".

### How to revert
Remove `Response_Count` from the `trend_data` list in `app.py` and revert the tooltip label function in `dashboard.js`.

---

## [2026-03-17] — QR Code Generator Added

**Files changed:** `generate_qr.py`
**Type:** Feature
**Status:** ✅ Working

### What changed
Added a utility script to generate a QR code for the application URL.

### Why
To allow students to quickly scan and access the feedback form from printed notices in the mess hall.

### Details
- Uses `qrcode` library to generate `messmate_qr.png`.
- Configurable for different deployment URLs.

### How to revert
Delete `generate_qr.py` and `messmate_qr.png`.

---

## [2026-03-17] — Seed Data Added

**Files changed:** `seed_data.py`
**Type:** Feature
**Status:** ✅ Working

### What changed
Created a demo data seeding script that injects 70 mock responses into the database.

### Why
To populate the dashboard with realistic data for VC presentations and prototypes.

### Details
- Generates diversified scores (1-5) and random timestamps across the last 7 days.
- Includes randomized reviews and suggestions from a sample pool.

### How to revert
Manually clear the `responses` tab in Google Sheets or delete the `seed_data.py` script.

---

## [2026-03-17] — Admin Dashboard Built

**Files changed:** `templates/dashboard.html`, `static/dashboard.js`
**Type:** Feature
**Status:** ✅ Working

### What changed
Developed the internal admin dashboard for real-time canteen feedback visualization.

### Why
To allow canteen managers and stakeholders to monitor student satisfaction and food quality trends.

### Details
- Stat cards for "Today's Average" and "Response Count".
- 7-day/30-day toggleable trend line chart using Chart.js.
- Horizontal bar chart for per-item ratings.
- Real-time suggestions feed.

### How to revert
Delete `templates/dashboard.html` and `static/dashboard.js` references.

---

## [2026-03-17] — Student Feedback Form Built

**Files changed:** `templates/form.html`, `static/style.css`
**Type:** Feature
**Status:** ✅ Working

### What changed
Created the primary student-facing feedback interface.

### Why
To capture live feedback from students after meals.

### Details
- Emoji-based rating system.
- Conditional logic for Rice (Curry/Rasam).
- Specific ratings for 10+ food items.
- Character-limited review and suggestion text areas.

### How to revert
Revert the HTML structure of `form.html` to a basic version.

---

## [2026-03-17] — Initial Project Scaffold

**Files changed:** `app.py`, `sheets.py`, `requirements.txt`, `Procfile`, `.gitignore`
**Type:** Feature
**Status:** ✅ Working

### What changed
Set up the base Flask application structure and Google Sheets integration.

### Why
Initial repository setup for the MessMate project.

### Details
- Configured Flask server (`app.py`).
- Implemented Google Sheets API wrapper (`sheets.py`).
- Added dependency tracking (`requirements.txt`) and deployment config (`Procfile`).

### How to revert
N/A (Initial commit).

---

## [TEMPLATE — copy this for every future change]
## [YYYY-MM-DD HH:MM] — Short title

**Files changed:** 
**Type:** Bug Fix / Feature / Config / Refactor / Hotfix
**Status:** ✅ Working / ⚠️ Needs Testing / ❌ Broke Something

### What changed


### Why


### Details


### How to revert

---
