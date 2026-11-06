*** Settings ***
Documentation     Journey 4 — a new committee member, from invitation to the dashboard.
...
...               The admin adds Priya and reads her one-time password off the
...               screen. Priya signs in, is held on the password page until she
...               replaces it, files her first review, and is then held to one a
...               day. The VC finally sees her review on the committee dashboard.
...
...               Fixture: four members (three active) and one review today from
...               robot-test-rated, scored 4, 4, 3, 5, 4.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    committee

*** Variables ***
${PRIYA_NAME}        Priya Raman
${PRIYA_EMAIL}       priya.raman@sai.edu
${PRIYA_PASSWORD}    sambar-is-life-2026
${PRIYA_REVIEW}      Sambar was watery & the rice was cold

*** Test Cases ***
E04.01 Admin Adds Priya And Sees Her One-Time Password Once
    [Tags]    smoke    admin
    Login As Admin
    Add Member Via UI    ${PRIYA_NAME}    ${PRIYA_EMAIL}
    Element Should Contain    css=.alert.success    Added ${PRIYA_NAME}.
    ${otp}=    Get Revealed Password    ${PRIYA_EMAIL}
    Should Match Regexp    ${otp}    ^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$
    Set Suite Variable    ${OTP}    ${otp}

E04.02 Priya Is On The Roster As Active With Her Password Not Yet Set
    [Tags]    admin
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=members-table    timeout=${TIMEOUT}
    Member Row Should Show Status    ${PRIYA_EMAIL}    badge-active
    Member Row Should Show Status    ${PRIYA_EMAIL}    badge-pending

E04.03 The Password Is Not Shown Again And Was Never Stored In Plain Text
    [Tags]    admin    security
    Page Should Not Contain Element    css=.credential-banner
    Page Should Not Contain    ${OTP}
    ${member}=    Get Stored Member    ${PRIYA_EMAIL}
    Should Not Contain    ${member}[Password_Hash]    ${OTP}
    Should Not Be Empty    ${member}[Password_Hash]
    Should Be Equal    ${member}[Must_Change_Password]    TRUE
    Should Be Equal    ${member}[Active]    TRUE

E04.04 Priya Signs In And Is Sent Straight To Choose A Password
    Sign Out Of Admin
    Become A New Visitor
    Login As Committee Member    ${PRIYA_EMAIL}    ${OTP}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password

E04.05 She Cannot Skip Ahead To The Rating Page
    [Tags]    security
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password
    Page Should Not Contain Element    id=committeeForm

E04.06 A Short Password Is Stopped By The Browser
    [Tags]    validation
    Choose New Password    short
    Location Should Contain    /committee/password
    ${too_short}=    Execute JavaScript    return document.getElementById('password').validity.tooShort
    Should Be True    ${too_short}

E04.07 A Short Password Is Also Refused By The Server
    [Tags]    validation    security
    [Documentation]    minlength is only a hint to the browser; a direct POST
    ...    must meet the same rule on the server.
    Open Visitor Session    priya-direct
    ${response}=    Session Member Login    priya-direct    ${PRIYA_EMAIL}    ${OTP}
    Response Should Redirect To    ${response}    /committee/password
    ${token}=    Get Csrf Token    priya-direct    /committee/password
    ${data}=    Create Dictionary    csrf_token=${token}    password=short    confirm=short
    ${response}=    POST On Session    priya-direct    /committee/password    data=${data}
    ...    expected_status=400
    Should Contain    ${response.text}    at least 8 characters
    ${member}=    Get Stored Member    ${PRIYA_EMAIL}
    Should Be Equal    ${member}[Must_Change_Password]    TRUE

E04.08 A Mistyped Confirmation Is Rejected
    [Tags]    validation
    Choose New Password    ${PRIYA_PASSWORD}    ${PRIYA_PASSWORD}-typo
    Wait Until Page Contains Element    css=.error-banner    timeout=${TIMEOUT}
    Element Should Contain    css=.error-banner    do not match

E04.09 A Good Password Takes Her To The Rating Form
    Choose New Password    ${PRIYA_PASSWORD}
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}
    Location Should Be    ${COMMITTEE_URL}
    ${member}=    Get Stored Member    ${PRIYA_EMAIL}
    Should Be Equal    ${member}[Must_Change_Password]    FALSE

E04.10 Submit Stays Disabled Until All Five Areas Are Rated
    Element Should Be Disabled    id=submit-btn
    Rate Dimension    taste      5
    Rate Dimension    quality    4
    Rate Dimension    variety    3
    Rate Dimension    hygiene    4
    Element Should Be Disabled    id=submit-btn
    Rate Dimension    menu       5
    Element Should Be Enabled    id=submit-btn

E04.11 Priya Files Her First Review
    [Tags]    smoke
    Input Text    id=review    ${PRIYA_REVIEW}
    Submit Committee Review
    Page Should Contain    Review recorded
    Page Should Contain    ${PRIYA_NAME}

E04.12 The Review Was Stored Against Her Name
    ${today}=    Today
    ${rows}=    Get Stored Rows Where    committee_reviews    Member_Email    ${PRIYA_EMAIL}
    Length Should Be    ${rows}    1
    ${row}=    Set Variable    ${rows}[0]
    Should Be Equal    ${row}[Date]           ${today}
    Should Be Equal    ${row}[Member_Name]    ${PRIYA_NAME}
    Should Be Equal    ${row}[Review]         ${PRIYA_REVIEW}
    FOR    ${dimension}    ${expected}    IN
    ...    Taste    5    Quality    4    Variety    3    Hygiene    4    Menu    5
        Should Be Equal As Integers    ${row}[${dimension}]    ${expected}
    END

E04.13 Coming Back The Same Day Shows Already Reviewed
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=already-heading    timeout=${TIMEOUT}
    Page Should Not Contain Element    id=committeeForm

E04.14 A Replayed Second Review Is Not Stored
    [Tags]    security
    [Documentation]    The form is hidden after one review, but the POST route must
    ...    refuse a second one on its own — not rely on the page hiding it.
    Open Visitor Session    priya
    ${response}=    Session Member Login    priya    ${PRIYA_EMAIL}    ${PRIYA_PASSWORD}
    Response Should Redirect To    ${response}    /committee
    ${token}=    Get Csrf Token    priya    /committee/login
    ${data}=    Create Dictionary    csrf_token=${token}    taste=1    quality=1
    ...    variety=1    hygiene=1    menu=1    review=second attempt
    ${response}=    POST On Session    priya    /committee/submit    data=${data}
    Should Contain    ${response.text}    already reviewed today
    ${rows}=    Get Stored Rows Where    committee_reviews    Member_Email    ${PRIYA_EMAIL}
    Length Should Be    ${rows}    1

E04.15 She Signs Out And The One-Time Password No Longer Works
    [Tags]    security
    Click Element    xpath=//button[normalize-space()='Sign out']
    Wait Until Page Contains Element    id=login-btn    timeout=${TIMEOUT}
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=login-btn    timeout=${TIMEOUT}
    Login As Committee Member    ${PRIYA_EMAIL}    ${OTP}
    Login Should Be Refused

E04.16 Her Own Password Signs Her Back In
    Login As Committee Member    ${PRIYA_EMAIL}    ${PRIYA_PASSWORD}
    Wait Until Page Contains Element    id=already-heading    timeout=${TIMEOUT}

E04.17 The VC Sees Today's Numbers Include Priya
    [Tags]    smoke    dashboard
    [Documentation]    Two reviews today out of four active members. The average
    ...    pools all ten scores: (4+4+3+5+4 + 5+4+3+4+5) / 10 = 4.1.
    Become A New Visitor
    Open Committee Dashboard
    Element Text Should Be    id=stat-today-count        2
    Element Text Should Be    id=stat-active-members     4
    Element Text Should Be    id=stat-participation      50%
    Element Text Should Be    id=stat-today-avg          4.1

E04.18 Her Review Heads The Feed, Ampersand Intact
    [Tags]    dashboard    security
    First Feed Entry Should Be    ${PRIYA_REVIEW}    ${PRIYA_NAME}
    Page Should Not Contain    &amp;

E04.19 The Token View Offers No Roster Management
    [Tags]    dashboard    security
    Page Should Not Contain Link    Manage members
