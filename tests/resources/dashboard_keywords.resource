*** Settings ***
Documentation     Keywords specific to the admin dashboard.
Resource          common.resource

*** Keywords ***
Get Stat Card Value
    [Arguments]    ${card_heading}
    [Documentation]    Returns the value text from a named stat card (e.g. "Today's Average").
    ${value}=    Get Text    xpath=//h3[contains(text(),"${card_heading}")]/following-sibling::p
    ${value}=    Strip String    ${value}
    RETURN    ${value}

Dashboard Should Show Average
    [Arguments]    ${expected}
    [Documentation]    Verifies the Today's Average stat card shows the expected value.
    ${avg}=    Get Stat Card Value    Today's Average
    Should Be Equal As Strings    ${avg}    ${expected}

Dashboard Should Show Response Count
    [Arguments]    ${expected}
    [Documentation]    Verifies the Responses Today stat card shows the expected count.
    ${count}=    Get Stat Card Value    Responses Today
    Should Be Equal As Numbers    ${count}    ${expected}

Chart Should Be Visible
    [Arguments]    ${chart_id}
    [Documentation]    Verifies a Chart.js canvas is present and has a 2D rendering context.
    Element Should Be Visible    id=${chart_id}
    ${rendered}=    Execute Javascript    return document.getElementById('${chart_id}').getContext('2d') !== null
    Should Be True    ${rendered}
