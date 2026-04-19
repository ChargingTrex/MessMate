# MessMate — Robot Framework Test Guide 🧪

A complete guide to running and managing the automated test suite for MessMate.

---

## Prerequisites

### 1. Install Python Dependencies

```bash
# Activate your virtual environment first
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install Robot Framework and libraries
pip install robotframework
pip install robotframework-seleniumlibrary
pip install robotframework-requests
```

### 2. Install Chrome & ChromeDriver (for UI tests)

```bash
# Option A: Using webdriver-manager (recommended)
pip install webdriver-manager

# Option B: Manual install
# Download ChromeDriver matching your Chrome version from:
# https://googlechromelabs.github.io/chrome-for-testing/
```

### 3. Start the MessMate App

The Flask app must be running before executing tests:

```bash
python app.py
```

The app will start at `http://localhost:5000`.

> **Important:** The in-memory rate limiter resets when the app restarts. If submission tests fail with 429, restart the app.

---

## Test File Structure

```
tests/
├── resources/
│   ├── common.resource              # Shared keywords & variables
│   ├── form_keywords.resource       # Form-specific keywords
│   └── dashboard_keywords.resource  # Dashboard-specific keywords
├── form_tests.robot                 # 23 UI tests  (TC01–TC23)
├── dashboard_tests.robot            # 15 UI tests  (TC24–TC38)
├── api_tests.robot                  # 16 API tests (TC39–TC54)
├── run_tests.sh                     # Shell test runner script
└── results/                         # Auto-generated reports (gitignored)
```

---

## Running Tests

### Run All Tests

```bash
robot --outputdir tests/results tests/
```

### Run by Test Suite

```bash
# Form UI tests only
robot --outputdir tests/results tests/form_tests.robot

# Dashboard UI tests only
robot --outputdir tests/results tests/dashboard_tests.robot

# API tests only (no browser needed — fastest)
robot --outputdir tests/results tests/api_tests.robot
```

### Run by Tag

```bash
# Smoke tests (quick sanity check)
robot --include smoke --outputdir tests/results tests/

# API tests only (no browser)
robot --include api --outputdir tests/results tests/

# Security tests
robot --include security --outputdir tests/results tests/

# Critical path only (must-pass for demo)
robot --include must --outputdir tests/results tests/

# Form validation tests
robot --include validation --outputdir tests/results tests/

# Chart rendering tests
robot --include charts --outputdir tests/results tests/

# Rice dropdown logic tests
robot --include rice --outputdir tests/results tests/
```

### Run a Single Test by Name

```bash
robot --test "TC01 Form Page Loads Successfully" tests/form_tests.robot

robot --test "TC40 Health Endpoint Returns JSON Status OK" tests/api_tests.robot

robot --test "TC47*" tests/api_tests.robot   # Wildcard match
```

### Run with Visible Browser (Debug Mode)

By default, UI tests run headless. To see the browser:

```bash
robot --variable HEADLESS:\${FALSE} --outputdir tests/results tests/form_tests.robot
```

### Use the Test Runner Script

```bash
# Run all tests
bash tests/run_tests.sh

# Run only smoke tests
bash tests/run_tests.sh smoke

# Run only API tests
bash tests/run_tests.sh api
```

This creates a timestamped output directory under `tests/results/`.

---

## Tag Reference

| Tag | What it covers |
|-----|---------------|
| `smoke` | Basic sanity — page loads, health check |
| `form` | All student form tests |
| `dashboard` | All dashboard tests |
| `api` | All HTTP/API tests (no browser) |
| `submission` | Form POST submission flows |
| `validation` | Input validation (required fields, character limits) |
| `security` | XSS, token protection, double-escape checks |
| `rate-limit` | Spam protection (1/IP/day limit) |
| `charts` | Chart.js rendering and toggle tests |
| `suggestions` | Suggestions section tests |
| `empty-state` | No-data fallback states |
| `rice` | Rice dropdown conditional logic |
| `must` | Critical path — run before any demo |
| `visual` | Visual/styling tests (color classes) |
| `review` | Review textarea and character counter |
| `assets` | Static file serving (CSS, JS) |
| `error` | Error banner display tests |

---

## Test Case Summary

### Form Tests (TC01–TC23)

| ID | Test | Tags |
|----|------|------|
| TC01 | Form page loads with correct title | smoke, form |
| TC02 | Submit button disabled on load | smoke, form, validation |
| TC03 | All 5 emoji buttons visible | smoke, form |
| TC04 | Selecting emoji enables submit | form, validation |
| TC05 | Emoji sets hidden input value | form, validation |
| TC06 | Only one emoji selected at a time | form, validation |
| TC07 | All 5 emoji values selectable | form, validation |
| TC08 | Rice rows hidden by default | form, rice |
| TC09 | Curry shows only curry row | form, rice |
| TC10 | Rasam shows only rasam row | form, rice |
| TC11 | Both shows both rows | form, rice |
| TC12 | Reset hides all rice rows | form, rice |
| TC13 | Reset clears rice ratings | form, rice |
| TC14 | Char counter starts at 0 | form, review |
| TC15 | Char counter updates on input | form, review |
| TC16 | Review enforces 150 char limit | form, review, validation |
| TC17 | Counter shows 150 at limit | form, review |
| TC18 | Minimal submission succeeds | form, submission, must |
| TC19 | Full form submission succeeds | form, submission, must |
| TC20 | Thanks page has back link | form, submission |
| TC21 | XSS in review not executed | form, security |
| TC22 | No POST without overall | form, validation |
| TC23 | Error banner test (placeholder) | form, error |

### Dashboard Tests (TC24–TC38)

| ID | Test | Tags |
|----|------|------|
| TC24 | No token → 403 | dashboard, security, must |
| TC25 | Wrong token → 403 | dashboard, security, must |
| TC26 | Correct token loads dashboard | dashboard, smoke, must |
| TC27 | All 3 stat cards present | dashboard, smoke |
| TC28 | Date card shows correct day | dashboard, smoke |
| TC29 | Average shows "--" or score | dashboard, empty-state |
| TC30 | Average card color class | dashboard, visual |
| TC31 | Trend chart canvas rendered | dashboard, charts |
| TC32 | Item chart canvas rendered | dashboard, charts |
| TC33 | Defaults to 7-day view | dashboard, charts |
| TC34 | Toggle switches to 30 days | dashboard, charts |
| TC35 | Toggle switches back to 7 days | dashboard, charts |
| TC36 | Suggestions section present | dashboard, suggestions |
| TC37 | Empty suggestions message | dashboard, suggestions, empty-state |
| TC38 | No raw HTML entities | dashboard, security |

### API Tests (TC39–TC54)

| ID | Test | Tags |
|----|------|------|
| TC39 | Health returns 200 | api, smoke, must |
| TC40 | Health returns `{"status":"ok"}` | api, smoke, must |
| TC41 | Valid POST returns 200/302 | api, submission |
| TC42 | POST without overall → error | api, submission, validation |
| TC43 | Invalid overall value → error | api, submission, validation |
| TC44 | Non-numeric overall → error | api, submission, validation |
| TC45 | XSS accepted but sanitized | api, security |
| TC46 | Overlong review truncated | api, submission, validation |
| TC47 | Rate limit blocks 2nd submit | api, rate-limit, must |
| TC48 | Dashboard no token → 403 | api, security, must |
| TC49 | Dashboard wrong token → 403 | api, security |
| TC50 | Dashboard correct token → 200 | api, security, must |
| TC51 | Dashboard has chart data | api, dashboard |
| TC52 | Dashboard has all sections | api, dashboard |
| TC53 | CSS file served (200) | api, assets |
| TC54 | Dashboard JS served (200) | api, assets |

---

## Viewing Test Reports

After running tests, Robot Framework generates HTML reports:

```bash
# Open the report
open tests/results/report.html    # macOS
# xdg-open tests/results/report.html  # Linux
# start tests/results/report.html     # Windows
```

The report includes:
- **Summary** — pass/fail counts and execution time
- **Log** — detailed step-by-step execution log with screenshots on failure
- **Output XML** — machine-readable results for CI integration

### Combine Reports from Multiple Runs

```bash
rebot --outputdir tests/results tests/results/*/output.xml
```

---

## CI/CD Integration (GitHub Actions)

The project includes a GitHub Actions workflow at `.github/workflows/messmate_tests.yml`.

### What It Does
1. Sets up Python 3.11 and Chrome
2. Installs Robot Framework + app dependencies
3. Starts the Flask app in the background
4. Runs `smoke` and `api` tagged tests
5. Uploads test results as build artifacts

### Required GitHub Secrets
Set these in your repo → Settings → Secrets:

| Secret | Value |
|--------|-------|
| `FLASK_SECRET_KEY` | Your generated secret key |
| `SPREADSHEET_ID` | Google Sheet ID from URL |
| `GOOGLE_CREDENTIALS_JSON` | Full service account JSON string |
| `DASHBOARD_TOKEN` | e.g. `vc2026` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `SeleniumLibrary not found` | `pip install robotframework-seleniumlibrary` |
| ChromeDriver version mismatch | `pip install webdriver-manager` |
| Rate limit test (TC47) fails | Restart the Flask app to reset the in-memory limiter |
| Submission tests return 429 | Rate limiter triggered — restart `python app.py` |
| Headless Chrome crashes on Linux | Already handled — `--no-sandbox` and `--disable-dev-shm-usage` in options |
| UI tests can't find elements | Ensure the app is running at `http://localhost:5000` |
| Dashboard tests fail with no data | Run `python seed_data.py` to seed demo data first |
| `Alert Should Not Be Present` flakes | Add `Sleep 1s` before the assertion |
| Emoji in tags break on Windows | Save `.robot` files as UTF-8 |

---

## Quick Commands Cheat Sheet

```bash
# ─── Setup ───────────────────────────────────────────
pip install robotframework robotframework-seleniumlibrary robotframework-requests
python app.py                           # Start the app

# ─── Run Tests ───────────────────────────────────────
robot --include api tests/              # API only (fastest, no browser)
robot --include smoke tests/            # Quick smoke check
robot --include must tests/             # Critical path for demo
robot tests/                            # Everything

# ─── Debug ───────────────────────────────────────────
robot --variable HEADLESS:\${FALSE} tests/form_tests.robot  # See the browser
robot --test "TC01*" tests/form_tests.robot                 # Single test
robot --loglevel DEBUG tests/api_tests.robot                # Verbose logging

# ─── Reports ─────────────────────────────────────────
open tests/results/report.html          # View report (macOS)
open tests/results/log.html             # View detailed log
```
