*** Settings ***
Documentation     Shared keywords for the Food Committee UI suites — member
...               login, the rating widget, and the admin roster.
Library           SeleniumLibrary
Library           RequestsLibrary
Library           Collections
Library           String
Resource          common.resource

*** Variables ***
${COMMITTEE_LOGIN_URL}    ${BASE_URL}/committee/login
${COMMITTEE_URL}          ${BASE_URL}/committee
${COMMITTEE_PW_URL}       ${BASE_URL}/committee/password
${ADMIN_LOGIN_URL}        ${BASE_URL}/admin/login
${ADMIN_MEMBERS_URL}      ${BASE_URL}/admin/members
${COMMITTEE_DASH_URL}     ${BASE_URL}/dashboard/committee?token=${DASHBOARD_TOKEN}

# Fixture identities. test/fake_server.py seeds exactly these; against a real
# spreadsheet, seed matching robot-test-* members or override via environment.
${ADMIN_PASSWORD}          %{ADMIN_PASSWORD=admin-test-password}
${MEMBER_EMAIL}            %{TEST_COMMITTEE_EMAIL=robot-test-member@sai.edu}
${MEMBER_PASSWORD}         %{TEST_COMMITTEE_PASSWORD=robot-test-password}
${NEWBIE_EMAIL}            robot-test-newbie@sai.edu
${NEWBIE_PASSWORD}         robot-test-newbie
${RETIRED_EMAIL}           robot-test-retired@sai.edu
${RETIRED_PASSWORD}        robot-test-retired
${RATED_EMAIL}             robot-test-rated@sai.edu
${RATED_PASSWORD}          robot-test-rated

@{DIMENSIONS}    taste    quality    variety    hygiene    menu

*** Keywords ***
Reset Test Fixture
    [Documentation]    Restores the seeded fixture so suites are order-independent.
    ...    Only test/fake_server.py exposes this route; against a real
    ...    spreadsheet it is absent and the call is skipped.
    ${status}    ${response}=    Run Keyword And Ignore Error
    ...    POST    ${BASE_URL}/__test__/reset    expected_status=any
    Run Keyword If    '${status}' == 'FAIL'
    ...    Log    Fixture reset unavailable — running against a live sheet.    level=WARN

Start With A Clean Session
    [Documentation]    Resets the fixture AND drops the browser's cookies, so each
    ...    test starts signed out. Without this a leftover session makes
    ...    /committee/login redirect straight to the rating page — correct
    ...    behaviour that would otherwise look like a broken login form.
    Reset Test Fixture
    Go To    ${BASE_URL}/health
    Delete All Cookies

Skip If Charts Unavailable
    [Documentation]    Chart.js is loaded from a CDN. On a network that blocks it
    ...    the canvases stay empty — an environment condition, not a defect — so
    ...    chart assertions skip with a clear reason instead of failing.
    ${loaded}=    Execute JavaScript    return typeof Chart !== 'undefined'
    Skip If    not ${loaded}    Chart.js CDN unreachable from this network.

# ── Member session ────────────────────────────────────────────────────────────

Navigate To Committee Login
    [Documentation]    Opens the committee login page.
    Go To    ${COMMITTEE_LOGIN_URL}
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}

Sign Out Of Committee
    [Documentation]    Clears any member session by posting the logout form.
    Go To    ${COMMITTEE_URL}
    ${signed_in}=    Run Keyword And Return Status
    ...    Page Should Contain Element    css=button.link-btn
    Run Keyword If    ${signed_in}    Click Element    css=button.link-btn

Login As Committee Member
    [Arguments]    ${email}=${MEMBER_EMAIL}    ${password}=${MEMBER_PASSWORD}
    [Documentation]    Submits the committee login form. Does not assert the outcome —
    ...    callers check for the rating page, the password page, or an error.
    Navigate To Committee Login
    Input Text       id=email       ${email}
    Input Password   id=password    ${password}
    Click Element    id=login-btn

Login And Reach Rating Page
    [Arguments]    ${email}=${MEMBER_EMAIL}    ${password}=${MEMBER_PASSWORD}
    [Documentation]    Signs in and waits for the rating form to be ready.
    Login As Committee Member    ${email}    ${password}
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}

# ── Rating widget ─────────────────────────────────────────────────────────────

Rate Dimension
    [Arguments]    ${dimension}    ${score}
    [Documentation]    Clicks the emoji button for one dimension (1-5).
    Click Element    css=.emoji-btn[data-item="${dimension}"][data-value="${score}"]

Rate All Dimensions
    [Arguments]    ${score}=4
    [Documentation]    Rates all five dimensions with the same score.
    FOR    ${dimension}    IN    @{DIMENSIONS}
        Rate Dimension    ${dimension}    ${score}
    END

Dimension Hidden Value Should Be
    [Arguments]    ${dimension}    ${expected}
    [Documentation]    Asserts the hidden input the emoji widget writes into.
    ${value}=    Get Element Attribute    id=${dimension}_val    value
    Should Be Equal    ${value}    ${expected}

Submit Committee Review
    [Documentation]    Submits the rating form and waits for the confirmation page.
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.thanks-container    timeout=${TIMEOUT}

# ── Admin session ─────────────────────────────────────────────────────────────

Login As Admin
    [Documentation]    Signs in to the admin roster UI.
    Go To    ${ADMIN_LOGIN_URL}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Input Password   id=password    ${ADMIN_PASSWORD}
    Click Element    id=admin-login-btn
    Wait Until Page Contains Element    id=add-member-form    timeout=${TIMEOUT}

Sign Out Of Admin
    [Documentation]    Clears the admin session if one is active, and waits for
    ...    the sign-out to land. Without the wait the next Go To can race the
    ...    logout POST and the following assertion fails intermittently.
    Go To    ${ADMIN_MEMBERS_URL}
    ${signed_in}=    Run Keyword And Return Status
    ...    Page Should Contain Element    xpath=//button[text()='Sign out']
    Run Keyword If    ${signed_in}    Run Keywords
    ...    Click Element    xpath=//button[text()='Sign out']
    ...    AND    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}

Add Member Via UI
    [Arguments]    ${name}    ${email}
    [Documentation]    Fills and submits the single-member add form, then waits
    ...    for the outcome banner — success or rejection. Returning before the
    ...    POST lands lets a following navigation race it.
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=add-member-form    timeout=${TIMEOUT}
    Input Text       id=name     ${name}
    Input Text       id=email    ${email}
    Click Element    id=add-btn
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}

Bulk Add Members Via UI
    [Arguments]    ${lines}
    [Documentation]    Pastes a block of 'Name, email' lines into the bulk form.
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=bulk-add-form    timeout=${TIMEOUT}
    Input Text       id=bulk-members    ${lines}
    Click Element    id=bulk-add-btn
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}

Get Revealed Password
    [Arguments]    ${email}
    [Documentation]    Reads a one-time password out of the credential banner.
    ...    This is the only place the password is ever visible.
    Wait Until Page Contains Element    css=.credential-banner    timeout=${TIMEOUT}
    ${password}=    Get Text
    ...    xpath=//table[@class='credential-table']//td[normalize-space()='${email}']/following-sibling::td/code
    RETURN    ${password}

Act On Member
    [Arguments]    ${email}    ${action}
    [Documentation]    Clicks a per-row action: deactivate, activate, or reset,
    ...    then waits for the resulting banner. Every mutation re-renders the
    ...    roster with one, so this is the signal that the write actually
    ...    landed — without it a following sign-in can race the POST and the
    ...    assertion fails intermittently.
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=members-table    timeout=${TIMEOUT}
    Click Element    xpath=//tr[@data-member-row='${email}']//button[@value='${action}']
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}

Member Row Should Show Status
    [Arguments]    ${email}    ${badge_class}
    [Documentation]    Asserts a roster row carries the expected status badge.
    Page Should Contain Element
    ...    xpath=//tr[@data-member-row='${email}']//span[contains(@class,'${badge_class}')]

Roster Should Contain Member
    [Arguments]    ${email}
    Page Should Contain Element    xpath=//tr[@data-member-row='${email}']

Roster Should Not Contain Member
    [Arguments]    ${email}
    Page Should Not Contain Element    xpath=//tr[@data-member-row='${email}']
