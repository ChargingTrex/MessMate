*** Settings ***
Documentation     End-to-end tests for the Food Committee module: member login,
...               the five-dimension rating page, and the admin roster UI.
...
...               These require a live test spreadsheet. The pure-logic checks
...               run without credentials in test/test_committee.py.
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Open MessMate Browser
Suite Teardown    Run Keywords    Cleanup Test Members    AND    Close MessMate Browser

*** Variables ***
${NEW_MEMBER_EMAIL}    robot-test-new@sai.edu
${NEW_MEMBER_NAME}     Robot Test Member

*** Test Cases ***
Committee Login Page Loads
    [Documentation]    The login page renders and states that reviews are attributed.
    [Tags]    smoke    committee
    Navigate To Committee Login
    Page Should Contain Element    id=email
    Page Should Contain Element    id=password
    Page Should Contain    not anonymous

Valid Member Login Reaches The Rating Page
    [Documentation]    A known member signs in and sees all five dimensions.
    [Tags]    smoke    committee
    Login As Committee Member
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}
    FOR    ${dimension}    IN    taste    quality    variety    hygiene    menu
        Page Should Contain Element    css=.emoji-group[data-dimension="${dimension}"]
    END

Invalid Password Is Rejected
    [Documentation]    A wrong password shows the error banner and grants no access.
    [Tags]    smoke    committee
    Login As Committee Member    ${TEST_MEMBER_EMAIL}    definitely-wrong-password
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    Incorrect email or password

Unauthenticated Access Redirects To Login
    [Documentation]    /committee is not reachable without a session.
    [Tags]    smoke    committee
    Go To    ${BASE_URL}/committee/logout
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}
    Location Should Contain    /committee/login

Submit Button Stays Disabled Until All Five Are Rated
    [Documentation]    All five dimensions are required, unlike the student form
    ...    where per-item ratings are optional.
    [Tags]    committee
    Login As Committee Member
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}
    Element Should Be Disabled    id=submit-btn
    Rate Committee Dimension    taste      4
    Rate Committee Dimension    quality    4
    Rate Committee Dimension    variety    4
    Rate Committee Dimension    hygiene    4
    Element Should Be Disabled    id=submit-btn
    Rate Committee Dimension    menu       4
    Element Should Be Enabled    id=submit-btn

Admin Login Reaches The Roster
    [Documentation]    The admin password opens the member management UI.
    [Tags]    smoke    admin
    Login As Admin
    Page Should Contain Element    id=members-table
    Page Should Contain Element    id=add-member-form

Roster UI Refuses A Token-Only Request
    [Documentation]    The read-only ?token= credential must never reach the
    ...    roster UI — it leaks through history, referrers, and access logs.
    [Tags]    smoke    admin    security
    Go To    ${BASE_URL}/admin/logout
    Go To    ${BASE_URL}/admin/members?token=${DASHBOARD_TOKEN}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Location Should Contain    /admin/login
    Page Should Not Contain Element    id=members-table

Added Member Can Sign In With The Generated Password
    [Documentation]    The full add-then-login round trip, including the
    ...    forced password change on first sign-in.
    [Tags]    admin    committee
    Login As Admin
    Add Committee Member Via UI    ${NEW_MEMBER_NAME}    ${NEW_MEMBER_EMAIL}
    ${password}=    Get Revealed Password    ${NEW_MEMBER_EMAIL}
    Should Not Be Empty    ${password}

    Login As Committee Member    ${NEW_MEMBER_EMAIL}    ${password}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password
    [Teardown]    Deactivate Member    ${NEW_MEMBER_EMAIL}

Duplicate Email Is Rejected
    [Documentation]    An address already on the roster cannot be added twice.
    [Tags]    admin
    Login As Admin
    Add Committee Member Via UI    Duplicate One    robot-test-dupe@sai.edu
    Go To    ${ADMIN_MEMBERS_URL}
    Input Text       id=name     Duplicate Two
    Input Text       id=email    robot-test-dupe@sai.edu
    Click Element    id=add-btn
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    already on the roster
    [Teardown]    Deactivate Member    robot-test-dupe@sai.edu

Deactivated Member Cannot Sign In
    [Documentation]    Removal from the committee takes effect immediately.
    [Tags]    admin    security
    Login As Admin
    Add Committee Member Via UI    Rotating Out    robot-test-rotate@sai.edu
    ${password}=    Get Revealed Password    robot-test-rotate@sai.edu
    Deactivate Member    robot-test-rotate@sai.edu

    Login As Committee Member    robot-test-rotate@sai.edu    ${password}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    Incorrect email or password

Committee Dashboard Requires A Credential
    [Documentation]    No token and no session means no dashboard.
    [Tags]    smoke    api
    Go To    ${BASE_URL}/admin/logout
    ${response}=    GET    ${BASE_URL}/dashboard/committee    expected_status=403
    Should Be Equal As Integers    ${response.status_code}    403

Committee Dashboard Renders With A Token
    [Documentation]    The read-only credential still opens the dashboard.
    [Tags]    smoke    api
    Go To    ${COMMITTEE_DASH_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}
    Page Should Contain Element    id=dimensionChart
    Page Should Contain Element    id=committeeTrendChart

Health Endpoint Still Responds
    [Documentation]    Regression guard on the pre-existing app.
    [Tags]    smoke    api
    ${response}=    GET    ${BASE_URL}/health
    Should Be Equal As Integers    ${response.status_code}    200
    Should Be Equal    ${response.json()}[status]    ok

Student Form Is Unaffected
    [Documentation]    The anonymous student flow must not regress.
    [Tags]    smoke    api
    Navigate To Form
    Page Should Contain Element    id=overall_val
    Page Should Not Contain    Committee
