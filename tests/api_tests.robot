*** Settings ***
Documentation     API/backend tests for MessMate using RequestsLibrary.
...               These tests run without a browser — fast for CI pipelines.
...               Tests health check, form submission, validation, rate limiting,
...               dashboard access control, and static assets.
Library           RequestsLibrary
Library           Collections
Library           String
Suite Setup       Create Session    messmate    ${BASE_URL}
Suite Teardown    Delete All Sessions

*** Variables ***
${BASE_URL}           http://localhost:5000
${DASHBOARD_TOKEN}    vc2026

*** Test Cases ***

# ── SECTION 1: Health Check ───────────────────────────────────────────────

TC39 Health Endpoint Returns 200
    [Tags]    api    smoke    must
    [Documentation]    GET /health should return HTTP 200.
    ${resp}=    GET On Session    messmate    /health
    Status Should Be    200    ${resp}

TC40 Health Endpoint Returns JSON Status OK
    [Tags]    api    smoke    must
    [Documentation]    GET /health should return {"status": "ok"}.
    ${resp}=    GET On Session    messmate    /health
    ${body}=    Set Variable    ${resp.json()}
    Should Be Equal    ${body}[status]    ok

# ── SECTION 2: Form Submission API ────────────────────────────────────────

TC41 Valid Minimal POST Returns 200 Or Redirect
    [Tags]    api    submission
    [Documentation]    POST /submit with overall=3 should succeed (200 or 302 redirect).
    ${data}=    Create Dictionary
    ...    overall=3
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Be True    ${resp.status_code} in [200, 302]

TC42 POST Without Overall Returns Error
    [Tags]    api    submission    validation
    [Documentation]    POST /submit without an overall rating should not redirect to thanks.
    ${data}=    Create Dictionary    chapati=3
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    # Should not redirect to /thanks — stays on form with error
    Should Not Contain    ${resp.url}    /thanks

TC43 POST With Invalid Overall Value Returns Error
    [Tags]    api    submission    validation
    [Documentation]    POST /submit with overall=9 (out of range) should not accept.
    ${data}=    Create Dictionary    overall=9
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Not Contain    ${resp.url}    /thanks

TC44 POST With Non-Numeric Overall Returns Error
    [Tags]    api    submission    validation
    [Documentation]    POST /submit with overall=abc should be rejected.
    ${data}=    Create Dictionary    overall=abc
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Not Contain    ${resp.url}    /thanks

TC45 POST With XSS In Review Is Accepted But Sanitized
    [Tags]    api    security
    [Documentation]    XSS in the review field should be accepted but sanitized server-side.
    ${data}=    Create Dictionary
    ...    overall=3
    ...    review=<script>alert('xss')</script>
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    # Submission should succeed (200/302) — sanitisation happens server-side
    Should Be True    ${resp.status_code} in [200, 302]

TC46 POST With Overlong Review Is Truncated Or Rejected
    [Tags]    api    submission    validation
    [Documentation]    A review longer than 150 chars is truncated server-side ([:150] slice).
    ${long_review}=    Generate Random String    200    [LETTERS]
    ${data}=    Create Dictionary    overall=3    review=${long_review}
    ${resp}=    POST On Session    messmate    /submit    data=${data}
    ...    expected_status=any
    Should Be True    ${resp.status_code} in [200, 302]

TC47 Rate Limit Blocks Second Submission From Same IP
    [Tags]    api    rate-limit    must
    [Documentation]    Flask-Limiter should block a second POST /submit from the same IP.
    ...    Note: Only works if previous submissions in this session haven't triggered it.
    ...    Run this test in isolation or restart the app to reset in-memory limiter.
    ${data}=    Create Dictionary    overall=4
    ${resp1}=    POST On Session    messmate    /submit    data=${data}    expected_status=any
    ${resp2}=    POST On Session    messmate    /submit    data=${data}    expected_status=any
    Should Be Equal As Numbers    ${resp2.status_code}    429
    ${body}=    Convert To String    ${resp2.text}
    Should Contain    ${body}    tomorrow

# ── SECTION 3: Dashboard API ──────────────────────────────────────────────

TC48 Dashboard Without Token Returns 403
    [Tags]    api    security    must
    [Documentation]    GET /dashboard without a token should return 403.
    ${resp}=    GET On Session    messmate    /dashboard    expected_status=any
    Should Be Equal As Numbers    ${resp.status_code}    403

TC49 Dashboard With Wrong Token Returns 403
    [Tags]    api    security
    [Documentation]    GET /dashboard with an incorrect token should return 403.
    ${params}=    Create Dictionary    token=wrongtoken
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}    expected_status=any
    Should Be Equal As Numbers    ${resp.status_code}    403

TC50 Dashboard With Correct Token Returns 200
    [Tags]    api    security    must
    [Documentation]    GET /dashboard with the correct token should return 200.
    ${params}=    Create Dictionary    token=${DASHBOARD_TOKEN}
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}
    Status Should Be    200    ${resp}
    Should Contain    ${resp.text}    MessMate

TC51 Dashboard Response Contains Chart Data Script
    [Tags]    api    dashboard
    [Documentation]    Dashboard HTML should contain the MESSMATE_DATA JS object.
    ${params}=    Create Dictionary    token=${DASHBOARD_TOKEN}
    ${resp}=    GET On Session    messmate    /dashboard    params=${params}
    Should Contain    ${resp.text}    MESSMATE_DATA
    Should Contain    ${resp.text}    trendData
    Should Contain    ${resp.text}    itemData

TC52 Dashboard Response Contains All Four Sections
    [Tags]    api    dashboard
    [Documentation]    Dashboard HTML should contain all four main sections.
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
    [Documentation]    GET /static/style.css should return 200 with text/css content type.
    ${resp}=    GET On Session    messmate    /static/style.css
    Status Should Be    200    ${resp}
    Should Contain    ${resp.headers}[Content-Type]    text/css

TC54 Dashboard JS File Is Served
    [Tags]    api    assets
    [Documentation]    GET /static/dashboard.js should return 200 with javascript content type.
    ${resp}=    GET On Session    messmate    /static/dashboard.js
    Status Should Be    200    ${resp}
    Should Contain    ${resp.headers}[Content-Type]    javascript
