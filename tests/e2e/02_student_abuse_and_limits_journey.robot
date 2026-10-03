*** Settings ***
Documentation     Journey 2 — hostile and repeated student input.
...
...               A script-injection attempt through the browser, followed all the
...               way to the dashboard; malformed posts sent straight at the
...               server; then the production rate limits switched back on to
...               prove the 1-per-day form cap and the 3-per-day meal cap hold.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    student    security

*** Variables ***
${XSS_REVIEW}         <script>window.__xssReview = 1</script>
${XSS_SUGGESTION}     <img src=x onerror="window.__xssSuggestion = 1">

*** Test Cases ***
E02.01 Student Submits Markup In Both Free-Text Fields
    Navigate To Form
    Select Overall Emoji    2
    Type Review        ${XSS_REVIEW}
    Type Suggestion    ${XSS_SUGGESTION}
    Submit Form

E02.02 Review Is Stored Escaped And Suggestion Raw
    [Documentation]    Review is escaped on write; Suggestion is left for Jinja to
    ...    escape on render. Escaping both would show admins a literal "&lt;".
    ${row}=    Get Last Stored Row    responses
    Should Not Contain    ${row}[Review]    <script>
    Should Contain        ${row}[Review]    &lt;script&gt;
    Should Be Equal       ${row}[Suggestion]    ${XSS_SUGGESTION}

E02.03 Dashboard Shows The Markup As Text And Runs None Of It
    Open Student Dashboard
    Element Text Should Be    css=.suggestions-list .suggestion-item:first-child .suggestion-text
    ...    "${XSS_SUGGESTION}"
    Page Should Not Contain Element    css=.suggestions-list img
    ${ran}=    Execute JavaScript
    ...    return Boolean(window.__xssSuggestion || window.__xssReview)
    Should Not Be True    ${ran}    Injected script executed on the dashboard.

E02.04 A Post Without An Overall Rating Is Refused And Not Stored
    [Tags]    validation
    Open Visitor Session    raw
    ${before}=    Get Stored Rows    responses
    ${response}=    Submit Student Feedback Over HTTP    raw    chapati=4    review=no overall
    Should Be Equal As Integers    ${response.status_code}    200
    Should Contain    ${response.text}    Overall rating is required.
    ${after}=    Get Stored Rows    responses
    Should Be Equal    ${before}    ${after}

E02.05 Out-Of-Range And Non-Numeric Ratings Never Reach The Sheet
    [Tags]    validation
    [Documentation]    "seven" and "-1" are not digit strings, so they are refused
    ...    as overall and stored blank as items rather than as junk.
    ${response}=    Submit Student Feedback Over HTTP    raw    overall=seven
    Should Contain    ${response.text}    Overall rating is required.
    ${response}=    Submit Student Feedback Over HTTP    raw    overall=-1
    Should Contain    ${response.text}    Overall rating is required.
    ${response}=    Submit Student Feedback Over HTTP    raw    overall=3    poriyal=great    sweet=-2
    Response Should Redirect To    ${response}    /thanks
    ${row}=    Get Last Stored Row    responses
    Should Be Equal    ${row}[Poriyal]    ${EMPTY}
    Should Be Equal    ${row}[Sweet]      ${EMPTY}

E02.06 An Overlong Review Is Truncated To 150 Characters
    [Tags]    validation
    [Documentation]    The textarea's maxlength is client-side only; the server
    ...    must enforce it too.
    ${long}=    Evaluate    'x' * 400
    ${response}=    Submit Student Feedback Over HTTP    raw    overall=4    review=${long}
    Response Should Redirect To    ${response}    /thanks
    ${row}=    Get Last Stored Row    responses
    Length Should Be    ${row}[Review]    150

E02.07 The Browser Form Also Caps The Review At 150
    Navigate To Form
    ${long}=    Evaluate    'y' * 200
    Type Review    ${long}
    ${value}=    Get Value    id=review
    Length Should Be    ${value}    150
    Element Text Should Be    id=char-counter    150 / 150

E02.08 With Limits On, A Second Form Submission Is Turned Away
    [Tags]    rate-limit
    Turn Rate Limits On
    ${before}=    Get Stored Rows    responses
    ${first}=    Submit Student Feedback Over HTTP    raw    overall=5
    Response Should Redirect To    ${first}    /thanks
    ${second}=    Submit Student Feedback Over HTTP    raw    overall=1
    Should Be Equal As Integers    ${second.status_code}    429
    Should Contain    ${second.text}    already submitted feedback for today
    ${after}=    Get Stored Rows    responses
    ${added}=    Evaluate    len($after) - len($before)
    Should Be Equal As Integers    ${added}    1    Only the first submission may be stored.

E02.09 The Browser Shows The Limit As A Friendly Banner, Not An Error Page
    [Tags]    rate-limit
    Navigate To Form
    Select Overall Emoji    3
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.error-banner    timeout=${TIMEOUT}
    Element Should Contain    css=.error-banner    Come back tomorrow
    Page Should Contain Element    id=feedbackForm

E02.10 Meal Reactions Allow Three A Day, One Per Meal
    [Tags]    rate-limit    home
    ${before}=    Get Stored Rows    meal_ratings
    FOR    ${meal}    IN    Breakfast    Lunch    Dinner
        ${response}=    Tap Meal Over HTTP    raw    ${meal}    good
        Response Should Redirect To    ${response}    rated=${meal.lower()}
    END
    ${fourth}=    Tap Meal Over HTTP    raw    Lunch    bad
    Should Be Equal As Integers    ${fourth.status_code}    429
    ${after}=    Get Stored Rows    meal_ratings
    ${added}=    Evaluate    len($after) - len($before)
    Should Be Equal As Integers    ${added}    3

E02.11 The Limits Do Not Touch Read-Only Pages
    [Tags]    rate-limit
    FOR    ${path}    IN    /    /home    /health    /thanks
        GET On Session    raw    ${path}    expected_status=200
    END
    [Teardown]    Run Keywords    Turn Rate Limits Off    AND    Record Step Outcome
