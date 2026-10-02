*** Settings ***
Documentation     Journey 3 — mess staff publish the menu, students react to it.
...
...               The admin corrects today's lunch and plans tomorrow in the menu
...               editor. Students then open the home page, see exactly what was
...               published, and tap good / bad / skip. The tally on each card,
...               and the rows behind it, are checked after every reaction.
...
...               Fixture: today's menu is seeded; no meal reactions exist yet.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    home    menu

*** Test Cases ***
E03.01 Admin Opens A Week Of Menus With Today Marked
    [Tags]    smoke
    Login As Admin
    Open Menu Editor
    ${days}=    Get WebElements    css=form[data-menu-day]
    Length Should Be    ${days}    7
    ${today}=    Today
    Element Attribute Value Should Be    id=${today}-Lunch    value
    ...    Rice, Sambar, Poriyal, Curd, Papad
    Page Should Contain Element    css=.menu-day-today form[data-menu-day="${today}"]

E03.02 Admin Corrects Today's Lunch
    ${today}=    Today
    Publish Menu    ${today}    lunch=Veg Biryani, Raita, Gulab Jamun
    Element Should Contain    css=.alert.success    Menu saved for ${today}.
    Element Attribute Value Should Be    id=${today}-Lunch    value    Veg Biryani, Raita, Gulab Jamun

E03.03 Admin Plans Tomorrow's Breakfast
    ${tomorrow}=    Days From Today    1
    Publish Menu    ${tomorrow}    breakfast=Pongal, Vada
    Element Should Contain    css=.alert.success    Menu saved for ${tomorrow}.

E03.04 Today Was Updated In Place And Tomorrow Appended
    [Documentation]    The editor upserts: saving a day twice must never create a
    ...    second row for it, or the home page would pick one at random.
    ${today}=    Today
    ${tomorrow}=    Days From Today    1
    ${rows}=    Get Stored Rows Where    menu    Date    ${today}
    Length Should Be    ${rows}    1
    Should Be Equal    ${rows}[0][Lunch]        Veg Biryani, Raita, Gulab Jamun
    Should Be Equal    ${rows}[0][Breakfast]    Idli, Sambar, Coconut Chutney
    ${rows}=    Get Stored Rows Where    menu    Date    ${tomorrow}
    Length Should Be    ${rows}    1
    Should Be Equal    ${rows}[0][Breakfast]    Pongal, Vada
    Stored Row Count Should Be    menu    2

E03.05 A Student Sees Today's Published Menu, Not Tomorrow's
    [Tags]    smoke
    Sign Out Of Admin
    Become A New Visitor
    Open Student Home
    Menu Items Should Be    Lunch        Veg Biryani    Raita    Gulab Jamun
    Menu Items Should Be    Breakfast    Idli    Sambar    Coconut Chutney
    Page Should Not Contain    Pongal
    FOR    ${meal}    IN    Breakfast    Lunch    Dinner
        Meal Should Have No Tally    ${meal}
    END

E03.06 First Student Likes Lunch And Leaves A Suggestion
    Tap Meal Reaction    Lunch    good    More raita please
    Element Should Contain    id=rated-banner    your lunch rating was recorded
    Meal Tally Should Be    Lunch    100%    1

E03.07 Second Student Disliked Lunch
    Become A New Visitor
    Open Student Home
    Tap Meal Reaction    Lunch    bad
    Meal Tally Should Be    Lunch    50%    2

E03.08 Third Student Skipped Lunch, Which Does Not Move The Score
    [Documentation]    Score is good / (good + bad). A skip is attendance, not a
    ...    verdict on the food, so it adds to the count and not the percentage.
    Become A New Visitor
    Open Student Home
    Tap Meal Reaction    Lunch    skip
    Meal Tally Should Be    Lunch    50%    3
    Element Should Have Class    css=.meal-card[data-meal="Lunch"] .tally-score    tally-mixed

E03.09 Only Lunch Has A Tally
    Meal Should Have No Tally    Breakfast
    Meal Should Have No Tally    Dinner

E03.10 Reactions Were Stored Anonymously
    ${headers}=    Get Stored Headers    meal_ratings
    Lists Should Be Equal    ${headers}    ${MEAL_RATING_HEADERS}
    ${rows}=    Get Stored Rows    meal_ratings
    Length Should Be    ${rows}    3
    ${ratings}=    Evaluate    [r['Rating'] for r in $rows]
    Lists Should Be Equal    ${ratings}    ${{ ['good', 'bad', 'skip'] }}
    Should Be Equal    ${rows}[0][Suggestion]    More raita please
    ${today}=    Today
    FOR    ${row}    IN    @{rows}
        Should Be Equal    ${row}[Meal]    Lunch
        Should Be Equal    ${row}[Date]    ${today}
    END

E03.11 A Tampered Reaction Is Refused With A Banner
    [Tags]    validation    security
    Open Visitor Session    tamper
    ${response}=    Tap Meal Over HTTP    tamper    Lunch    excellent
    Response Should Redirect To    ${response}    rated=invalid
    ${response}=    Tap Meal Over HTTP    tamper    Supper    good
    Response Should Redirect To    ${response}    rated=invalid
    Stored Row Count Should Be    meal_ratings    3
    Go To    ${HOME_URL}?rated=invalid
    Element Should Contain    css=.error-banner    Please pick good, bad or skip.

E03.12 Admin Clears Dinner And Students See It Unpublished
    Login As Admin
    ${today}=    Today
    Publish Menu    ${today}    dinner=${EMPTY}
    Sign Out Of Admin
    Become A New Visitor
    Open Student Home
    Element Text Should Be    css=#menu-dinner li.menu-empty    Menu not published yet
    Menu Items Should Be    Lunch    Veg Biryani    Raita    Gulab Jamun

E03.13 A Student Cannot Reach The Editor
    [Tags]    security
    Become A New Visitor
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=admin-login-btn    timeout=${TIMEOUT}
    Location Should Contain    /admin/login
    Page Should Not Contain Element    id=menu-editor
