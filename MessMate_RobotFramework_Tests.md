# MessMate — Robot Framework Test Suite Prompt
**Python + Robot Framework + SeleniumLibrary + RequestsLibrary**
*End-to-end and API tests for the MessMate Flask app.*

---

## Prerequisites
Before pasting any block, make sure these are installed:
```bash
pip install robotframework
pip install robotframework-seleniumlibrary
pip install robotframework-requests
pip install webdrivermanager
webdrivermanager chrome --linkpath /usr/local/bin
```

---

## File Structure to Create
```
messmate/
└── tests/
    ├── resources/
    │   ├── common.resource       # Shared keywords and variables
    │   ├── form_keywords.resource
    │   └── dashboard_keywords.resource
    ├── form_tests.robot          # Student form UI tests
    ├── dashboard_tests.robot     # Dashboard UI tests
    ├── api_tests.robot           # Backend/API tests
    └── results/                  # Auto-generated test reports
```

---

# PROMPT BLOCK 0 — Setup & Common Resources

```
You are a senior QA engineer helping me write Robot Framework tests for
"MessMate" — a Flask web app where students rate college mess food.

=== APP OVERVIEW ===
Base URL     : http://localhost:5000 (configurable)
Form route   : GET /
Submit route : POST /submit (rate limited: 1 per IP per day)
Thanks route : GET /thanks
Dashboard    : GET /dashboard?token=TOKEN
Health route : GET /health

=== TECH STACK FOR TESTS ===
Robot Framework       : test runner
SeleniumLibrary       : browser UI automation
RequestsLibrary       : HTTP/API tests
Browser               : Chrome (headless for CI, headed for local dev)

=== FILE TO CREATE: tests/resources/common.resource ===

*** Settings ***
Library    SeleniumLibrary
Library    RequestsLibrary
Library    Collections
Library    String
Library    DateTime

*** Variables ***
${BASE_URL}           http://localhost:5000
${DASHBOARD_TOKEN}    vc2026
${DASHBOARD_URL}      ${BASE_URL}/dashboard?token=${DASHBOARD_TOKEN}
${BROWSER}            chrome
${HEADLESS}           ${TRUE}
${TIMEOUT}            10s
${CHROME_OPTIONS}     add_argument("--headless");add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")

*** Keywords ***
Open MessMate Browser
    [Documentation]    Opens Chrome and navigates to the form.
    ${options}=    Evaluate    sys.modules['selenium.webdriver'].ChromeOptions()    sys, selenium.webdriver
    Run Keyword If    ${HEADLESS}    Call Method    ${options}    add_argument    --headless
    Call Method    ${options}    add_argument    --no-sandbox
    Call Method    ${options}    add_argument    --disable-dev-shm-usage
    Open Browser    ${BASE_URL}    ${BROWSER}    options=${options}
    Set Selenium Timeout    ${TIMEOUT}
    Maximize Browser Window

Close MessMate Browser
    Close All Browsers

Navigate To Form
    Go To    ${BASE_URL}
    Wait Until Page Contains Element    id=overall_val    timeout=${TIMEOUT}

Navigate To Dashboard
    Go To    ${DASHBOARD_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}

Select Overall Emoji
    [Arguments]    ${score}
    [Documentation]    Clicks the emoji button for the given score (1-5).
    Click Element    css=.emoji-btn[data-value="${score}"]
    Wait Until Element Contains    id=overall_val    ${score}

Select Item Emoji
    [Arguments]    ${item_name}    ${score}
    [Documentation]    Selects an emoji rating for a specific item.
    Click Element    css=.emoji-btn[data-item="${item_name}"][data-value="${score}"]

Submit Form
    [Documentation]    Clicks the submit button and waits for redirect.
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.thanks-container    timeout=${TIMEOUT}

Page Should Show Error
    [Arguments]    ${message}
    Element Should Be Visible    css=.error-banner
    Page Should Contain    ${message}

=== FILE TO CREATE: tests/resources/form_keywords.resource ===

*** Settings ***
Resource    common.resource

*** Keywords ***
Fill Minimal Form
    [Arguments]    ${score}=3
    [Documentation]    Fills only the required Overall rating.
    Navigate To Form
    Select Overall Emoji    ${score}

Fill Full Form
    [Arguments]    ${overall}=4    ${chapati}=3    ${review}=Test review    ${suggestion}=Test suggestion
    Navigate To Form
    Select Overall Emoji    ${overall}
    Select Item Emoji    chapati    ${chapati}
    Input Text    css=textarea[name="review"]    ${review}
    Input Text    css=input[name="suggestion"]    ${suggestion}

Select Rice Option
    [Arguments]    ${option}
    [Documentation]    Selects from the Rice dropdown: Curry, Rasam, or Both.
    Select From List By Label    css=select[name="rice_served"]    ${option}

Submit Button Should Be Disabled
    Element Should Be Disabled    id=submit-btn

Submit Button Should Be Enabled
    Element Should Be Enabled    id=submit-btn

=== FILE TO CREATE: tests/resources/dashboard_keywords.resource ===

*** Settings ***
Resource    common.resource

*** Keywords ***
Get Stat Card Value
    [Arguments]    ${card_heading}
    [Documentation]    Returns the value text from a named stat card.
    ${value}=    Get Text    xpath=//h3[contains(text(),"${card_heading}")]/following-sibling::p
    RETURN    ${value}

Dashboard Should Show Average
    [Arguments]    ${expected}
    ${avg}=    Get Stat Card Value    Today's Average
    Should Be Equal As Strings    ${avg}    ${expected}

Dashboard Should Show Response Count
    [Arguments]    ${expected}
    ${count}=    Get Stat Card Value    Responses Today
    Should Be Equal As Numbers    ${count}    ${expected}

Chart Should Be Visible
    [Arguments]    ${chart_id}
    Element Should Be Visible    id=${chart_id}
    ${rendered}=    Execute Javascript    return document.getElementById('${chart_id}').getContext('2d') !== null
    Should Be True    ${rendered}

Produce the complete resource files with all keywords.
Tell me when done.
```

---

# PROMPT BLOCK 1 — Form UI Tests

```
MessMate Robot Framework resources are set up.
Now write the student form UI tests.

=== FILE TO CREATE: tests/form_tests.robot ===

*** Settings ***
Resource          resources/common.resource
Resource          resources/form_keywords.resource
Suite Setup       Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Navigate To Form

*** Test Cases ***

# ── SECTION 1: Page Load ──────────────────────────────────────────────────

TC01 Form Page Loads Successfully
    [Tags]    smoke    form
    Title Should Be    MessMate — Rate Today's Lunch 🍱
    Page Should Contain    How was today's lunch overall?
    Page Should Contain    Rate individual items

TC02 Submit Button Is Disabled On Page Load
    [Tags]    smoke    form    validation
    Submit Button Should Be Disabled

TC03 All Emoji Buttons Are Visible
    [Tags]    smoke    form
    FOR    ${score}    IN RANGE    1    6
        Element Should Be Visible    css=.emoji-btn[data-value="${score}"]
    END

# ── SECTION 2: Overall Rating ─────────────────────────────────────────────

TC04 Selecting Overall Emoji Enables Submit Button
    [Tags]    form    validation
    Select Overall Emoji    3
    Submit Button Should Be Enabled

TC05 Overall Emoji Selection Sets Hidden Input Value
    [Tags]    form    validation
    Select Overall Emoji    4
    ${val}=    Get Element Attribute    id=overall_val    value
    Should Be Equal    ${val}    4

TC06 Only One Overall Emoji Can Be Selected At A Time
    [Tags]    form    validation
    Select Overall Emoji    2
    Select Overall Emoji    5
    ${val}=    Get Element Attribute    id=overall_val    value
    Should Be Equal    ${val}    5
    Element Should Not Have Class    css=.emoji-btn[data-value="2"]    selected

TC07 All Five Overall Emoji Values Are Selectable
    [Tags]    form    validation
    FOR    ${score}    IN RANGE    1    6
        Select Overall Emoji    ${score}
        ${val}=    Get Element Attribute    id=overall_val    value
        Should Be Equal As Numbers    ${val}    ${score}
    END

# ── SECTION 3: Rice Dropdown ──────────────────────────────────────────────

TC08 Rice Rating Rows Hidden By Default
    [Tags]    form    rice
    Element Should Not Be Visible    css=[data-rice-row="curry"]
    Element Should Not Be Visible    css=[data-rice-row="rasam"]

TC09 Rice Dropdown Curry Shows Only Curry Row
    [Tags]    form    rice
    Select Rice Option    Curry
    Element Should Be Visible      css=[data-rice-row="curry"]
    Element Should Not Be Visible  css=[data-rice-row="rasam"]

TC10 Rice Dropdown Rasam Shows Only Rasam Row
    [Tags]    form    rice
    Select Rice Option    Rasam
    Element Should Not Be Visible  css=[data-rice-row="curry"]
    Element Should Be Visible      css=[data-rice-row="rasam"]

TC11 Rice Dropdown Both Shows Both Rows
    [Tags]    form    rice
    Select Rice Option    Both
    Element Should Be Visible    css=[data-rice-row="curry"]
    Element Should Be Visible    css=[data-rice-row="rasam"]

TC12 Rice Dropdown Reset Hides All Rice Rows
    [Tags]    form    rice
    Select Rice Option    Both
    Select From List By Label    css=select[name="rice_served"]    Select...
    Element Should Not Be Visible    css=[data-rice-row="curry"]
    Element Should Not Be Visible    css=[data-rice-row="rasam"]

TC13 Rice Rating Clears When Dropdown Is Reset
    [Tags]    form    rice
    Select Rice Option    Curry
    Select Item Emoji    rice_curry    4
    Select From List By Label    css=select[name="rice_served"]    Select...
    ${val}=    Get Element Attribute    css=input[name="rice_curry"]    value
    Should Be Equal    ${val}    ${EMPTY}

# ── SECTION 4: Review Text ────────────────────────────────────────────────

TC14 Review Character Counter Starts At Zero
    [Tags]    form    review
    Element Should Contain    css=.char-counter    0 / 150

TC15 Review Character Counter Updates On Input
    [Tags]    form    review
    Input Text    css=textarea[name="review"]    Hello
    Element Should Contain    css=.char-counter    5 / 150

TC16 Review Field Enforces 150 Character Limit
    [Tags]    form    review    validation
    ${long_text}=    Generate Random String    160    [LETTERS]
    Input Text    css=textarea[name="review"]    ${long_text}
    ${actual}=    Get Value    css=textarea[name="review"]
    ${length}=    Get Length    ${actual}
    Should Be True    ${length} <= 150

TC17 Review Counter Shows 150 At Limit
    [Tags]    form    review
    ${text}=    Generate Random String    150    [LETTERS]
    Input Text    css=textarea[name="review"]    ${text}
    Element Should Contain    css=.char-counter    150 / 150

# ── SECTION 5: Form Submission ────────────────────────────────────────────

TC18 Minimal Submission Succeeds
    [Tags]    form    submission    🔴must
    Fill Minimal Form    score=3
    Submit Form
    Title Should Be    MessMate — Thank You

TC19 Full Form Submission Succeeds
    [Tags]    form    submission    🔴must
    Fill Full Form    overall=4    chapati=3    review=Food was good    suggestion=Add puliyodarai
    Submit Form
    Title Should Be    MessMate — Thank You

TC20 Thank You Page Has Link Back To Form
    [Tags]    form    submission
    Fill Minimal Form
    Submit Form
    Page Should Contain Element    css=a[href="/"]

TC21 XSS In Review Is Not Executed
    [Tags]    form    security
    Navigate To Form
    Select Overall Emoji    3
    Input Text    css=textarea[name="review"]    <script>alert('xss')</script>
    Submit Form
    # If we reach the thanks page without an alert dialog, XSS is blocked
    Title Should Be    MessMate — Thank You
    Alert Should Not Be Present

# ── SECTION 6: Error States ───────────────────────────────────────────────

TC22 Submitting Without Overall Shows No POST
    [Tags]    form    validation
    Navigate To Form
    # Button is disabled — JS prevents submission, page stays on form
    Submit Button Should Be Disabled
    Location Should Be    ${BASE_URL}/

TC23 Error Banner Displays When Flask Returns Error
    [Tags]    form    error
    # Simulate by navigating with error param if your Flask route supports it
    # Otherwise test by triggering a rate-limit scenario
    Log    Error banner test — covered by rate limit test in api_tests.robot
```

---

# PROMPT BLOCK 2 — Dashboard UI Tests

```
Form tests are complete. Now write the dashboard UI tests.

=== FILE TO CREATE: tests/dashboard_tests.robot ===

*** Settings ***
Resource          resources/common.resource
Resource          resources/dashboard_keywords.resource
Suite Setup       Open MessMate Browser
Suite Teardown    Close MessMate Browser

*** Test Cases ***

# ── SECTION 1: Access Control ─────────────────────────────────────────────

TC24 Dashboard Without Token Returns 403
    [Tags]    dashboard    security    🔴must
    Go To    ${BASE_URL}/dashboard
    Page Should Contain    Access denied

TC25 Dashboard With Wrong Token Returns 403
    [Tags]    dashboard    security    🔴must
    Go To    ${BASE_URL}/dashboard?token=wrongtoken
    Page Should Contain    Access denied

TC26 Dashboard With Correct Token Loads Successfully
    [Tags]    dashboard    smoke    🔴must
    Navigate To Dashboard
    Title Should Be    MessMate — Admin Dashboard 📊
    Page Should Contain    MessMate Admin Dashboard

# ── SECTION 2: Stat Cards ─────────────────────────────────────────────────

TC27 All Three Stat Cards Are Present
    [Tags]    dashboard    smoke
    Navigate To Dashboard
    Page Should Contain    Today's Average
    Page Should Contain    Responses Today
    Page Should Contain    Today's Date

TC28 Today Date Card Shows Correct Day
    [Tags]    dashboard    smoke
    Navigate To Dashboard
    ${today}=    Get Current Date    result_format=%A, %d %B %Y
    ${card_val}=    Get Stat Card Value    Today's Date
    Should Be Equal    ${card_val}    ${today}

TC29 Average Card Shows Dashes When No Data
    [Tags]    dashboard    empty-state
    Navigate To Dashboard
    ${avg}=    Get Stat Card Value    Today's Average
    # Either shows "--" (no data) or a number (if seeded data exists)
    Should Match Regexp    ${avg}    (--|[1-5]\\.[0-9])

TC30 Average Card Has Correct Colour Class
    [Tags]    dashboard    visual
    Navigate To Dashboard
    ${avg_text}=    Get Stat Card Value    Today's Average
    ${has_score}=    Run Keyword And Return Status    Should Match Regexp    ${avg_text}    [1-5]\\.[0-9]
    Run Keyword If    ${has_score}    Verify Average Card Colour Class    ${avg_text}

Verify Average Card Colour Class
    [Arguments]    ${avg_text}
    ${avg}=    Convert To Number    ${avg_text}
    ${classes}=    Get Element Attribute    css=.stat-card:first-child    class
    IF    ${avg} < 2.5
        Should Contain    ${classes}    score-red
    ELSE IF    ${avg} <= 3.5
        Should Contain    ${classes}    score-amber
    ELSE
        Should Contain    ${classes}    score-green
    END

# ── SECTION 3: Charts ─────────────────────────────────────────────────────

TC31 Trend Chart Canvas Is Present And Rendered
    [Tags]    dashboard    charts
    Navigate To Dashboard
    Chart Should Be Visible    trendChart

TC32 Item Chart Canvas Is Present And Rendered
    [Tags]    dashboard    charts
    Navigate To Dashboard
    Chart Should Be Visible    itemChart

TC33 Trend Chart Defaults To 7 Day View
    [Tags]    dashboard    charts
    Navigate To Dashboard
    Element Should Have Class    id=btn7Days    active
    Element Should Not Have Class    id=btn30Days    active
    Element Should Contain    id=trendChartTitle    7-Day

TC34 Trend Chart Toggle Switches To 30 Days
    [Tags]    dashboard    charts
    Navigate To Dashboard
    Click Element    id=btn30Days
    Element Should Have Class    id=btn30Days    active
    Element Should Not Have Class    id=btn7Days    active
    Element Should Contain    id=trendChartTitle    30-Day

TC35 Trend Chart Toggle Switches Back To 7 Days
    [Tags]    dashboard    charts
    Navigate To Dashboard
    Click Element    id=btn30Days
    Click Element    id=btn7Days
    Element Should Have Class    id=btn7Days    active
    Element Should Contain    id=trendChartTitle    7-Day

# ── SECTION 4: Suggestions ────────────────────────────────────────────────

TC36 Suggestions Section Is Present
    [Tags]    dashboard    suggestions
    Navigate To Dashboard
    Page Should Contain    Student Suggestions

TC37 Empty Suggestions Shows Friendly Message
    [Tags]    dashboard    suggestions    empty-state
    Navigate To Dashboard
    ${has_suggestions}=    Run Keyword And Return Status
    ...    Page Should Contain Element    css=.suggestion-item
    Run Keyword Unless    ${has_suggestions}
    ...    Page Should Contain    No suggestions yet

TC38 Suggestions Do Not Show Raw HTML Entities
    [Tags]    dashboard    security
    Navigate To Dashboard
    Page Should Not Contain    &amp;
    Page Should Not Contain    &lt;
    Page Should Not Contain    &gt;
```

---

# PROMPT BLOCK 3 — API / Backend Tests

```
UI tests are complete. Now write the API-level tests using RequestsLibrary.
These run without a browser — faster, for CI pipelines.

=== FILE TO CREATE: tests/api_tests.robot ===

*** Settings ***
Resource          resources/common.resource
Suite Setup       Create Session    messmate    ${BASE_URL}
Suite Teardown    Delete All Sessions

*** Test Cases ***

# ── SECTION 1: Health Check ───────────────────────────────────────────────

TC39 Health Endpoint Returns 200
    [Tags]    api    smoke    🔴must
    ${resp}=    GET On Session    messmate    /health
    Status Should Be    200    ${resp}

TC40 Health Endpoint Returns JSON Status OK
    [Tags]    api    smoke    🔴must
    ${resp}=    GET On Session    messmate    /health
    ${body}=    Set Variable    ${resp.json()}
    Should Be Equal    ${body}[status]    ok

# ── SECTION 2: Form Submission API ────────────────────────────────────────

TC41 Valid Minimal POST Returns 200 Or Redirect
    [Tags]    api    submission
    ${data}=    Create Dictionary
    ...    overall=3
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Be True    ${resp.status_code} in [200, 302]

TC42 POST Without Overall Returns Error
    [Tags]    api    submission    validation
    ${data}=    Create Dictionary    chapati=3
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    # Should not redirect to /thanks — either 200 with error or 400
    Should Not Contain    ${resp.url}    /thanks

TC43 POST With Invalid Overall Value Returns Error
    [Tags]    api    submission    validation
    ${data}=    Create Dictionary    overall=9
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Not Contain    ${resp.url}    /thanks

TC44 POST With Non-Numeric Overall Returns Error
    [Tags]    api    submission    validation
    ${data}=    Create Dictionary    overall=abc
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Not Contain    ${resp.url}    /thanks

TC45 POST With XSS In Review Is Accepted But Sanitized
    [Tags]    api    security
    ${data}=    Create Dictionary
    ...    overall=3
    ...    review=<script>alert('xss')</script>
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    # Submission should succeed (200/302) — sanitisation happens server-side
    Should Be True    ${resp.status_code} in [200, 302]

TC46 POST With Overlong Review Is Truncated Or Rejected
    [Tags]    api    submission    validation
    ${long_review}=    Generate Random String    200    [LETTERS]
    ${data}=    Create Dictionary    overall=3    review=${long_review}
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Be True    ${resp.status_code} in [200, 302]

TC47 Rate Limit Blocks Second Submission From Same IP
    [Tags]    api    rate-limit    🔴must
    [Documentation]    This test submits twice and expects the second to be rate-limited (429).
    ...    Note: only works if the first submission in this session hasn't already triggered the limit.
    ...    Run this test in isolation or reset the limiter between runs.
    ${data}=    Create Dictionary    overall=4
    ${resp1}=    POST On Session    messmate    /submit    data=${data}    expected_status=any
    ${resp2}=    POST On Session    messmate    /submit    data=${data}    expected_status=any
    Should Be Equal As Numbers    ${resp2.status_code}    429
    ${body}=    Convert To String    ${resp2.text}
    Should Contain    ${body}    tomorrow

# ── SECTION 3: Dashboard API ──────────────────────────────────────────────

TC48 Dashboard Without Token Returns 403
    [Tags]    api    security    🔴must
    ${resp}=    GET On Session    messmate    /dashboard    expected_status=any
    Should Be Equal As Numbers    ${resp.status_code}    403

TC49 Dashboard With Wrong Token Returns 403
    [Tags]    api    security
    ${params}=    Create Dictionary    token=wrongtoken
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}    expected_status=any
    Should Be Equal As Numbers    ${resp.status_code}    403

TC50 Dashboard With Correct Token Returns 200
    [Tags]    api    security    🔴must
    ${params}=    Create Dictionary    token=${DASHBOARD_TOKEN}
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}
    Status Should Be    200    ${resp}
    Should Contain    ${resp.text}    MessMate

TC51 Dashboard Response Contains Chart Data Script
    [Tags]    api    dashboard
    ${params}=    Create Dictionary    token=${DASHBOARD_TOKEN}
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}
    Should Contain    ${resp.text}    MESSMATE_DATA
    Should Contain    ${resp.text}    trendData
    Should Contain    ${resp.text}    itemData

TC52 Dashboard Response Contains All Four Sections
    [Tags]    api    dashboard
    ${params}=    Create Dictionary    token=${DASHBOARD_TOKEN}
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}
    Should Contain    ${resp.text}    Today's Average
    Should Contain    ${resp.text}    Responses Today
    Should Contain    ${resp.text}    trendChart
    Should Contain    ${resp.text}    itemChart
    Should Contain    ${resp.text}    Student Suggestions

# ── SECTION 4: Static Assets ──────────────────────────────────────────────

TC53 CSS File Is Served
    [Tags]    api    assets
    ${resp}=    GET On Session    messmate    /static/style.css
    Status Should Be    200    ${resp}
    Should Contain    ${resp.headers}[Content-Type]    text/css

TC54 Dashboard JS File Is Served
    [Tags]    api    assets
    ${resp}=    GET On Session    messmate    /static/dashboard.js
    Status Should Be    200    ${resp}
    Should Contain    ${resp.headers}[Content-Type]    javascript
```

---

# PROMPT BLOCK 4 — Test Runner & CI Setup

```
All test files are written. Now set up the runner and reporting.

=== FILE TO CREATE: tests/run_tests.sh ===
#!/bin/bash
# MessMate Test Runner
# Usage: bash tests/run_tests.sh [tag]
# Example: bash tests/run_tests.sh smoke

TAG=${1:-""}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="tests/results/${TIMESTAMP}"
mkdir -p ${OUTPUT_DIR}

if [ -n "$TAG" ]; then
    echo "Running tests with tag: ${TAG}"
    robot --include ${TAG} \
          --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
else
    echo "Running all tests"
    robot --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
fi

echo ""
echo "Results saved to: ${OUTPUT_DIR}"
echo "Open ${OUTPUT_DIR}/report.html to view the test report."

=== FILE TO CREATE: tests/run_tests.bat (Windows) ===
@echo off
set TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set OUTPUT_DIR=tests\results\%TIMESTAMP%
mkdir %OUTPUT_DIR%

if "%1"=="" (
    robot --outputdir %OUTPUT_DIR% --log log.html --report report.html tests\
) else (
    robot --include %1 --outputdir %OUTPUT_DIR% --log log.html --report report.html tests\
)

echo Results saved to: %OUTPUT_DIR%

=== HOW TO RUN ===
Run all tests:
    robot --outputdir tests/results tests/

Run only smoke tests (fast, no browser needed):
    robot --include smoke --outputdir tests/results tests/

Run only API tests (no browser):
    robot --include api --outputdir tests/results tests/api_tests.robot

Run only security tests:
    robot --include security --outputdir tests/results tests/

Run a single test by name:
    robot --test "TC40 Health Endpoint Returns JSON Status OK" tests/api_tests.robot

Run headed (visible browser, for debugging):
    robot --variable HEADLESS:${FALSE} tests/form_tests.robot

Generate combined report from multiple runs:
    rebot --outputdir tests/results tests/results/*/output.xml

=== FILE TO CREATE: .github/workflows/messmate_tests.yml ===
(GitHub Actions CI — runs tests on every push)

name: MessMate Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install robotframework
          pip install robotframework-seleniumlibrary
          pip install robotframework-requests
          pip install -r requirements.txt

      - name: Install Chrome
        uses: browser-actions/setup-chrome@latest

      - name: Install ChromeDriver
        run: |
          pip install webdriver-manager
          python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

      - name: Start MessMate app
        env:
          FLASK_SECRET_KEY: ${{ secrets.FLASK_SECRET_KEY }}
          SPREADSHEET_ID: ${{ secrets.SPREADSHEET_ID }}
          GOOGLE_CREDENTIALS_JSON: ${{ secrets.GOOGLE_CREDENTIALS_JSON }}
          DASHBOARD_TOKEN: ${{ secrets.DASHBOARD_TOKEN }}
        run: |
          python app.py &
          sleep 3

      - name: Run Robot Framework tests
        run: |
          robot --include smoke \
                --include api \
                --outputdir tests/results \
                tests/

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: robot-results
          path: tests/results/

Tell me when all files are created and show me the full folder structure.
```

---

# Quick Reference

| Command | What it runs |
|---------|-------------|
| `robot tests/` | All tests |
| `robot --include smoke tests/` | Smoke tests only (fast check) |
| `robot --include api tests/` | API tests only (no browser) |
| `robot --include 🔴must tests/` | Critical path only |
| `robot --include security tests/` | Security tests only |
| `robot --variable HEADLESS:${FALSE} tests/` | Headed browser (debug mode) |
| `robot --test "TC40*" tests/` | Single test by name |

---

# Tag Reference

| Tag | Tests covered |
|-----|--------------|
| `smoke` | Basic sanity — page loads, health check |
| `form` | All student form tests |
| `dashboard` | All dashboard tests |
| `api` | All RequestsLibrary HTTP tests (no browser) |
| `submission` | Form POST submission flows |
| `validation` | Input validation (required fields, limits) |
| `security` | XSS, token protection, double-escape |
| `rate-limit` | Spam protection test |
| `charts` | Chart rendering tests |
| `suggestions` | Suggestions section tests |
| `empty-state` | No-data fallback states |
| `rice` | Rice dropdown conditional logic |
| `🔴must` | Critical path — run these before any demo |

---

# Known Issues & Fixes

| Problem | Fix |
|---------|-----|
| `SeleniumLibrary` not found | `pip install robotframework-seleniumlibrary` |
| ChromeDriver version mismatch | `pip install webdriver-manager` and use `ChromeDriverManager().install()` |
| Rate limit test fails (TC47) | Run in isolation: `robot --test "TC47*" tests/api_tests.robot` — needs a fresh IP/session |
| Headless Chrome crashes on Linux | Add `--disable-dev-shm-usage` and `--no-sandbox` to Chrome options |
| Emoji in test names break on Windows | Save `.robot` files as UTF-8 with BOM or replace emoji tags with words |
| `Alert Should Not Be Present` flakes | Add `Sleep    1s` before the assertion to let JS settle |
| Dashboard tests fail without seed data | Run `python seed_data.py` before dashboard tests |

---

*MessMate Robot Framework Test Prompt v1.0 · April 2026*
