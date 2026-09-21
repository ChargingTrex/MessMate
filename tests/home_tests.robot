*** Settings ***
Documentation     Student home UI tests: today's menu, the one-tap reaction per
...               meal, the suggestion disclosure, and the admin menu editor
...               that publishes what students see.
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Suite Setup       Run Keywords    Reset Test Fixture    AND    Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Start With A Clean Session

*** Variables ***
${HOME_URL}          ${BASE_URL}/home
${MENU_EDITOR_URL}   ${BASE_URL}/admin/menu

*** Test Cases ***

# ── SECTION 1: The menu ───────────────────────────────────────────────────

TC180 Home Page Loads Without A Login
    [Tags]    smoke    home
    [Documentation]    The cheapest feedback surface must not ask for anything.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Title Should Be    MessMate — Today's Menu 🍽️
    Page Should Not Contain Element    id=password

TC181 All Three Meals Are Shown
    [Tags]    smoke    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    FOR    ${meal}    IN    Breakfast    Lunch    Dinner
        Page Should Contain Element    css=.meal-card[data-meal="${meal}"]
    END

TC182 Today's Dishes Are Listed As Separate Items
    [Tags]    home
    [Documentation]    The fixture publishes a comma-separated menu; each dish
    ...    should become its own chip rather than one run-on line.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    id=menu-lunch    timeout=${TIMEOUT}
    ${items}=    Get WebElements    css=#menu-lunch li
    Should Be True    len($items) > 1

TC183 Serving Times Are Shown
    [Tags]    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-time    timeout=${TIMEOUT}
    Page Should Contain    12:00

TC184 Each Meal Offers Good Bad And Skip
    [Tags]    smoke    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    FOR    ${rating}    IN    good    bad    skip
        ${buttons}=    Get WebElements    css=.rate-btn[data-rating="${rating}"]
        Length Should Be    ${buttons}    3
    END

# ── SECTION 2: Reacting ───────────────────────────────────────────────────

TC185 Tapping Good Records A Reaction
    [Tags]    smoke    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Click Element    css=.meal-card[data-meal="Lunch"] .rate-btn[data-rating="good"]
    Wait Until Page Contains Element    id=rated-banner    timeout=${TIMEOUT}
    Page Should Contain    lunch

TC186 Tapping Skip Is Recorded Too
    [Tags]    home
    [Documentation]    A skip is attendance data, not a missing answer.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Click Element    css=.meal-card[data-meal="Breakfast"] .rate-btn[data-rating="skip"]
    Wait Until Page Contains Element    id=rated-banner    timeout=${TIMEOUT}

TC187 A Tally Appears Once A Meal Has Been Rated
    [Tags]    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Click Element    css=.meal-card[data-meal="Dinner"] .rate-btn[data-rating="good"]
    Wait Until Page Contains Element    id=rated-banner    timeout=${TIMEOUT}
    Page Should Contain Element
    ...    css=.meal-card[data-meal="Dinner"] .tally-score

TC188 The Suggestion Box Is Hidden Until Asked For
    [Tags]    home
    [Documentation]    One tap is the point; the suggestion is opt-in.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    ${box}=    Get WebElement
    ...    css=.meal-card[data-meal="Lunch"] .suggestion-details .suggestion-input
    Element Should Not Be Visible    ${box}

TC189 Opening The Disclosure Reveals The Suggestion Field
    [Tags]    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Click Element    css=.meal-card[data-meal="Lunch"] .suggestion-details summary
    Wait Until Element Is Visible
    ...    css=.meal-card[data-meal="Lunch"] .suggestion-details .suggestion-input
    ...    timeout=${TIMEOUT}

TC190 A Suggestion Can Be Sent With A Reaction
    [Tags]    home
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.meal-card    timeout=${TIMEOUT}
    Click Element    css=.meal-card[data-meal="Lunch"] .suggestion-details summary
    Input Text
    ...    css=.meal-card[data-meal="Lunch"] .suggestion-details .suggestion-input
    ...    More curd please
    Click Element    css=.meal-card[data-meal="Lunch"] .rate-btn[data-rating="good"]
    Wait Until Page Contains Element    id=rated-banner    timeout=${TIMEOUT}

TC191 Home Links Through To The Detailed Form
    [Tags]    home
    [Documentation]    Students with more to say must be able to find the
    ...    per-dish form, which stays at /.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.detail-link    timeout=${TIMEOUT}
    Click Element    css=.detail-link
    Wait Until Page Contains Element    id=overall_val    timeout=${TIMEOUT}

# ── SECTION 3: The menu editor ────────────────────────────────────────────

TC192 Menu Editor Is Closed Without An Admin Session
    [Tags]    smoke    home    security
    Sign Out Of Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Location Should Contain    /admin/login

TC193 Dashboard Token Cannot Open The Menu Editor
    [Tags]    smoke    home    security
    [Documentation]    Same privilege boundary as member management: a token
    ...    that travels in a URL must not change what students are told.
    Sign Out Of Admin
    Go To    ${BASE_URL}/admin/menu?token=${DASHBOARD_TOKEN}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Page Should Not Contain Element    id=menu-editor

TC194 Menu Editor Opens For An Admin
    [Tags]    smoke    home
    Login As Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}
    ${days}=    Get WebElements    css=form[data-menu-day]
    Length Should Be    ${days}    7

TC195 Today Is Marked In The Editor
    [Tags]    home
    Login As Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}
    Page Should Contain Element    css=.menu-day-today

TC196 Publishing A Menu Reaches Students
    [Tags]    smoke    home
    [Documentation]    The whole point of the editor: what an admin types is
    ...    what a student sees, without a redeploy.
    Login As Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}
    ${today}=    Get Element Attribute    css=.menu-day-today form    data-menu-day
    Input Text    id=${today}-Lunch    Robot Biryani, Robot Raita
    Click Element    xpath=//form[@data-menu-day='${today}']//button[text()='Save']
    Wait Until Page Contains Element    css=.alert.success    timeout=${TIMEOUT}

    Go To    ${HOME_URL}
    Wait Until Page Contains Element    id=menu-lunch    timeout=${TIMEOUT}
    Page Should Contain    Robot Biryani
    Page Should Contain    Robot Raita

TC197 An Unpublished Day Says So
    [Tags]    home
    [Documentation]    Better than an empty card, which reads as "mess closed".
    Reset Test Fixture
    Login As Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}
    ${today}=    Get Element Attribute    css=.menu-day-today form    data-menu-day
    Input Text    id=${today}-Breakfast    ${EMPTY}
    Click Element    xpath=//form[@data-menu-day='${today}']//button[text()='Save']
    Wait Until Page Contains Element    css=.alert.success    timeout=${TIMEOUT}

    Go To    ${HOME_URL}
    Wait Until Page Contains Element    id=menu-breakfast    timeout=${TIMEOUT}
    Page Should Contain    Menu not published yet

# ── SECTION 4: Separation from the other feedback layers ──────────────────

TC198 The Per-Dish Form Is Untouched
    [Tags]    smoke    home
    [Documentation]    Regression guard: / keeps serving the detailed form, so
    ...    the printed QR codes still work.
    Navigate To Form
    Page Should Contain Element    id=overall_val
    Page Should Not Contain Element    css=.meal-card

TC199 The Committee Flow Is Unaffected
    [Tags]    home
    Navigate To Committee Login
    Page Should Contain Element    id=email
    Page Should Not Contain Element    css=.rate-btn
