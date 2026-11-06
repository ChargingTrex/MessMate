*** Settings ***
Documentation     Journey 6 — who can reach what.
...
...               Walks the same routes as four different visitors — anonymous,
...               dashboard-token holder, committee member, admin — then attacks
...               the boundaries between them: forged and replayed CSRF tokens,
...               open redirects, login probing, and brute force.
...
...               Mostly HTTP sessions, each with its own cookie jar, so every
...               visitor is provably independent of the others.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    security

*** Variables ***
@{ADMIN_ONLY}       /admin/members    /admin/menu
@{MEMBER_ONLY}      /committee    /committee/password    /committee/thanks
@{DASHBOARDS}       /dashboard    /dashboard/committee
@{PUBLIC_PAGES}     /    /home    /thanks    /health    /committee/login    /admin/login

*** Test Cases ***
E06.01 Anyone Can Reach The Public Pages
    [Tags]    smoke
    Open Visitor Session    anon
    FOR    ${path}    IN    @{PUBLIC_PAGES}
        GET On Session    anon    ${path}    expected_status=200
    END

E06.02 Anonymous Visitors Are Sent To The Right Login Page
    FOR    ${path}    IN    @{ADMIN_ONLY}
        ${response}=    Get Without Redirect    anon    ${path}
        Response Should Redirect To    ${response}    /admin/login?next=${path}
    END
    FOR    ${path}    IN    @{MEMBER_ONLY}
        ${response}=    Get Without Redirect    anon    ${path}
        Response Should Redirect To    ${response}    /committee/login
    END

E06.03 Dashboards Refuse A Missing Or Wrong Token
    FOR    ${path}    IN    @{DASHBOARDS}
        ${response}=    GET On Session    anon    ${path}    expected_status=403
        Should Contain    ${response.text}    Access denied
        GET On Session    anon    ${path}    params=token=not-the-token    expected_status=403
        GET On Session    anon    ${path}    params=token=    expected_status=403
    END

E06.04 The Dashboard Token Is Read-Only
    [Documentation]    The token opens both dashboards and nothing else — it is a
    ...    link that gets forwarded around, so it must never manage the roster.
    FOR    ${path}    IN    @{DASHBOARDS}
        GET On Session    anon    ${path}    params=token=${DASHBOARD_TOKEN}    expected_status=200
    END
    FOR    ${path}    IN    @{ADMIN_ONLY}
        ${response}=    Get Without Redirect    anon    ${path}?token=${DASHBOARD_TOKEN}
        Response Should Redirect To    ${response}    /admin/login
    END

E06.05 A Committee Member Cannot Reach Admin Pages Or Dashboards
    Open Visitor Session    member
    ${response}=    Session Member Login    member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Response Should Redirect To    ${response}    /committee
    GET On Session    member    /committee    expected_status=200
    FOR    ${path}    IN    @{ADMIN_ONLY}
        ${response}=    Get Without Redirect    member    ${path}
        Response Should Redirect To    ${response}    /admin/login
    END
    FOR    ${path}    IN    @{DASHBOARDS}
        GET On Session    member    ${path}    expected_status=403
    END

E06.06 An Admin Session Opens Everything Admin-Side Without A Token
    Open Visitor Session    admin
    ${response}=    Session Admin Login    admin
    Response Should Redirect To    ${response}    /admin/members
    FOR    ${path}    IN    @{ADMIN_ONLY}    @{DASHBOARDS}
        GET On Session    admin    ${path}    expected_status=200
    END
    ${response}=    GET On Session    admin    /dashboard/committee
    Should Contain    ${response.text}    Manage members

E06.07 Being Admin Does Not Make You A Committee Member
    ${response}=    Get Without Redirect    admin    /committee
    Response Should Redirect To    ${response}    /committee/login

E06.08 Roster Changes Without A CSRF Token Are Refused
    ${before}=    Get Stored Rows    committee_members
    ${data}=    Create Dictionary    name=Forged    email=forged@sai.edu
    POST On Session    admin    /admin/members/add    data=${data}    expected_status=403
    ${data}=    Create Dictionary    email=${MEMBER_EMAIL}    action=deactivate
    POST On Session    admin    /admin/members/update    data=${data}    expected_status=403
    ${after}=    Get Stored Rows    committee_members
    Should Be Equal    ${before}    ${after}

E06.09 A CSRF Token From Another Session Is Refused
    [Documentation]    Tokens are bound to the session that issued them, so one
    ...    lifted from an attacker's own login page is worthless here.
    Open Visitor Session    attacker
    ${foreign}=    Get Csrf Token    attacker    /admin/login
    ${data}=    Create Dictionary    name=Forged    email=forged@sai.edu    csrf_token=${foreign}
    POST On Session    admin    /admin/members/add    data=${data}    expected_status=403
    ${data}=    Create Dictionary    date=2030-01-01    Lunch=Forged    csrf_token=${foreign}
    POST On Session    admin    /admin/menu/save    data=${data}    expected_status=403
    ${rows}=    Get Stored Rows Where    committee_members    Email    forged@sai.edu
    Should Be Empty    ${rows}
    ${rows}=    Get Stored Rows Where    menu    Date    2030-01-01
    Should Be Empty    ${rows}

E06.10 The Same Request With The Session's Own Token Succeeds
    [Documentation]    Proves the two refusals above were the CSRF check and
    ...    not some other failure.
    ${token}=    Get Csrf Token    admin    /admin/members
    ${data}=    Create Dictionary    name=Real Member    email=real@sai.edu    csrf_token=${token}
    ${response}=    POST On Session    admin    /admin/members/add    data=${data}    expected_status=200
    Should Contain    ${response.text}    Added Real Member.
    ${member}=    Get Stored Member    real@sai.edu
    Should Be Equal    ${member}[Name]    Real Member

E06.11 Committee Logins And Reviews Also Need The Token
    ${before}=    Get Stored Rows    committee_reviews
    ${data}=    Create Dictionary    email=${MEMBER_EMAIL}    password=${MEMBER_PASSWORD}
    POST On Session    anon    /committee/login    data=${data}    expected_status=403
    ${data}=    Create Dictionary    taste=5    quality=5    variety=5    hygiene=5    menu=5
    POST On Session    member    /committee/submit    data=${data}    expected_status=403
    ${after}=    Get Stored Rows    committee_reviews
    Should Be Equal    ${before}    ${after}

E06.12 Logout Is POST-Only So A Link Cannot Sign You Out
    ${response}=    GET On Session    member    /committee/logout    expected_status=405
    GET On Session    member    /committee    expected_status=200

E06.13 Login Never Reveals Who Is On The Committee
    [Documentation]    Unknown email, wrong password, and deactivated member get a
    ...    byte-identical answer.
    Open Visitor Session    prober
    ${unknown}=    Session Member Login    prober    nobody@sai.edu    whatever-password
    ${wrong}=      Session Member Login    prober    ${MEMBER_EMAIL}    wrong-password
    ${retired}=    Session Member Login    prober    ${RETIRED_EMAIL}    ${RETIRED_PASSWORD}
    FOR    ${response}    IN    ${unknown}    ${wrong}    ${retired}
        Should Be Equal As Integers    ${response.status_code}    401
        Should Contain    ${response.text}    Incorrect email or password.
    END
    ${a}=    Evaluate    re.sub(r'value="[^"]*"', '', $unknown.text)    modules=re
    ${b}=    Evaluate    re.sub(r'value="[^"]*"', '', $wrong.text)      modules=re
    ${c}=    Evaluate    re.sub(r'value="[^"]*"', '', $retired.text)    modules=re
    Should Be Equal    ${a}    ${b}
    Should Be Equal    ${a}    ${c}

E06.14 Login Redirects Stay On This Site
    [Documentation]    ?next= is honoured for local paths only.
    FOR    ${next}    ${lands_on}    IN
    ...    /admin/menu                     /admin/menu
    ...    //evil.example/phish            /admin/members
    ...    https://evil.example/phish      /admin/members
    ...    javascript:alert(1)             /admin/members
        Open Visitor Session    redirect
        ${token}=    Get Csrf Token    redirect    /admin/login
        ${data}=    Create Dictionary    password=${ADMIN_PASSWORD}    next=${next}    csrf_token=${token}
        ${response}=    POST On Session    redirect    /admin/login    data=${data}
        ...    allow_redirects=${FALSE}    expected_status=any
        Should Be Equal    ${response.headers}[Location]    ${lands_on}
    END

E06.15 The Browser Follows A Deep Link Through Login
    Become A New Visitor
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=admin-login-btn    timeout=${TIMEOUT}
    Input Password    id=password    ${ADMIN_PASSWORD}
    Click Element     id=admin-login-btn
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}
    Location Should Be    ${MENU_EDITOR_URL}

E06.16 Session Cookies Are HttpOnly And SameSite
    Open Visitor Session    cookies
    ${response}=    Session Member Login    cookies    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    ${set_cookie}=    Set Variable    ${response.headers}[Set-Cookie]
    Should Contain    ${set_cookie}    HttpOnly
    Should Contain    ${set_cookie}    SameSite=Lax
    ${cookie}=    Get Cookie    session
    Should Be True    ${cookie.httpOnly}    Browser session cookie must be HttpOnly.

E06.17 Admin Password Guessing Is Capped At Ten An Hour
    [Tags]    rate-limit
    Turn Rate Limits On
    Open Visitor Session    guesser
    FOR    ${attempt}    IN RANGE    10
        ${response}=    Session Admin Login    guesser    guess-${attempt}
        Should Be Equal As Integers    ${response.status_code}    401
    END
    ${response}=    Session Admin Login    guesser    ${ADMIN_PASSWORD}
    Should Be Equal As Integers    ${response.status_code}    429
    Should Contain    ${response.text}    Too many login attempts
    Should Contain    ${response.text}    admin-login-btn
    Should Not Contain    ${response.text}    feedbackForm
    [Teardown]    Run Keywords    Turn Rate Limits Off    AND    Record Step Outcome
