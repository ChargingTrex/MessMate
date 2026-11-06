*** Settings ***
Documentation     Journey 7 — Google Sheets goes down mid-service, then comes back.
...
...               Every page a student, member, admin or VC might open during the
...               outage must still render — empty, with an honest message where
...               a write failed — and never a 500 page with a stack trace. Once
...               the backend recovers, everything is back without a restart and
...               nothing half-written was left behind.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    resilience

*** Test Cases ***
E07.01 Before The Outage Everything Has Data
    Open Visitor Session    probe
    ${rows}=    Get Stored Rows    responses
    Set Suite Variable    ${RESPONSES_BEFORE}    ${rows}
    ${rows}=    Get Stored Rows    committee_members
    Set Suite Variable    ${MEMBERS_BEFORE}    ${rows}
    Open Visitor Session    member
    ${response}=    Session Member Login    member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Response Should Redirect To    ${response}    /committee
    Login As Admin

E07.02 The Backend Starts Throwing
    Simulate Sheets Backend    raise

E07.03 The Health Check Still Answers
    [Documentation]    /health is for the host's uptime probe; it must not flap
    ...    every time Google has a bad minute.
    ${response}=    GET On Session    probe    /health    expected_status=200
    Should Be Equal    ${response.json()}[status]    ok

E07.04 Students Still Get The Home Page, With No Menu
    Become A New Visitor
    Open Student Home
    FOR    ${meal}    IN    breakfast    lunch    dinner
        Element Text Should Be    css=#menu-${meal} li.menu-empty    Menu not published yet
    END

E07.05 A Meal Reaction Fails Honestly
    Tap Meal Reaction    Lunch    good
    Element Should Contain    css=.error-banner    Couldn't save that just now
    Page Should Not Contain Element    id=rated-banner

E07.06 A Dish-By-Dish Submission Fails With A Message, Not A Crash
    Navigate To Form
    Select Overall Emoji    4
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.error-banner    timeout=${TIMEOUT}
    Element Should Contain    css=.error-banner    An error occurred saving your feedback.
    ${response}=    Submit Student Feedback Over HTTP    probe    overall=4
    Should Be Equal As Integers    ${response.status_code}    500
    Should Not Contain    ${response.text}    Traceback

E07.07 Both Dashboards Render Empty Instead Of Failing
    [Tags]    dashboard
    Open Student Dashboard
    Student Stat Should Be    Today's Average    --
    Student Stat Should Be    Responses Today    0
    Page Should Contain Element    css=.suggestions-list .empty-state
    Open Committee Dashboard
    Element Text Should Be    id=stat-today-avg          --
    Element Text Should Be    id=stat-active-members     0
    Page Should Contain    No written reviews yet.

E07.08 A Signed-In Member Is Sent To Log In, Not Shown An Error
    [Documentation]    The roster cannot be read, so the session cannot be
    ...    re-validated; the safe answer is to treat it as signed out.
    ${response}=    Get Without Redirect    member    /committee
    Response Should Redirect To    ${response}    /committee/login

E07.09 Committee Login Fails Like A Wrong Password, Not A 500
    Become A New Visitor
    Login As Committee Member    ${MEMBER_EMAIL}    ${MEMBER_PASSWORD}
    Login Should Be Refused

E07.10 Admin Writes Fail With A Clear Message
    Login As Admin
    Add Member Via UI    Outage Person    outage@sai.edu
    Element Should Contain    css=.error-banner    Could not save the new member.
    ${today}=    Today
    Publish Menu    ${today}    lunch=Outage Biryani
    Element Should Contain    css=.error-banner    Could not save the menu.

E07.11 Then The Backend Returns Nothing At All
    [Documentation]    The other failure shape: get_sheet() returns None rather
    ...    than raising, which the student write path reports differently.
    Simulate Sheets Backend    unavailable
    ${response}=    Submit Student Feedback Over HTTP    probe    overall=4
    Should Be Equal As Integers    ${response.status_code}    500
    Should Contain    ${response.text}    Failed to connect to Google Sheets
    GET On Session    probe    /home    expected_status=200
    GET On Session    probe    /dashboard    params=token=${DASHBOARD_TOKEN}    expected_status=200
    GET On Session    probe    /dashboard/committee    params=token=${DASHBOARD_TOKEN}    expected_status=200

E07.12 Google Recovers
    Simulate Sheets Backend    ok

E07.13 Nothing Was Half-Written During The Outage
    ${rows}=    Get Stored Rows    responses
    Should Be Equal    ${rows}    ${RESPONSES_BEFORE}
    ${rows}=    Get Stored Rows    committee_members
    Should Be Equal    ${rows}    ${MEMBERS_BEFORE}
    Stored Row Count Should Be    meal_ratings    0
    ${today}=    Today
    ${rows}=    Get Stored Rows Where    menu    Date    ${today}
    Should Not Contain    ${rows}[0][Lunch]    Outage

E07.14 Students Are Back Without A Restart
    Become A New Visitor
    Open Student Home
    Menu Items Should Be    Lunch    Rice    Sambar    Poriyal    Curd    Papad
    Tap Meal Reaction    Lunch    good
    Element Should Contain    id=rated-banner    your lunch rating was recorded
    Meal Tally Should Be    Lunch    100%    1

E07.15 The Committee And The Dashboards Are Back Too
    Login And Reach Rating Page
    Open Committee Dashboard
    Element Text Should Be    id=stat-active-members    3
    Page Should Contain    Historic review from day -1
    Open Student Dashboard
    Student Stat Should Be    Responses Today    1
