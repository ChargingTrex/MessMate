*** Settings ***
Documentation     Committee dashboard UI tests: access control, stat cards,
...               Chart.js rendering, the 7/30-day toggle, the review feed,
...               and separation from the student dashboard.
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Run Keywords    Reset Test Fixture    AND    Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Start With A Clean Session

*** Test Cases ***

# ── SECTION 1: Access control ─────────────────────────────────────────────

TC120 Dashboard Without A Credential Is Denied
    [Tags]    smoke    dashboard    security
    Sign Out Of Admin
    Go To    ${BASE_URL}/dashboard/committee
    Page Should Contain    Access denied

TC121 Dashboard With A Wrong Token Is Denied
    [Tags]    dashboard    security
    Go To    ${BASE_URL}/dashboard/committee?token=not-the-token
    Page Should Contain    Access denied

TC122 Dashboard Opens With The Read-Only Token
    [Tags]    smoke    dashboard
    [Documentation]    The token keeps working for viewing, which is what it is for.
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Title Should Be    MessMate — Committee Dashboard 🍽️

TC123 Dashboard Opens With An Admin Session
    [Tags]    dashboard
    Login As Admin
    Go To    ${BASE_URL}/dashboard/committee
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}

TC124 Admin Session Sees The Manage Members Link
    [Tags]    dashboard
    Login As Admin
    Go To    ${BASE_URL}/dashboard/committee
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Contain Element    xpath=//a[contains(@href,'/admin/members')]

TC125 Token Holder Is Not Shown The Manage Members Link
    [Tags]    dashboard    security
    [Documentation]    A token holder should not be shown a door they cannot open.
    ...    Split from TC104 so each assertion starts from a clean session rather
    ...    than depending on a sign-out mid-test.
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Not Contain Element    xpath=//a[contains(@href,'/admin/members')]

# ── SECTION 2: Stat cards ─────────────────────────────────────────────────

TC126 All Four Stat Cards Render
    [Tags]    smoke    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Contain Element    id=stat-today-avg
    Page Should Contain Element    id=stat-today-count
    Page Should Contain Element    id=stat-active-members
    Page Should Contain Element    id=stat-participation

TC127 Today's Score Reflects The Seeded Review
    [Tags]    dashboard
    [Documentation]    The fixture has one review today scoring 4,4,3,5,4 — mean 4.0.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=stat-today-avg    timeout=${TIMEOUT}
    ${score}=    Get Text    id=stat-today-avg
    Should Be Equal    ${score}    4.0

TC128 Response Count Matches The Reviews Filed Today
    [Tags]    dashboard
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=stat-today-count    timeout=${TIMEOUT}
    ${count}=    Get Text    id=stat-today-count
    Should Be Equal    ${count}    1

TC129 Active Member Count Excludes Retired Members
    [Tags]    dashboard
    [Documentation]    The fixture has four members, one of them deactivated.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=stat-active-members    timeout=${TIMEOUT}
    ${active}=    Get Text    id=stat-active-members
    Should Be Equal    ${active}    3

TC130 Participation Is A Percentage Of Active Members
    [Tags]    dashboard
    [Documentation]    One review from three active members is 33%.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=stat-participation    timeout=${TIMEOUT}
    ${participation}=    Get Text    id=stat-participation
    Should Be Equal    ${participation}    33%

TC131 Score Card Is Colour Coded
    [Tags]    dashboard
    [Documentation]    Same red/amber/green thresholds as the student dashboard.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Contain Element    css=.stat-card.score-green

# ── SECTION 3: Charts ─────────────────────────────────────────────────────

TC132 Both Chart Canvases Render
    [Tags]    smoke    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=dimensionChart    timeout=${TIMEOUT}
    Page Should Contain Element    id=committeeTrendChart

TC133 Chart.js Actually Draws The Dimension Chart
    [Tags]    dashboard
    [Documentation]    Asserts a real Chart instance exists, not just a canvas tag.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=dimensionChart    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    ${drawn}=    Execute JavaScript
    ...    return Chart.getChart('dimensionChart') !== undefined
    Should Be True    ${drawn}

TC134 The Dimension Chart Plots All Five Areas
    [Tags]    dashboard
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=dimensionChart    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    ${labels}=    Execute JavaScript
    ...    return Chart.getChart('dimensionChart').data.labels
    Length Should Be    ${labels}    5
    Should Contain    ${labels}    Taste
    Should Contain    ${labels}    Hygiene

TC135 The Trend Chart Carries Overall Plus Each Dimension
    [Tags]    dashboard
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=committeeTrendChart    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    ${datasets}=    Execute JavaScript
    ...    return Chart.getChart('committeeTrendChart').data.datasets.map(d => d.label)
    Length Should Be    ${datasets}    6
    Should Contain    ${datasets}    Overall

TC136 Per-Dimension Trend Lines Start Hidden
    [Tags]    dashboard
    [Documentation]    Six lines at once is unreadable; the overall trend leads
    ...    and the rest are opt-in through the legend.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=committeeTrendChart    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    ${hidden}=    Execute JavaScript
    ...    return Chart.getChart('committeeTrendChart').data.datasets.slice(1).every(d => d.hidden === true)
    Should Be True    ${hidden}

TC137 Trend Toggle Buttons Render
    [Tags]    smoke    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Page Should Contain Element    id=btnCommittee7
    Page Should Contain Element    id=btnCommittee30

TC138 Seven Day View Is Active By Default
    [Tags]    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=btnCommittee7    timeout=${TIMEOUT}
    Element Should Have Class        id=btnCommittee7     active
    Element Should Not Have Class    id=btnCommittee30    active
    Element Text Should Be    id=committeeTrendTitle    7-Day Committee Trend

TC139 Switching To One Month Updates The Chart Title
    [Tags]    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=btnCommittee30    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    Click Element    id=btnCommittee30
    Element Should Have Class        id=btnCommittee30    active
    Element Should Not Have Class    id=btnCommittee7     active
    Element Text Should Be    id=committeeTrendTitle    30-Day Committee Trend

TC140 Toggling Back To Seven Days Restores The View
    [Tags]    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    id=btnCommittee30    timeout=${TIMEOUT}
    Skip If Charts Unavailable
    Click Element    id=btnCommittee30
    Click Element    id=btnCommittee7
    Element Should Have Class    id=btnCommittee7    active
    Element Text Should Be    id=committeeTrendTitle    7-Day Committee Trend

# ── SECTION 4: Review feed ────────────────────────────────────────────────

TC141 Review Feed Renders With Attribution
    [Tags]    smoke    dashboard
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.suggestions-list    timeout=${TIMEOUT}
    Page Should Contain    Already reviewed earlier today
    Page Should Contain    Robot Test Rated

TC142 Review Feed Is Newest First
    [Tags]    dashboard
    [Documentation]    Ordering comes from the Date column, not the sheet's
    ...    physical row order.
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.suggestions-list    timeout=${TIMEOUT}
    ${first}=    Get Text    css=.suggestion-item:first-child .suggestion-text
    Should Contain    ${first}    Already reviewed earlier today

# ── SECTION 5: Separation from student data ───────────────────────────────

TC143 Student Dashboard Still Renders
    [Tags]    smoke    dashboard
    [Documentation]    Regression guard — the committee module must not touch it.
    Go To    ${BASE_URL}/dashboard?token=${DASHBOARD_TOKEN}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Contain Element    id=trendChart
    Page Should Contain Element    id=itemChart

TC144 Committee Reviews Do Not Appear On The Student Dashboard
    [Tags]    dashboard    security
    [Documentation]    A five-member committee average and a 200-student average
    ...    measure different things and are never mixed.
    Reset Test Fixture
    Go To    ${BASE_URL}/dashboard?token=${DASHBOARD_TOKEN}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Not Contain    Already reviewed earlier today
    Page Should Not Contain    Robot Test Rated

TC145 Student Feedback Does Not Appear On The Committee Dashboard
    [Tags]    dashboard
    Reset Test Fixture
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Not Contain    Student suggestion

TC146 The Two Dashboards Cross-Link
    [Tags]    dashboard
    Go To    ${COMMITTEE_DASH_URL}
    Page Should Contain Element    xpath=//a[contains(@href,'/dashboard')]
