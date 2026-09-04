*** Settings ***
Documentation     Food Committee member UI tests: login page, credential
...               handling, the forced first-login password change, the
...               five-dimension rating widget, and submission.
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Run Keywords    Reset Test Fixture    AND    Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Start With A Clean Session

*** Test Cases ***

# ── SECTION 1: Login page ─────────────────────────────────────────────────

TC60 Committee Login Page Loads
    [Tags]    smoke    committee
    [Documentation]    The login page renders with both credential fields.
    Navigate To Committee Login
    Title Should Be    MessMate — Food Committee Login
    Page Should Contain Element    id=email
    Page Should Contain Element    id=password
    Page Should Contain Element    id=login-btn

TC61 Login Page States That Reviews Are Attributed
    [Tags]    committee    privacy
    [Documentation]    Committee reviews are the first non-anonymous data in the
    ...    app, so members must be told before they sign in.
    Navigate To Committee Login
    Page Should Contain    not anonymous
    Page Should Contain Element    css=.notice-box

TC62 Login Page Links Back To The Anonymous Student Form
    [Tags]    committee
    [Documentation]    A student who lands here should be able to get to the
    ...    right form rather than assuming they need an account.
    Navigate To Committee Login
    Page Should Contain Element    xpath=//a[@href='/']

TC63 Valid Login Reaches The Rating Page
    [Tags]    smoke    committee
    Login And Reach Rating Page
    Page Should Contain Element    id=committeeForm
    Page Should Contain    Signed in as

TC64 Invalid Password Shows The Error Banner
    [Tags]    smoke    committee    security
    Login As Committee Member    ${MEMBER_EMAIL}    definitely-wrong-password
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    Incorrect email or password
    Page Should Not Contain Element    id=committeeForm

TC65 Unknown Email Gives The Same Message As A Wrong Password
    [Tags]    committee    security
    [Documentation]    The login page must not reveal who is on the committee.
    Login As Committee Member    definitely-not-a-member@sai.edu    anything
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    Incorrect email or password

TC66 Deactivated Member Cannot Sign In
    [Tags]    committee    security
    [Documentation]    Rotation off the committee takes effect immediately.
    Login As Committee Member    ${RETIRED_EMAIL}    ${RETIRED_PASSWORD}
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Not Contain Element    id=committeeForm

TC67 Rating Page Is Unreachable Without A Session
    [Tags]    smoke    committee    security
    Sign Out Of Committee
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}
    Location Should Contain    /committee/login

# ── SECTION 2: Forced first-login password change ─────────────────────────

TC68 First Sign In Is Diverted To The Password Change
    [Tags]    committee    security
    [Documentation]    The password an admin hands out is single use.
    Login As Committee Member    ${NEWBIE_EMAIL}    ${NEWBIE_PASSWORD}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password

TC69 Rating Page Stays Blocked Until The Password Is Changed
    [Tags]    committee    security
    Login As Committee Member    ${NEWBIE_EMAIL}    ${NEWBIE_PASSWORD}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Location Should Contain    /committee/password

TC70 Mismatched Confirmation Is Rejected
    [Tags]    committee
    Login As Committee Member    ${NEWBIE_EMAIL}    ${NEWBIE_PASSWORD}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Input Password    id=password    a-good-password
    Input Password    id=confirm     a-different-password
    Click Element     id=password-btn
    Wait Until Element Is Visible    css=.error-banner    timeout=${TIMEOUT}
    Page Should Contain    do not match

TC71 Changing The Password Unblocks Rating
    [Tags]    committee
    Login As Committee Member    ${NEWBIE_EMAIL}    ${NEWBIE_PASSWORD}
    Wait Until Page Contains Element    id=password-btn    timeout=${TIMEOUT}
    Input Password    id=password    chosen-by-the-member
    Input Password    id=confirm     chosen-by-the-member
    Click Element     id=password-btn
    Wait Until Page Contains Element    id=committeeForm    timeout=${TIMEOUT}

# ── SECTION 3: Rating widget ──────────────────────────────────────────────

TC72 All Five Dimensions Are Present
    [Tags]    smoke    committee
    Login And Reach Rating Page
    FOR    ${dimension}    IN    @{DIMENSIONS}
        Page Should Contain Element    css=.emoji-group[data-dimension="${dimension}"]
        Page Should Contain Element    id=${dimension}_val
    END

TC73 Submit Is Disabled Until Every Dimension Is Rated
    [Tags]    smoke    committee
    [Documentation]    Unlike the student form, where per-item ratings are
    ...    optional, all five committee dimensions are required.
    Login And Reach Rating Page
    Element Should Be Disabled    id=submit-btn
    Rate Dimension    taste      4
    Rate Dimension    quality    4
    Rate Dimension    variety    4
    Rate Dimension    hygiene    4
    Element Should Be Disabled    id=submit-btn
    Rate Dimension    menu       4
    Element Should Be Enabled    id=submit-btn

TC74 Progress Hint Tracks How Many Are Rated
    [Tags]    committee
    Login And Reach Rating Page
    Rate Dimension    taste      3
    Rate Dimension    quality    3
    Element Text Should Be Contains    id=submit-hint    Rated 2 of 5

TC75 Selecting An Emoji Marks It And Records The Value
    [Tags]    committee
    Login And Reach Rating Page
    Rate Dimension    taste    5
    Element Should Have Class
    ...    css=.emoji-btn[data-item="taste"][data-value="5"]    selected
    Dimension Hidden Value Should Be    taste    5

TC76 Ratings Within A Dimension Are Mutually Exclusive
    [Tags]    committee
    Login And Reach Rating Page
    Rate Dimension    taste    5
    Rate Dimension    taste    2
    Element Should Have Class
    ...    css=.emoji-btn[data-item="taste"][data-value="2"]    selected
    Element Should Not Have Class
    ...    css=.emoji-btn[data-item="taste"][data-value="5"]    selected
    Dimension Hidden Value Should Be    taste    2

TC77 Dimensions Are Rated Independently
    [Tags]    committee
    [Documentation]    Rating one dimension must not disturb another.
    Login And Reach Rating Page
    Rate Dimension    taste      1
    Rate Dimension    hygiene    5
    Dimension Hidden Value Should Be    taste      1
    Dimension Hidden Value Should Be    hygiene    5

TC78 Review Character Counter Updates
    [Tags]    committee
    Login And Reach Rating Page
    Input Text    id=review    Rice was cold
    Element Text Should Be Contains    id=char-counter    13 / 500

TC79 Review Field Enforces Its Maximum Length
    [Tags]    committee
    Login And Reach Rating Page
    ${maxlength}=    Get Element Attribute    id=review    maxlength
    Should Be Equal    ${maxlength}    500

# ── SECTION 4: Submission ─────────────────────────────────────────────────

TC80 A Complete Review Submits Successfully
    [Tags]    smoke    committee
    Login And Reach Rating Page
    Rate All Dimensions    4
    Input Text    id=review    Robot Framework submitted this review
    Submit Committee Review
    Page Should Contain    Review recorded

TC81 Review Is Optional
    [Tags]    committee
    Login And Reach Rating Page
    Rate All Dimensions    3
    Submit Committee Review
    Page Should Contain    Review recorded

TC82 A Second Review The Same Day Is Refused
    [Tags]    smoke    committee
    [Documentation]    One review per member per day keeps averages meaningful.
    Login And Reach Rating Page
    Rate All Dimensions    5
    Submit Committee Review
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=already-heading    timeout=${TIMEOUT}
    Page Should Contain    already reviewed today
    Page Should Not Contain Element    id=committeeForm

TC83 A Member Who Already Rated Sees The Notice On Sign In
    [Tags]    committee
    [Documentation]    The fixture member has already rated today.
    Login As Committee Member    ${RATED_EMAIL}    ${RATED_PASSWORD}
    Wait Until Page Contains Element    id=already-heading    timeout=${TIMEOUT}
    Page Should Not Contain Element    id=committeeForm

TC84 Double Submission Is Prevented Client Side
    [Tags]    committee
    [Documentation]    The button disables itself so a double tap cannot post twice.
    Login And Reach Rating Page
    Rate All Dimensions    4
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.thanks-container    timeout=${TIMEOUT}

TC85 Signing Out Ends The Session
    [Tags]    committee    security
    Login And Reach Rating Page
    Click Element    css=button.link-btn
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}
    Go To    ${COMMITTEE_URL}
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}
    Location Should Contain    /committee/login

*** Keywords ***
Element Text Should Be Contains
    [Arguments]    ${locator}    ${expected}
    [Documentation]    Asserts an element's text contains the expected substring.
    ${text}=    Get Text    ${locator}
    Should Contain    ${text}    ${expected}
