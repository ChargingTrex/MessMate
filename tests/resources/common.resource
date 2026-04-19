*** Settings ***
Documentation     Shared keywords and variables for MessMate Robot Framework tests.
Library           SeleniumLibrary
Library           RequestsLibrary
Library           Collections
Library           String
Library           DateTime

*** Variables ***
${BASE_URL}           http://localhost:5000
${DASHBOARD_TOKEN}    vc2026
${DASHBOARD_URL}      ${BASE_URL}/dashboard?token=${DASHBOARD_TOKEN}
${BROWSER}            chrome
${HEADLESS}           ${TRUE}
${TIMEOUT}            10s

*** Keywords ***
Open MessMate Browser
    [Documentation]    Opens Chrome (headless by default) and navigates to the form.
    ${options}=    Evaluate    sys.modules['selenium.webdriver'].ChromeOptions()    sys, selenium.webdriver
    Run Keyword If    ${HEADLESS}    Call Method    ${options}    add_argument    --headless
    Call Method    ${options}    add_argument    --no-sandbox
    Call Method    ${options}    add_argument    --disable-dev-shm-usage
    Call Method    ${options}    add_argument    --disable-gpu
    Open Browser    ${BASE_URL}    ${BROWSER}    options=${options}
    Set Selenium Timeout    ${TIMEOUT}
    Maximize Browser Window

Close MessMate Browser
    [Documentation]    Closes all open browser instances.
    Close All Browsers

Navigate To Form
    [Documentation]    Navigates to the student feedback form and waits for it to load.
    Go To    ${BASE_URL}
    Wait Until Page Contains Element    id=overall_val    timeout=${TIMEOUT}

Navigate To Dashboard
    [Documentation]    Navigates to the admin dashboard with the correct token.
    Go To    ${DASHBOARD_URL}
    Wait Until Page Contains Element    css=.stat-cards    timeout=${TIMEOUT}

Select Overall Emoji
    [Arguments]    ${score}
    [Documentation]    Clicks the overall emoji button for the given score (1-5).
    ...    Uses the section-overall scoped selector to avoid matching item emojis.
    Click Element    css=.section-overall .emoji-btn[data-value="${score}"]
    Wait Until Element Is Enabled    id=submit-btn    timeout=${TIMEOUT}

Select Item Emoji
    [Arguments]    ${item_name}    ${score}
    [Documentation]    Selects an emoji rating for a specific item by data-item attribute.
    Click Element    css=.emoji-btn[data-item="${item_name}"][data-value="${score}"]

Submit Form
    [Documentation]    Clicks the submit button and waits for the thanks page to load.
    Click Element    id=submit-btn
    Wait Until Page Contains Element    css=.thanks-container    timeout=${TIMEOUT}

Page Should Show Error
    [Arguments]    ${message}
    [Documentation]    Verifies the error banner is visible and contains the expected message.
    Element Should Be Visible    css=.error-banner
    Page Should Contain    ${message}

Element Should Have Class
    [Arguments]    ${locator}    ${class_name}
    [Documentation]    Verifies that an element has the specified CSS class.
    ${classes}=    Get Element Attribute    ${locator}    class
    Should Contain    ${classes}    ${class_name}

Element Should Not Have Class
    [Arguments]    ${locator}    ${class_name}
    [Documentation]    Verifies that an element does NOT have the specified CSS class.
    ${classes}=    Get Element Attribute    ${locator}    class
    Should Not Contain    ${classes}    ${class_name}
