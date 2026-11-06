*** Settings ***
Documentation     Journey 1 — a student rates lunch dish by dish, and the VC sees it.
...
...               Starts on the student home page, follows the link to the
...               per-dish form, submits a partial rating, then follows the data:
...               the stored row, the daily_summary upsert, and the stakeholder
...               dashboard's stat cards and suggestion board.
...
...               Fixture: one student response already exists today (overall 4),
...               so after this journey today holds two.
Resource          resources/e2e.resource
Suite Setup       Begin Journey
Suite Teardown    End Journey
Test Setup        Continue Journey
Test Teardown     Record Step Outcome
Test Tags         e2e    student

*** Variables ***
${REVIEW}          Rasam was too salty but the chapati was soft
${SUGGESTION}      Paneer & peas on Fridays

*** Test Cases ***
E01.01 Student Finds The Detailed Form From The Home Page
    [Tags]    smoke
    Open Student Home
    Click Link    css=a.detail-link
    Wait Until Page Contains Element    id=feedbackForm    timeout=${TIMEOUT}
    Location Should Be    ${BASE_URL}/
    Element Should Be Disabled    id=submit-btn

E01.02 Student Rates Overall And Only The Dishes Served
    Select Overall Emoji    5
    Choose Rice Served    both
    Wait Until Element Is Visible    id=rice_curry_container
    Wait Until Element Is Visible    id=rice_rasam_container
    Select Item Emoji    rice_curry    4
    Select Item Emoji    rice_rasam    3
    Select Item Emoji    chapati       5
    Select Item Emoji    curd          2
    Element Attribute Value Should Be    id=overall_val       value    5
    Element Attribute Value Should Be    id=rice_curry_val    value    4
    Element Attribute Value Should Be    id=rice_rasam_val    value    3
    Element Attribute Value Should Be    id=chapati_val       value    5
    Element Attribute Value Should Be    id=curd_val          value    2
    Element Attribute Value Should Be    id=poriyal_val       value    ${EMPTY}

E01.03 Student Changes Their Mind About Chapati
    [Documentation]    Re-tapping a group replaces the value; only one stays selected.
    Select Item Emoji    chapati    4
    Element Attribute Value Should Be    id=chapati_val    value    4
    ${selected}=    Get WebElements    css=.emoji-group[data-input="chapati_val"] .emoji-btn.selected
    Length Should Be    ${selected}    1

E01.04 Student Writes A Review And A Suggestion
    Type Review        ${REVIEW}
    ${length}=    Get Length    ${REVIEW}
    Element Text Should Be    id=char-counter    ${length} / 150
    Type Suggestion    ${SUGGESTION}

E01.05 Submission Lands On The Anonymous Thank-You Page
    [Tags]    smoke
    Submit Form
    Location Should Be    ${BASE_URL}/thanks
    Page Should Contain    Thanks! Your feedback was recorded.
    Page Should Contain    completely anonymous

E01.06 Exactly The Rated Dishes Were Stored
    ${row}=    Get Last Stored Row    responses
    Should Be Equal As Integers    ${row}[Overall]       5
    Should Be Equal As Integers    ${row}[Rice_Curry]    4
    Should Be Equal As Integers    ${row}[Rice_Rasam]    3
    Should Be Equal As Integers    ${row}[Chapati]       4
    Should Be Equal As Integers    ${row}[Curd]          2
    FOR    ${unrated}    IN    Chapati_Gravy    Poriyal    Sweet    Salad    Papad    Pickle
        Should Be Equal    ${row}[${unrated}]    ${EMPTY}    ${unrated} should be blank, not 0.
    END
    Should Be Equal    ${row}[Review]        ${REVIEW}
    Should Be Equal    ${row}[Suggestion]    ${SUGGESTION}    Suggestion must be stored raw, not escaped.
    ${today}=    Today
    Should Start With    ${row}[Timestamp]    ${today}

E01.07 Nothing Identifying Was Stored
    [Documentation]    The anonymity promise, checked at the storage layer.
    ${headers}=    Get Stored Headers    responses
    Lists Should Be Equal    ${headers}    ${RESPONSE_HEADERS}
    Stored Row Count Should Be    responses    4

E01.08 Daily Summary Was Upserted For Today
    ${today}=    Today
    ${rows}=    Get Stored Rows Where    daily_summary    Date    ${today}
    Length Should Be    ${rows}    1    Today must have exactly one summary row.
    Should Be Equal As Integers    ${rows}[0][Response_Count]    2
    Should Be Equal As Numbers     ${rows}[0][Avg_Overall]       4.5
    # Fixture rated rice-curry 4; this student rated it 4 as well
    Should Be Equal As Numbers     ${rows}[0][Avg_Rice_Curry]    4.0

E01.09 Another Response Can Be Started From The Thank-You Page
    Go To    ${BASE_URL}/thanks
    Click Link    Submit another response
    Wait Until Page Contains Element    id=feedbackForm    timeout=${TIMEOUT}
    Element Should Be Disabled    id=submit-btn
    Element Attribute Value Should Be    id=overall_val    value    ${EMPTY}

E01.10 VC Sees Today's Count And Average Update
    [Tags]    smoke    dashboard
    Become A New Visitor
    Open Student Dashboard
    Student Stat Should Be    Responses Today    2
    Student Stat Should Be    Today's Average    4.5
    Element Should Have Class    xpath=//div[contains(concat(' ',@class,' '),' stat-card ')][.//h3[normalize-space()="Today's Average"]]
    ...    score-green

E01.11 VC Sees The Suggestion First, Escaped Exactly Once
    [Tags]    dashboard    security
    Element Text Should Be    css=.suggestions-list .suggestion-item:first-child .suggestion-text
    ...    "${SUGGESTION}"
    Page Should Not Contain    &amp;

E01.12 The Dashboard Is Still Closed Without The Token
    [Tags]    security
    Become A New Visitor
    Go To    ${BASE_URL}/dashboard
    Page Should Contain    Access denied
    Page Should Not Contain Element    css=.stat-cards
