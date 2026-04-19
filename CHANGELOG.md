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
