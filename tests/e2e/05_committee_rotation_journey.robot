*** Settings ***
Documentation     Journey 5 — end of term: the admin rotates the committee.
...
...               New members arrive in one pasted block, with typos in it. An
...               outgoing member is deactivated while still signed in and loses
...               access on their next click, but their review history stays. A
...               returning member is reactivated, and a member who forgot their
...               password is reset and forced to choose a new one.
...
...               Fixture: robot-test-member (active, six days of history),
...               robot-test-retired (inactive), robot-test-rated (active).
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    committee    admin

*** Variables ***
${ARJUN_EMAIL}     arjun.k@sai.edu
${MEERA_EMAIL}     meera.s@sai.edu

*** Test Cases ***
E05.01 The Outgoing Member Is Signed In Elsewhere
    [Documentation]    A separate HTTP session stands in for the outgoing member's
    ...    phone, still signed in when the admin deactivates them.
    Open Visitor Session    outgoing
    ${response}=    Session Member Login    outgoing    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Response Should Redirect To    ${response}    /committee
    ${response}=    Get Without Redirect    outgoing    /committee
    Should Be Equal As Integers    ${response.status_code}    200
    Should Contain    ${response.text}    committeeForm

E05.02 Admin Pastes The Incoming Committee, Typos And All
    Login As Admin
    ${lines}=    Catenate    SEPARATOR=\n
    ...    Arjun Kumar, ${ARJUN_EMAIL}
    ...    Meera Sundar, MEERA.S@sai.edu
    ...    No Comma Here arjun@sai.edu
    ...    Arjun Again, ${ARJUN_EMAIL}
    ...    Robot Test Member, ${MEMBER_EMAIL}
    ...    Bad Email, not-an-email
    Bulk Add Members Via UI    ${lines}
    Element Should Contain    css=.alert.success    Added 2 member(s).

E05.03 Each Bad Line Is Reported By Line Number
    Element Should Contain    css=.error-banner    Line 3: expected 'Name, email'.
    Element Should Contain    css=.error-banner    Line 4: ${ARJUN_EMAIL} is duplicated in this list.
    Element Should Contain    css=.error-banner    Line 5: ${MEMBER_EMAIL} is already on the roster
    Element Should Contain    css=.error-banner    Line 6:

E05.04 Both Newcomers Get A One-Time Password, Emails Normalised
    ${arjun}=    Get Revealed Password    ${ARJUN_EMAIL}
    ${meera}=    Get Revealed Password    ${MEERA_EMAIL}
    Should Not Be Equal    ${arjun}    ${meera}
    Set Suite Variable    ${ARJUN_OTP}    ${arjun}
    ${rows}=    Get Stored Rows    committee_members
    Length Should Be    ${rows}    6
    Roster Should Contain Member    ${ARJUN_EMAIL}
    Roster Should Contain Member    ${MEERA_EMAIL}

E05.05 Admin Deactivates The Outgoing Member
    Act On Member    ${MEMBER_EMAIL}    deactivate
    Element Should Contain    css=.alert.success    Deactivated ${MEMBER_EMAIL}.
    Member Row Should Show Status    ${MEMBER_EMAIL}    badge-inactive
    ${today}=    Today
    ${member}=    Get Stored Member    ${MEMBER_EMAIL}
    Should Be Equal    ${member}[Active]      FALSE
    Should Be Equal    ${member}[Term_End]    ${today}

E05.06 Their Open Session Stops Working On The Next Click
    [Tags]    security
    ${response}=    Get Without Redirect    outgoing    /committee
    Response Should Redirect To    ${response}    /committee/login

E05.07 They Cannot Sign In Again, And Are Told Nothing Specific
    [Tags]    security
    Sign Out Of Admin
    Become A New Visitor
    Login As Committee Member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Login Should Be Refused

E05.08 Their Review History Survives Deactivation
    [Documentation]    There is no delete, by design: the history is the record.
    ${rows}=    Get Stored Rows Where    committee_reviews    Member_Email    ${MEMBER_EMAIL}
    Length Should Be    ${rows}    6
    Open Committee Dashboard
    Page Should Contain    Historic review from day -1
    # newbie, rated, arjun, meera
    Element Text Should Be    id=stat-active-members    4

E05.09 A Returning Member Is Reactivated With Their Old Password
    Login As Admin
    Act On Member    ${RETIRED_EMAIL}    activate
    Element Should Contain    css=.alert.success    Reactivated ${RETIRED_EMAIL}.
    Member Row Should Show Status    ${RETIRED_EMAIL}    badge-active
    ${member}=    Get Stored Member    ${RETIRED_EMAIL}
    Should Be Equal    ${member}[Term_End]    ${EMPTY}
    Sign Out Of Admin
    Become A New Visitor
    Login And Reach Rating Page    ${RETIRED_EMAIL}    ${RETIRED_PASSWORD}

E05.10 A Member Who Forgot Their Password Is Reset
    Become A New Visitor
    Login As Admin
    Act On Member    ${RATED_EMAIL}    reset
    Element Should Contain    css=.alert.success    Password reset for ${RATED_EMAIL}.
    ${otp}=    Get Revealed Password    ${RATED_EMAIL}
    Set Suite Variable    ${RESET_OTP}    ${otp}
    Member Row Should Show Status    ${RATED_EMAIL}    badge-pending

E05.11 The Forgotten Password Stops Working
    [Tags]    security
    Sign Out Of Admin
    Become A New Visitor
    Login As Committee Member    ${RATED_EMAIL}    ${RATED_PASSWORD}
    Login Should Be Refused

E05.12 The Reset Password Forces A New One, Then Shows Today's Review
    [Documentation]    robot-test-rated already reviewed today; a reset must not
    ...    wipe that or let them file a second one.
    Login As Committee Member    ${RATED_EMAIL}    ${RESET_OTP}
    Choose New Password    brand-new-password-1
    Wait Until Page Contains Element    id=already-heading    timeout=${TIMEOUT}

E05.13 A Newcomer Completes Their First Day
    Become A New Visitor
    Login As Committee Member    ${ARJUN_EMAIL}    ${ARJUN_OTP}
    Choose New Password    arjun-rates-dinner
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}
    Rate Committee Dimensions    3    3    2    4    3
    Submit Committee Review

E05.14 The Dashboard Reflects The New Committee
    [Tags]    dashboard
    [Documentation]    Active: newbie, rated, retired (back), arjun, meera = 5.
    ...    Reviews today: rated + arjun = 2, so participation is 40%.
    Become A New Visitor
    Open Committee Dashboard
    Element Text Should Be    id=stat-active-members    5
    Element Text Should Be    id=stat-today-count       2
    Element Text Should Be    id=stat-participation     40%
