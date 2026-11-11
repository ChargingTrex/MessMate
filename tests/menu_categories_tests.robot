*** Settings ***
Documentation     Menu categories and CSV upload layouts, in a real browser.
...               An admin types a categorised menu or uploads the mess's
...               weekly grid; students see each category beside its dishes,
...               on the card, in the day switcher and at phone width; the
...               committee form still rates bare dish names.
...
...               Run against the in-memory backend (test/fake_server.py), one
...               suite at a time. Test IDs match
...               docs/TEST_PLAN.md (TC200–TC210).
Resource          resources/common.resource
Resource          resources/committee_keywords.resource
Library           OperatingSystem
Suite Setup       Run Keywords    Reset Test Fixture    AND    Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Start With A Clean Session

*** Variables ***
${HOME_URL}          ${BASE_URL}/home
${MENU_EDITOR_URL}   ${BASE_URL}/admin/menu
${CSV_DIR}           ${OUTPUT DIR}${/}menu-csv

*** Test Cases ***

# ── SECTION 1: Typing categories in the editor ────────────────────────────

TC200 Editor Explains The Category Format
    [Tags]    smoke    menu    categories
    [Documentation]    The format is only usable if the editor says what it is.
    Open Menu Editor
    Page Should Contain    Category: Dish
    Page Should Contain    Meal, Category
    ${href}=    Get Element Attribute    xpath=//a[text()='Download blank template']    href
    Should Contain    ${href}    /admin/menu/template.csv?start=

TC201 A Categorised Menu Shows Each Category Beside Its Dishes
    [Tags]    critical    menu    categories    home
    [Documentation]    Two Spread rows read as one line; order is the mess's.
    Open Menu Editor
    ${today}=    Today In Editor
    Save Editor Meal    ${today}    Breakfast
    ...    Main Item: Robot Pongal\nSpread: Butter\nSpread: Jam\nBeverage: Coffee
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=#menu-breakfast.menu-items-categorised    timeout=${TIMEOUT}
    Element Text Should Be    css=#menu-breakfast li:nth-child(1) .menu-cat     Main Item
    Element Text Should Be    css=#menu-breakfast li:nth-child(1) .menu-dish    Robot Pongal
    Element Text Should Be    css=#menu-breakfast li:nth-child(2) .menu-dish    Butter, Jam
    Element Text Should Be    css=#menu-breakfast li:nth-child(3) .menu-cat     Beverage
    ${lines}=    Get Element Count    css=#menu-breakfast li
    Should Be Equal As Integers    ${lines}    3

TC202 Template Rows Left Blank Are Not Published
    [Tags]    menu    categories
    [Documentation]    "Egg:" with nothing after it must not count as a menu.
    Open Menu Editor
    ${today}=    Today In Editor
    Save Editor Meal    ${today}    Breakfast    Egg:\nBread:
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    id=menu-breakfast    timeout=${TIMEOUT}
    Element Should Contain    id=menu-breakfast    Menu not published yet

TC203 A Menu Without Categories Keeps Its Chips
    [Tags]    menu    categories    regression
    [Documentation]    The fixture's lunch is a plain comma list.
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    id=menu-lunch    timeout=${TIMEOUT}
    Page Should Not Contain Element    css=#menu-lunch.menu-items-categorised
    Page Should Not Contain Element    css=#menu-lunch .menu-cat
    ${chips}=    Get Element Count    css=#menu-lunch li
    Should Be True    ${chips} > 1

# ── SECTION 2: Uploading the mess's weekly grid ───────────────────────────

TC204 A Grid Upload Publishes Categories And Skips Snacks
    [Tags]    critical    menu    upload
    [Documentation]    Day-first dates, a merged Meal cell, a Snacks block and
    ...    a Notes column — the sheet as the mess writes it.
    ${d1}    ${d1_dmy}=    Date From Today    1
    ${d2}    ${d2_dmy}=    Date From Today    2
    ${csv}=    Catenate    SEPARATOR=\n
    ...    Meal,Category,${d1_dmy},${d2_dmy},Notes
    ...    ,,Tomorrow,Day after,
    ...    Breakfast,Main Item,Robot Sevai,Robot Idly,from the mess
    ...    ,Spread,Butter,Butter,
    ...    ,Spread,Jam,Jam,
    ...    Snacks,Snack 1 ( Fried ),Aloo Samosa,Veg Puff,
    ...    Dinner,Korma,Robot Kurma,,
    Upload Menu CSV    grid.csv    ${csv}
    Element Should Contain    css=.alert.success    Imported 2 days.
    Element Should Contain    css=.alert.success    Skipped Snacks
    Go To    ${HOME_URL}?date=${d1}
    Wait Until Page Contains Element    css=#menu-breakfast.menu-items-categorised    timeout=${TIMEOUT}
    Element Text Should Be    css=#menu-breakfast li:nth-child(1) .menu-dish    Robot Sevai
    Element Text Should Be    css=#menu-breakfast li:nth-child(2) .menu-dish    Butter, Jam
    Element Text Should Be    css=#menu-dinner li:nth-child(1) .menu-cat        Korma
    Page Should Not Contain    Aloo Samosa
    Page Should Not Contain    from the mess

TC205 The Day Switcher Renders Uploaded Categories
    [Tags]    menu    upload    home
    [Documentation]    Switching days is client-side; home.js must build the
    ...    same category lines the server renders.
    ${d1}    ${d1_dmy}=    Date From Today    1
    ${csv}=    Catenate    SEPARATOR=\n
    ...    Meal,Category,${d1}
    ...    Lunch,Rice,Robot Biryani
    ...    ,Curd,Robot Raitha
    Upload Menu CSV    switch.csv    ${csv}
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=.day-tab[data-date="${d1}"]    timeout=${TIMEOUT}
    Click Element    css=.day-tab[data-date="${d1}"]
    Wait Until Page Contains Element    css=#menu-lunch.menu-items-categorised    timeout=${TIMEOUT}
    Element Text Should Be    css=#menu-lunch li:nth-child(1) .menu-cat     Rice
    Element Text Should Be    css=#menu-lunch li:nth-child(2) .menu-dish    Robot Raitha

TC206 The Older Layout Still Uploads
    [Tags]    menu    upload    regression
    ${d1}    ${d1_dmy}=    Date From Today    1
    ${csv}=    Catenate    SEPARATOR=\n
    ...    Date,Breakfast,Lunch,Dinner
    ...    ${d1},"Robot Dosa, Robot Chutney",,
    Upload Menu CSV    old.csv    ${csv}
    Element Should Contain    css=.alert.success    Imported 1 day.
    Go To    ${HOME_URL}?date=${d1}
    Wait Until Page Contains Element    id=menu-breakfast    timeout=${TIMEOUT}
    Page Should Not Contain Element    css=#menu-breakfast.menu-items-categorised
    Element Should Contain    id=menu-breakfast    Robot Dosa

TC207 A Grid Without Dates Is Refused
    [Tags]    menu    upload    validation
    ${csv}=    Catenate    SEPARATOR=\n
    ...    Meal,Category,Monday
    ...    Lunch,Rice,Robot Rice
    Upload Menu CSV    nodates.csv    ${csv}
    Page Should Show Error    No date columns found.

TC208 A File In Neither Layout Is Refused
    [Tags]    menu    upload    validation
    ${csv}=    Catenate    SEPARATOR=\n
    ...    Day,Food
    ...    Monday,Rice
    Upload Menu CSV    wrong.csv    ${csv}
    Page Should Show Error    CSV needs a header row

# ── SECTION 3: Layout and the other surfaces ──────────────────────────────

TC209 A Categorised Card Fits A Phone Screen
    [Tags]    menu    categories    responsive
    [Documentation]    The label column must not push the page sideways at 390px.
    Open Menu Editor
    ${today}=    Today In Editor
    Save Editor Meal    ${today}    Lunch
    ...    Podi / Oil & Thogayal: Curry Leaves Podi & Oil\nSambar / Kulambu: Mix Vathal Kara Kuzhambu
    Emulate Phone Width    390
    Go To    ${HOME_URL}
    Wait Until Page Contains Element    css=#menu-lunch.menu-items-categorised    timeout=${TIMEOUT}
    ${width}=    Execute JavaScript    return window.innerWidth
    ${fits}=    Execute JavaScript
    ...    return document.documentElement.scrollWidth <= window.innerWidth
    Stop Emulating Phone Width
    Should Be Equal As Integers    ${width}    390    The viewport never reached phone width
    Should Be True    ${fits}    The page scrolls sideways at phone width

TC210 The Committee Form Rates Bare Dish Names
    [Tags]    menu    categories    committee
    [Documentation]    Categories are for reading; ratings key on the dish.
    Open Menu Editor
    ${today}=    Today In Editor
    Save Editor Meal    ${today}    Breakfast    Main Item: Robot Pongal\nChutney: Robot Chutney
    Delete All Cookies
    Login And Reach Rating Page
    Go To    ${COMMITTEE_URL}?meal=Breakfast
    Wait Until Page Contains Element    css=[data-dish-name="Robot Pongal"]    timeout=${TIMEOUT}
    Page Should Contain Element    css=[data-dish-name="Robot Chutney"]
    Page Should Not Contain    Main Item:

*** Keywords ***
Open Menu Editor
    [Documentation]    Signs in as admin and opens this week's editor.
    Login As Admin
    Go To    ${MENU_EDITOR_URL}
    Wait Until Page Contains Element    id=menu-editor    timeout=${TIMEOUT}

Today In Editor
    [Documentation]    Today's date as the editor marks it (YYYY-MM-DD).
    ${today}=    Get Element Attribute    css=.menu-day-today form    data-menu-day
    RETURN    ${today}

Save Editor Meal
    [Arguments]    ${date}    ${meal}    ${text}
    [Documentation]    Types one meal for one day and saves that day.
    Input Text    id=${date}-${meal}    ${text}
    Click Element    xpath=//form[@data-menu-day='${date}']//button[text()='Save']
    Wait Until Page Contains Element    css=.alert.success    timeout=${TIMEOUT}

Emulate Phone Width
    [Arguments]    ${width}
    [Documentation]    A headless window resized to 390px still lays out wider,
    ...    so the viewport is set through the DevTools protocol instead.
    ${lib}=    Get Library Instance    SeleniumLibrary
    Call Method    ${lib.driver}    execute_cdp_cmd    Emulation.setDeviceMetricsOverride
    ...    ${{ {"width": int($width), "height": 900, "deviceScaleFactor": 1, "mobile": True} }}

Stop Emulating Phone Width
    ${lib}=    Get Library Instance    SeleniumLibrary
    Call Method    ${lib.driver}    execute_cdp_cmd    Emulation.clearDeviceMetricsOverride    ${{ {} }}

Date From Today
    [Arguments]    ${days}
    [Documentation]    Returns the date ${days} from today as YYYY-MM-DD and
    ...    as DD-MM-YYYY, the mess sheet's own format.
    ${iso}=    Evaluate
    ...    (datetime.date.today() + datetime.timedelta(days=${days})).isoformat()    modules=datetime
    ${dmy}=    Evaluate
    ...    (datetime.date.today() + datetime.timedelta(days=${days})).strftime('%d-%m-%Y')    modules=datetime
    RETURN    ${iso}    ${dmy}

Upload Menu CSV
    [Arguments]    ${name}    ${content}
    [Documentation]    Writes ${content} to a CSV file and uploads it through
    ...    the editor's import form as a signed-in admin.
    Create File    ${CSV_DIR}${/}${name}    ${content}
    Open Menu Editor
    Choose File    id=menu-csv    ${CSV_DIR}${/}${name}
    Click Element    css=#menu-import-form button[type="submit"]
    Wait Until Page Contains Element    css=.alert    timeout=${TIMEOUT}
