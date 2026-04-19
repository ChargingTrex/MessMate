*** Settings ***
Documentation     Admin dashboard UI tests for MessMate.
...               Tests access control, stat cards, chart rendering,
...               toggle buttons, and suggestions section.
Resource          resources/common.resource
Resource          resources/dashboard_keywords.resource
Suite Setup       Open MessMate Browser
Suite Teardown    Close MessMate Browser

*** Test Cases ***

# ── SECTION 1: Access Control ─────────────────────────────────────────────

TC24 Dashboard Without Token Returns 403
    [Tags]    dashboard    security    must
    [Documentation]    Accessing the dashboard without a token should show "Access denied".
    Go To    ${BASE_URL}/dashboard
    Page Should Contain    Access denied

TC25 Dashboard With Wrong Token Returns 403
    [Tags]    dashboard    security    must
    [Documentation]    Accessing the dashboard with an incorrect token should show "Access denied".
    Go To    ${BASE_URL}/dashboard?token=wrongtoken
    Page Should Contain    Access denied

TC26 Dashboard With Correct Token Loads Successfully
    [Tags]    dashboard    smoke    must
    [Documentation]    Accessing the dashboard with the correct token should load successfully.
    Navigate To Dashboard
    Title Should Be    MessMate — Admin Dashboard 📊
    Page Should Contain    MessMate Admin Dashboard

# ── SECTION 2: Stat Cards ─────────────────────────────────────────────────

TC27 All Three Stat Cards Are Present
    [Tags]    dashboard    smoke
    [Documentation]    The dashboard should display all three stat cards.
    Navigate To Dashboard
    Page Should Contain    Today's Average
    Page Should Contain    Responses Today
    Page Should Contain    Today's Date

TC28 Today Date Card Shows Correct Day
    [Tags]    dashboard    smoke
    [Documentation]    The date card should show today's date in the correct format.
    Navigate To Dashboard
    ${today}=    Get Current Date    result_format=%A, %d %B %Y
    ${card_val}=    Get Stat Card Value    Today's Date
    Should Be Equal    ${card_val}    ${today}

TC29 Average Card Shows Dashes When No Data
    [Tags]    dashboard    empty-state
    [Documentation]    When there's no data, the average card should show "--" or a valid number.
    Navigate To Dashboard
    ${avg}=    Get Stat Card Value    Today's Average
    # Either shows "--" (no data) or a valid score like "3.5"
    Should Match Regexp    ${avg}    (--|[1-5]\\.[0-9])

TC30 Average Card Has Correct Colour Class
    [Tags]    dashboard    visual
    [Documentation]    The average card should have the correct color class based on the score.
    Navigate To Dashboard
    ${avg_text}=    Get Stat Card Value    Today's Average
    ${has_score}=    Run Keyword And Return Status    Should Match Regexp    ${avg_text}    [1-5]\\.[0-9]
    IF    ${has_score}
        ${avg}=    Convert To Number    ${avg_text}
        ${classes}=    Get Element Attribute    css=.stat-card:first-child    class
        IF    ${avg} < 2.5
            Should Contain    ${classes}    score-red
        ELSE IF    ${avg} <= 3.5
            Should Contain    ${classes}    score-amber
        ELSE
            Should Contain    ${classes}    score-green
        END
    END

# ── SECTION 3: Charts ─────────────────────────────────────────────────────

TC31 Trend Chart Canvas Is Present And Rendered
    [Tags]    dashboard    charts
    [Documentation]    The trend line chart canvas should be visible and have a rendering context.
    Navigate To Dashboard
    Chart Should Be Visible    trendChart

TC32 Item Chart Canvas Is Present And Rendered
    [Tags]    dashboard    charts
    [Documentation]    The item bar chart canvas should be visible and have a rendering context.
    Navigate To Dashboard
    # Item chart may show empty state text instead of canvas when no data
    ${has_canvas}=    Run Keyword And Return Status    Element Should Be Visible    id=itemChart
    IF    ${has_canvas}
        Chart Should Be Visible    itemChart
    ELSE
        Page Should Contain    No item ratings yet
    END

TC33 Trend Chart Defaults To 7 Day View
    [Tags]    dashboard    charts
    [Documentation]    On load, the trend chart should default to 7-day view.
    Navigate To Dashboard
    Element Should Have Class    id=btn7Days    active
    Element Should Not Have Class    id=btn30Days    active
    Element Should Contain    id=trendChartTitle    7-Day

TC34 Trend Chart Toggle Switches To 30 Days
    [Tags]    dashboard    charts
    [Documentation]    Clicking "1 Month" button should switch to 30-day view.
    Navigate To Dashboard
    Click Element    id=btn30Days
    Element Should Have Class    id=btn30Days    active
    Element Should Not Have Class    id=btn7Days    active
    Element Should Contain    id=trendChartTitle    30-Day

TC35 Trend Chart Toggle Switches Back To 7 Days
    [Tags]    dashboard    charts
    [Documentation]    Toggling back to "7 Days" should restore the 7-day view.
    Navigate To Dashboard
    Click Element    id=btn30Days
    Click Element    id=btn7Days
    Element Should Have Class    id=btn7Days    active
    Element Should Contain    id=trendChartTitle    7-Day

# ── SECTION 4: Suggestions ────────────────────────────────────────────────

TC36 Suggestions Section Is Present
    [Tags]    dashboard    suggestions
    [Documentation]    The suggestions heading should be visible on the dashboard.
    Navigate To Dashboard
    Page Should Contain    Student Suggestions

TC37 Empty Suggestions Shows Friendly Message
    [Tags]    dashboard    suggestions    empty-state
    [Documentation]    When there are no suggestions, a friendly empty-state message should show.
    Navigate To Dashboard
    ${has_suggestions}=    Run Keyword And Return Status
    ...    Page Should Contain Element    css=.suggestion-item
    Run Keyword Unless    ${has_suggestions}
    ...    Page Should Contain    No suggestions yet

TC38 Suggestions Do Not Show Raw HTML Entities
    [Tags]    dashboard    security
    [Documentation]    Suggestions should not display double-escaped entities like &amp;
    Navigate To Dashboard
    Page Should Not Contain    &amp;
    Page Should Not Contain    &lt;
    Page Should Not Contain    &gt;
