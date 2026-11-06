*** Settings ***
Documentation     Shared keywords for the end-to-end journey suites.
...
...               Each journey suite is one story told in order: its test cases
...               are consecutive steps that share a browser and fixture state.
...               A failed step marks the journey broken and every later step
...               SKIPS with that reason, so the report points at the first real
...               failure instead of a cascade of follow-on ones.
...
...               These suites need test/fake_server.py: they reset the fixture,
...               switch rate limits on and off, simulate a Sheets outage, and
...               read back what was stored. Against any other server they skip
...               rather than write into a real spreadsheet.
Library           SeleniumLibrary
Library           RequestsLibrary
Library           Collections
Library           String
Library           DateTime
Resource          ../../resources/common.resource
Resource          ../../resources/committee_keywords.resource

*** Variables ***
${HOME_URL}             ${BASE_URL}/home
${MENU_EDITOR_URL}      ${BASE_URL}/admin/menu
${JOURNEY_BROKEN}       ${FALSE}

# Column order of the anonymous tabs. Asserted exactly: a new column here is
# the first place an identifying field (an IP, a user agent) would appear.
@{RESPONSE_HEADERS}     Timestamp    Overall    Rice_Curry    Rice_Rasam    Chapati
...                     Chapati_Gravy    Poriyal    Sweet    Salad    Curd    Papad
...                     Pickle    Review    Suggestion
@{MEAL_RATING_HEADERS}  Timestamp    Date    Meal    Rating    Suggestion

*** Keywords ***
# ── Journey plumbing ──────────────────────────────────────────────────────────

Begin Journey
    [Documentation]    Suite setup for every journey: confirm the test server,
    ...    restore the fixture, and open one browser for the whole story.
    Require E2E Test Server
    Reset Test Fixture
    Open MessMate Browser
    Set Suite Variable    ${JOURNEY_BROKEN}    ${FALSE}

End Journey
    [Documentation]    Suite teardown: leave the server as the next suite expects.
    Run Keyword And Ignore Error    Reset Test Fixture
    Close All Browsers
    Delete All Sessions

Continue Journey
    [Documentation]    Test setup: skip this step if an earlier one failed.
    Skip If    ${JOURNEY_BROKEN}    An earlier step in this journey failed; see the first FAIL.

Record Step Outcome
    [Documentation]    Test teardown: a failure breaks the rest of the journey.
    Run Keyword If Test Failed    Set Suite Variable    ${JOURNEY_BROKEN}    ${TRUE}

Require E2E Test Server
    [Documentation]    Skips the whole suite unless BASE_URL is test/fake_server.py.
    ...    The journeys mutate state freely; against a live spreadsheet that
    ...    would mean writing test reviews into production data.
    ${status}    ${response}=    Run Keyword And Ignore Error
    ...    GET    ${BASE_URL}/__test__/sheet/menu    expected_status=200
    Skip If    '${status}' == 'FAIL'
    ...    End-to-end suites need test/fake_server.py at ${BASE_URL} (python test/fake_server.py 5001).

Today
    ${today}=    Get Current Date    result_format=%Y-%m-%d
    RETURN    ${today}

Days From Today
    [Arguments]    ${days}
    ${date}=    Get Current Date    increment=${days} days    result_format=%Y-%m-%d
    RETURN    ${date}

# ── Test-server controls ──────────────────────────────────────────────────────

Turn Rate Limits On
    [Documentation]    Switches the production caps on with empty counters.
    POST    ${BASE_URL}/__test__/limiter    params=enabled=1    expected_status=200

Turn Rate Limits Off
    POST    ${BASE_URL}/__test__/limiter    params=enabled=0    expected_status=200

Simulate Sheets Backend
    [Arguments]    ${mode}
    [Documentation]    ok | raise (get_sheet throws) | unavailable (returns None).
    POST    ${BASE_URL}/__test__/backend    params=mode=${mode}    expected_status=200

Get Stored Rows
    [Arguments]    ${tab}
    [Documentation]    Every row stored in a tab, as a list of dicts.
    ${response}=    GET    ${BASE_URL}/__test__/sheet/${tab}    expected_status=200
    RETURN    ${response.json()}[rows]

Get Stored Headers
    [Arguments]    ${tab}
    ${response}=    GET    ${BASE_URL}/__test__/sheet/${tab}    expected_status=200
    RETURN    ${response.json()}[headers]

Stored Row Count Should Be
    [Arguments]    ${tab}    ${expected}
    ${rows}=    Get Stored Rows    ${tab}
    Length Should Be    ${rows}    ${expected}

Get Last Stored Row
    [Arguments]    ${tab}
    ${rows}=    Get Stored Rows    ${tab}
    Should Not Be Empty    ${rows}    No rows stored in ${tab}.
    RETURN    ${rows}[-1]

Get Stored Rows Where
    [Arguments]    ${tab}    ${column}    ${value}
    ${rows}=    Get Stored Rows    ${tab}
    @{matches}=    Create List
    FOR    ${row}    IN    @{rows}
        ${cell}=    Get From Dictionary    ${row}    ${column}    default=${EMPTY}
        IF    '${cell}' == '${value}'    Append To List    ${matches}    ${row}
    END
    RETURN    ${matches}

Get Stored Member
    [Arguments]    ${email}
    ${matches}=    Get Stored Rows Where    committee_members    Email    ${email}
    Length Should Be    ${matches}    1    Expected exactly one roster row for ${email}.
    RETURN    ${matches}[0]

# ── HTTP sessions (no browser) ────────────────────────────────────────────────
# A RequestsLibrary session keeps its own cookie jar, so each alias is an
# independent visitor — handy for proving what a second person does or does
# not see while the browser is signed in as someone else.

Open Visitor Session
    [Arguments]    ${alias}
    Create Session    ${alias}    ${BASE_URL}    disable_warnings=1

Get Csrf Token
    [Arguments]    ${alias}    ${path}
    [Documentation]    Loads a page in that session and returns its CSRF token.
    ${response}=    GET On Session    ${alias}    ${path}    expected_status=200
    ${matches}=    Get Regexp Matches    ${response.text}
    ...    name="csrf_token" value="([^"]+)"    1
    Should Not Be Empty    ${matches}    No CSRF token found on ${path}.
    RETURN    ${matches}[0]

Session Admin Login
    [Arguments]    ${alias}    ${password}=${ADMIN_PASSWORD}
    ${token}=    Get Csrf Token    ${alias}    /admin/login
    ${response}=    POST On Session    ${alias}    /admin/login
    ...    data=${{ {'password': $password, 'csrf_token': $token} }}
    ...    allow_redirects=${FALSE}    expected_status=any
    RETURN    ${response}

Session Member Login
    [Arguments]    ${alias}    ${email}    ${password}
    ${token}=    Get Csrf Token    ${alias}    /committee/login
    ${response}=    POST On Session    ${alias}    /committee/login
    ...    data=${{ {'email': $email, 'password': $password, 'csrf_token': $token} }}
    ...    allow_redirects=${FALSE}    expected_status=any
    RETURN    ${response}

Response Should Redirect To
    [Arguments]    ${response}    ${path}
    Should Be True    ${response.status_code} in (301, 302, 303)
    ...    Expected a redirect, got ${response.status_code}.
    Should Contain    ${response.headers}[Location]    ${path}

Get Without Redirect
    [Arguments]    ${alias}    ${path}
    ${response}=    GET On Session    ${alias}    ${path}
    ...    allow_redirects=${FALSE}    expected_status=any
    RETURN    ${response}

Submit Student Feedback Over HTTP
    [Arguments]    ${alias}    &{fields}
    [Documentation]    Posts the per-dish form directly. /submit carries no CSRF
    ...    token by design: it is anonymous and has no session to forge.
    ${response}=    POST On Session    ${alias}    /submit    data=${fields}
    ...    allow_redirects=${FALSE}    expected_status=any
    RETURN    ${response}

Tap Meal Over HTTP
    [Arguments]    ${alias}    ${meal}    ${rating}    ${suggestion}=${EMPTY}
    ${response}=    POST On Session    ${alias}    /home/rate
    ...    data=${{ {'meal': $meal, 'rating': $rating, 'suggestion': $suggestion} }}
    ...    allow_redirects=${FALSE}    expected_status=any
    RETURN    ${response}

# ── Browser: student ──────────────────────────────────────────────────────────

Become A New Visitor
    [Documentation]    Drops every cookie, as if a different person picked up a phone.
    Go To    ${BASE_URL}/health
    Delete All Cookies

Open Student Home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}

Choose Rice Served
    [Arguments]    ${option}
    Select From List By Value    id=rice_served    ${option}

Type Review
    [Arguments]    ${text}
    Input Text    id=review    ${text}

Type Suggestion
    [Arguments]    ${text}
    Input Text    css=input[name="suggestion"]    ${text}

Tap Meal Reaction
    [Arguments]    ${meal}    ${rating}    ${suggestion}=${EMPTY}
    [Documentation]    Taps good / bad / skip on one meal card, optionally after
    ...    opening the suggestion disclosure and typing into it.
    ${card}=    Set Variable    css=.meal-card[data-meal="${meal}"]
    IF    $suggestion
        Click Element    ${card} summary
        Input Text    ${card} .suggestion-input    ${suggestion}
    END
    Click Element    ${card} .rate-btn[data-rating="${rating}"]
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}

Meal Tally Should Be
    [Arguments]    ${meal}    ${score}    ${total}
    ${card}=    Set Variable    css=.meal-card[data-meal="${meal}"]
    Element Text Should Be    ${card} .tally-score    ${score}
    Element Text Should Be    ${card} .tally-count    ${total} rated

Meal Should Have No Tally
    [Arguments]    ${meal}
    Page Should Not Contain Element    css=.meal-card[data-meal="${meal}"] .meal-tally

Menu Items Should Be
    [Arguments]    ${meal}    @{expected}
    ${elements}=    Get WebElements    css=#menu-${meal.lower()} li
    ${actual}=    Evaluate    [e.text.strip() for e in $elements]
    Lists Should Be Equal    ${actual}    ${expected}

# ── Browser: dashboards ───────────────────────────────────────────────────────

Open Student Dashboard
    Go To    ${DASHBOARD_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}

Student Stat Should Be
    [Arguments]    ${heading}    ${expected}
    Element Text Should Be
    ...    xpath=//div[@class='stat-cards']//h3[normalize-space()="${heading}"]/following-sibling::p
    ...    ${expected}

Open Committee Dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}

First Feed Entry Should Be
    [Arguments]    ${text}    ${byline}
    Element Text Should Be    css=.suggestions-list .suggestion-item:first-child .suggestion-text
    ...    "${text}"
    Element Should Contain    css=.suggestions-list .suggestion-item:first-child .suggestion-time
    ...    ${byline}

# ── Browser: committee ────────────────────────────────────────────────────────

Choose New Password
    [Arguments]    ${password}    ${confirm}=${password}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Input Password    id=password    ${password}
    Input Password    id=confirm     ${confirm}
    Click Element     id=password-btn

Rate Committee Dimensions
    [Arguments]    ${taste}    ${quality}    ${variety}    ${hygiene}    ${menu}
    Rate Dimension    taste      ${taste}
    Rate Dimension    quality    ${quality}
    Rate Dimension    variety    ${variety}
    Rate Dimension    hygiene    ${hygiene}
    Rate Dimension    menu       ${menu}

Login Should Be Refused
    [Documentation]    The one generic message — never a hint about which part was wrong.
    Wait Until Page Contains Element    css=.error-banner    timeout=${TIMEOUT}
    Element Text Should Be    css=.error-banner    Incorrect email or password.
    Location Should Contain    /committee/login

# ── Browser: admin ────────────────────────────────────────────────────────────

Open Menu Editor
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}

Publish Menu
    [Arguments]    ${date}    ${breakfast}=${NONE}    ${lunch}=${NONE}    ${dinner}=${NONE}
    [Documentation]    Edits one day in the editor and saves it. A meal left as
    ...    NONE keeps whatever is already in its field.
    Open Menu Editor
    FOR    ${meal}    ${value}    IN    Breakfast    ${breakfast}    Lunch    ${lunch}    Dinner    ${dinner}
        IF    $value is not None
            Clear Element Text    id=${date}-${meal}
            Input Text    id=${date}-${meal}    ${value}
        END
    END
    Click Element    css=form[data-menu-day="${date}"] button[type="submit"]
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}
