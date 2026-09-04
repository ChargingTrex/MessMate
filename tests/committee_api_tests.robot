*** Settings ***
Documentation     HTTP-level tests for the Food Committee routes: status codes,
...               redirects, the CSRF gate, and the privilege boundary between
...               the read-only token and an admin session.
...
...               No browser — these assert on raw responses, so they run fast
...               and catch what a rendered page can hide.
Library           RequestsLibrary
Library           Collections
Library           String
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Reset Test Fixture

*** Variables ***
&{FULL_RATING}    taste=4    quality=4    variety=4    hygiene=4    menu=4

*** Test Cases ***

# ── SECTION 1: Public surface ─────────────────────────────────────────────

TC150 Committee Login Page Returns 200
    [Tags]    smoke    api    committee
    ${response}=    GET    ${BASE_URL}/committee/login
    Should Be Equal As Integers    ${response.status_code}    200

TC151 Admin Login Page Returns 200
    [Tags]    smoke    api    admin
    ${response}=    GET    ${BASE_URL}/admin/login
    Should Be Equal As Integers    ${response.status_code}    200

TC152 Rating Page Redirects When Unauthenticated
    [Tags]    smoke    api    security
    ${response}=    GET    ${BASE_URL}/committee
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Be Equal As Integers    ${response.status_code}    302
    Should Contain    ${response.headers['Location']}    /committee/login

TC153 Roster Redirects When Unauthenticated
    [Tags]    smoke    api    security
    ${response}=    GET    ${BASE_URL}/admin/members
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Be Equal As Integers    ${response.status_code}    302
    Should Contain    ${response.headers['Location']}    /admin/login

# ── SECTION 2: The privilege boundary ─────────────────────────────────────

TC154 Token Opens The Committee Dashboard
    [Tags]    smoke    api
    ${response}=    GET    url=${BASE_URL}/dashboard/committee?token=${DASHBOARD_TOKEN}
    Should Be Equal As Integers    ${response.status_code}    200

TC155 Committee Dashboard Without A Token Is 403
    [Tags]    smoke    api    security
    ${response}=    GET    ${BASE_URL}/dashboard/committee    expected_status=403
    Should Contain    ${response.text}    Access denied

TC156 Token Does Not Open The Roster
    [Tags]    smoke    api    security
    [Documentation]    A credential that travels in the URL must not reach a
    ...    page that can create accounts.
    ${response}=    GET    url=${BASE_URL}/admin/members?token=${DASHBOARD_TOKEN}
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Be Equal As Integers    ${response.status_code}    302
    Should Contain    ${response.headers['Location']}    /admin/login

TC157 Token Cannot Add A Member
    [Tags]    smoke    api    security
    ${response}=    POST    url=${BASE_URL}/admin/members/add?token=${DASHBOARD_TOKEN}
    ...    data=${{ {'name': 'Attacker', 'email': 'attacker@sai.edu'} }}
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Contain    ${{ [302, 403] }}    ${response.status_code}

TC158 Token Cannot Bulk Add Members
    [Tags]    api    security
    ${response}=    POST    url=${BASE_URL}/admin/members/bulk?token=${DASHBOARD_TOKEN}
    ...    data=${{ {'members': 'Attacker, attacker@sai.edu'} }}
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Contain    ${{ [302, 403] }}    ${response.status_code}

TC159 Token Cannot Reset A Password
    [Tags]    api    security
    ${response}=    POST    url=${BASE_URL}/admin/members/update?token=${DASHBOARD_TOKEN}
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'action': 'reset'} }}
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Contain    ${{ [302, 403] }}    ${response.status_code}

TC160 The Attacker Created Nothing
    [Tags]    api    security
    [Documentation]    Confirms the refusals above were refusals, not silent successes.
    ${response}=    GET    url=${BASE_URL}/dashboard/committee?token=${DASHBOARD_TOKEN}
    Should Not Contain    ${response.text}    attacker@sai.edu

# ── SECTION 3: CSRF ───────────────────────────────────────────────────────

TC161 Login Without A CSRF Token Is Rejected
    [Tags]    smoke    api    security
    ${response}=    POST    ${BASE_URL}/committee/login
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'password': 'robot-test-password'} }}
    ...    expected_status=403
    Should Be Equal As Integers    ${response.status_code}    403

TC162 Admin Login Without A CSRF Token Is Rejected
    [Tags]    api    security
    ${response}=    POST    ${BASE_URL}/admin/login
    ...    data=${{ {'password': 'admin-test-password'} }}    expected_status=403
    Should Be Equal As Integers    ${response.status_code}    403

TC163 A Forged CSRF Token Is Rejected
    [Tags]    api    security
    ${response}=    POST    ${BASE_URL}/committee/login
    ...    data=${{ {'email': 'x@sai.edu', 'password': 'y', 'csrf_token': 'forged'} }}
    ...    expected_status=403
    Should Be Equal As Integers    ${response.status_code}    403

TC164 Review Submission Without A CSRF Token Is Rejected
    [Tags]    api    security
    ${response}=    POST    ${BASE_URL}/committee/submit    data=${FULL_RATING}
    ...    expected_status=any    allow_redirects=${FALSE}
    Should Contain    ${{ [302, 403] }}    ${response.status_code}

# ── SECTION 4: An authenticated session over HTTP ─────────────────────────

TC165 A Member Can Sign In And Submit Over Plain HTTP
    [Tags]    smoke    api    committee
    [Documentation]    Walks the whole flow with a session, harvesting the CSRF
    ...    token from each form the way a browser would.
    Reset Test Fixture
    Create Session    member    ${BASE_URL}

    ${page}=     GET On Session    member    /committee/login
    ${token}=    Extract Csrf Token    ${page.text}
    ${login}=    POST On Session    member    /committee/login
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'password': 'robot-test-password', 'csrf_token': $token} }}
    ...    expected_status=any
    Should Be Equal As Integers    ${login.status_code}    200

    ${form}=     GET On Session    member    /committee
    ${token}=    Extract Csrf Token    ${form.text}
    ${data}=     Copy Dictionary    ${FULL_RATING}
    Set To Dictionary    ${data}    csrf_token=${token}    review=Submitted over the API
    ${submit}=   POST On Session    member    /committee/submit    data=${data}
    Should Be Equal As Integers    ${submit.status_code}    200
    Should Contain    ${submit.text}    Review recorded

TC166 The Submitted Review Reaches The Dashboard
    [Tags]    api    committee
    ${response}=    GET    url=${BASE_URL}/dashboard/committee?token=${DASHBOARD_TOKEN}
    Should Contain    ${response.text}    Submitted over the API

TC167 A Second Submission The Same Day Is Refused
    [Tags]    api    committee
    Create Session    repeat    ${BASE_URL}
    ${page}=     GET On Session    repeat    /committee/login
    ${token}=    Extract Csrf Token    ${page.text}
    POST On Session    repeat    /committee/login
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'password': 'robot-test-password', 'csrf_token': $token} }}
    ...    expected_status=any

    ${page}=     GET On Session    repeat    /committee
    ${token}=    Extract Csrf Token    ${page.text}
    ${data}=     Copy Dictionary    ${FULL_RATING}
    Set To Dictionary    ${data}    csrf_token=${token}
    ${submit}=   POST On Session    repeat    /committee/submit    data=${data}
    ...    expected_status=any
    Should Contain    ${submit.text}    already reviewed

# ── SECTION 5: Validation ─────────────────────────────────────────────────

TC168 An Out Of Range Rating Is Rejected
    [Tags]    api    committee
    Reset Test Fixture
    Create Session    invalid    ${BASE_URL}
    ${page}=     GET On Session    invalid    /committee/login
    ${token}=    Extract Csrf Token    ${page.text}
    POST On Session    invalid    /committee/login
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'password': 'robot-test-password', 'csrf_token': $token} }}
    ...    expected_status=any

    ${page}=     GET On Session    invalid    /committee
    ${token}=    Extract Csrf Token    ${page.text}
    ${submit}=   POST On Session    invalid    /committee/submit
    ...    data=${{ {'taste': '9', 'quality': '4', 'variety': '4', 'hygiene': '4', 'menu': '4', 'csrf_token': $token} }}
    ...    expected_status=400
    Should Be Equal As Integers    ${submit.status_code}    400

TC169 A Missing Dimension Is Rejected
    [Tags]    api    committee
    Create Session    partial    ${BASE_URL}
    ${page}=     GET On Session    partial    /committee/login
    ${token}=    Extract Csrf Token    ${page.text}
    POST On Session    partial    /committee/login
    ...    data=${{ {'email': 'robot-test-member@sai.edu', 'password': 'robot-test-password', 'csrf_token': $token} }}
    ...    expected_status=any

    ${page}=     GET On Session    partial    /committee
    ${token}=    Extract Csrf Token    ${page.text}
    ${submit}=   POST On Session    partial    /committee/submit
    ...    data=${{ {'taste': '4', 'quality': '4', 'csrf_token': $token} }}
    ...    expected_status=400
    Should Contain    ${submit.text}    error-banner

# ── SECTION 6: Pre-existing endpoints ─────────────────────────────────────

TC170 Health Endpoint Still Responds
    [Tags]    smoke    api
    ${response}=    GET    ${BASE_URL}/health
    Should Be Equal As Integers    ${response.status_code}    200
    Should Be Equal    ${response.json()}[status]    ok

TC171 Student Form Still Serves
    [Tags]    smoke    api
    ${response}=    GET    ${BASE_URL}/
    Should Be Equal As Integers    ${response.status_code}    200
    Should Contain    ${response.text}    How was today's lunch overall?

TC172 Student Dashboard Still Serves
    [Tags]    smoke    api
    ${response}=    GET    url=${BASE_URL}/dashboard?token=${DASHBOARD_TOKEN}
    Should Be Equal As Integers    ${response.status_code}    200

*** Keywords ***
Extract Csrf Token
    [Arguments]    ${html}
    [Documentation]    Pulls the hidden CSRF field out of a rendered form, the
    ...    way a browser would before posting it back.
    ${match}=    Get Regexp Matches    ${html}
    ...    name="csrf_token" value="([^"]+)"    1
    Should Not Be Empty    ${match}    No CSRF token found in the page
    RETURN    ${match}[0]
