*** Settings ***
Documentation     Admin member management UI tests: access control, the roster
...               table, adding members singly and in bulk, rotation actions,
...               and one-time credential handling.
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Run Keywords    Reset Test Fixture    AND    Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Start With A Clean Session

*** Test Cases ***

# ── SECTION 1: Access control ─────────────────────────────────────────────

TC90 Admin Login Page Loads
    [Tags]    smoke    admin
    Go To    ${ADMIN_LOGIN_URL}
    Title Should Be    MessMate — Admin Login
    Page Should Contain Element    id=password
    Page Should Contain Element    id=admin-login-btn

TC91 Correct Password Opens The Roster
    [Tags]    smoke    admin
    Login As Admin
    Page Should Contain Element    id=members-table
    Page Should Contain Element    id=add-member-form
    Page Should Contain Element    id=bulk-add-form

TC92 Wrong Admin Password Is Refused
    [Tags]    smoke    admin    security
    Go To    ${ADMIN_LOGIN_URL}
    Input Password    id=password    not-the-admin-password
    Click Element     id=admin-login-btn
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Not Contain Element    id=members-table

TC93 Roster Is Unreachable Without An Admin Session
    [Tags]    smoke    admin    security
    Sign Out Of Admin
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Location Should Contain    /admin/login

TC94 Dashboard Token Cannot Open The Roster
    [Tags]    smoke    admin    security
    [Documentation]    The headline privilege boundary. A query-string token
    ...    leaks through history, referrers and access logs, so it must never
    ...    reach a page that can create accounts.
    Sign Out Of Admin
    Go To    ${BASE_URL}/admin/members?token=${DASHBOARD_TOKEN}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Location Should Contain    /admin/login
    Page Should Not Contain Element    id=members-table

TC95 Admin Sign Out Ends The Session
    [Tags]    admin    security
    Login As Admin
    Click Element    xpath=//button[text()='Sign out']
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Location Should Contain    /admin/login

# ── SECTION 2: Roster table ───────────────────────────────────────────────

TC96 Roster Lists The Seeded Members
    [Tags]    smoke    admin
    Login As Admin
    Roster Should Contain Member    ${MEMBER_EMAIL}
    Roster Should Contain Member    ${RETIRED_EMAIL}

TC97 Active And Inactive Members Are Badged Differently
    [Tags]    admin
    Login As Admin
    Member Row Should Show Status    ${MEMBER_EMAIL}     badge-active
    Member Row Should Show Status    ${RETIRED_EMAIL}    badge-inactive

TC98 A Member Who Has Not Set A Password Is Flagged
    [Tags]    admin
    [Documentation]    Lets an admin see at a glance who never completed setup.
    Login As Admin
    Member Row Should Show Status    ${NEWBIE_EMAIL}    badge-pending

TC99 Roster Shows Review Counts For The Month
    [Tags]    admin
    Login As Admin
    Page Should Contain    Reviews

TC100 Active Member Count Is Displayed
    [Tags]    admin
    Login As Admin
    Page Should Contain    active member

# ── SECTION 3: Adding members ─────────────────────────────────────────────

TC101 Adding A Member Reveals A One-Time Password
    [Tags]    smoke    admin
    Login As Admin
    Add Member Via UI    Robot Added Member    robot-test-added@sai.edu
    ${password}=    Get Revealed Password    robot-test-added@sai.edu
    Should Not Be Empty    ${password}
    Roster Should Contain Member    robot-test-added@sai.edu

TC102 The Generated Password Actually Works
    [Tags]    smoke    admin    committee
    [Documentation]    The full add-then-sign-in round trip.
    Login As Admin
    Add Member Via UI    Round Trip Member    robot-test-roundtrip@sai.edu
    ${password}=    Get Revealed Password    robot-test-roundtrip@sai.edu
    Login As Committee Member    robot-test-roundtrip@sai.edu    ${password}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password

TC103 The Password Is Not Shown Again After Reload
    [Tags]    admin    security
    [Documentation]    Only the hash is stored, so the reveal is genuinely
    ...    one-time — a reset is the only way back.
    Login As Admin
    Add Member Via UI    Once Only    robot-test-onceonly@sai.edu
    Wait Until Page Contains Element    css=.credential-banner    timeout=${TIMEOUT}
    Go To    ${ADMIN_MEMBERS_URL}
    Page Should Not Contain Element    css=.credential-banner

TC104 Duplicate Email Is Rejected
    [Tags]    admin
    Login As Admin
    Add Member Via UI    Duplicate Attempt    ${MEMBER_EMAIL}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    already on the roster

TC105 A Retired Member Cannot Be Re-Added
    [Tags]    admin
    [Documentation]    Reactivation preserves history; re-adding would fork it.
    Login As Admin
    Add Member Via UI    Retired Again    ${RETIRED_EMAIL}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    reactivate

TC106 Malformed Email Is Rejected
    [Tags]    admin
    Login As Admin
    Go To    ${ADMIN_MEMBERS_URL}
    Input Text    id=name     Bad Address
    Input Text    id=email    not-an-email-at-all
    Execute JavaScript    document.getElementById('email').removeAttribute('type')
    Click Element    id=add-btn
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}

# ── SECTION 4: Bulk add ───────────────────────────────────────────────────

TC107 Bulk Add Creates Every Valid Row
    [Tags]    smoke    admin
    [Documentation]    The rotation case — a whole incoming committee at once.
    Login As Admin
    Bulk Add Members Via UI
    ...    Bulk One, robot-test-bulk1@sai.edu\nBulk Two, robot-test-bulk2@sai.edu
    Wait Until Page Contains Element    css=.credential-banner    timeout=${TIMEOUT}
    Roster Should Contain Member    robot-test-bulk1@sai.edu
    Roster Should Contain Member    robot-test-bulk2@sai.edu

TC108 Bulk Add Reveals A Password Per Member
    [Tags]    admin
    Login As Admin
    Bulk Add Members Via UI
    ...    Bulk Three, robot-test-bulk3@sai.edu\nBulk Four, robot-test-bulk4@sai.edu
    ${first}=     Get Revealed Password    robot-test-bulk3@sai.edu
    ${second}=    Get Revealed Password    robot-test-bulk4@sai.edu
    Should Not Be Empty    ${first}
    Should Not Be Empty    ${second}
    Should Not Be Equal    ${first}    ${second}

TC109 Bulk Add Reports Bad Lines Individually
    [Tags]    admin
    [Documentation]    A malformed line must not silently vanish, and must not
    ...    stop the valid lines from being created.
    Login As Admin
    Bulk Add Members Via UI
    ...    Good One, robot-test-good@sai.edu\nMissing The Comma\nBad Email, nope
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    Line 2
    Page Should Contain    Line 3
    Roster Should Contain Member    robot-test-good@sai.edu

# ── SECTION 5: Rotation actions ───────────────────────────────────────────

TC110 Deactivating A Member Retires Them
    [Tags]    smoke    admin
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    deactivate
    Wait Until Page Contains Element    id=members-table    timeout=${TIMEOUT}
    Member Row Should Show Status    ${MEMBER_EMAIL}    badge-inactive

TC111 A Deactivated Member Can No Longer Sign In
    [Tags]    admin    security
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    deactivate
    Login As Committee Member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}

TC112 Deactivation Keeps The Member On The Roster
    [Tags]    admin
    [Documentation]    There is no delete — history stays attributable.
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    deactivate
    Roster Should Contain Member    ${MEMBER_EMAIL}

TC113 Reactivating Restores Access
    [Tags]    admin
    Login As Admin
    Act On Member    ${RETIRED_EMAIL}    activate
    Wait Until Page Contains Element    id=members-table    timeout=${TIMEOUT}
    Member Row Should Show Status    ${RETIRED_EMAIL}    badge-active
    Login As Committee Member    ${RETIRED_EMAIL}    ${RETIRED_PASSWORD}
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}

TC114 Resetting A Password Issues A New One
    [Tags]    smoke    admin
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    reset
    ${password}=    Get Revealed Password    ${MEMBER_EMAIL}
    Should Not Be Empty    ${password}
    Should Not Be Equal    ${password}    ${MEMBER_PASSWORD}

TC115 The Old Password Stops Working After A Reset
    [Tags]    admin    security
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    reset
    Get Revealed Password    ${MEMBER_EMAIL}
    Login As Committee Member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}

TC116 A Reset Password Forces Another Change
    [Tags]    admin    security
    Login As Admin
    Act On Member    ${MEMBER_EMAIL}    reset
    ${password}=    Get Revealed Password    ${MEMBER_EMAIL}
    Login As Committee Member    ${MEMBER_EMAIL}    ${password}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}

# ── SECTION 6: Rendering safety ───────────────────────────────────────────

TC117 Member Names Are Escaped Not Executed
    [Tags]    admin    security
    [Documentation]    Names reach the roster table unescaped from the sheet,
    ...    so Jinja must be the thing that escapes them.
    Login As Admin
    Add Member Via UI    <script>window.xssRan=true</script>    robot-test-xss@sai.edu
    Go To    ${ADMIN_MEMBERS_URL}
    ${ran}=    Execute JavaScript    return window.xssRan === true
    Should Not Be True    ${ran}
    Page Should Contain    <script>window.xssRan=true</script>

TC118 Admin Can Reach Both Dashboards From The Roster
    [Tags]    admin
    Login As Admin
    Page Should Contain Element    xpath=//a[contains(@href,'/dashboard/committee')]
    Page Should Contain Element    xpath=//a[@href='/dashboard']
