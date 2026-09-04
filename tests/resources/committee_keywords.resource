*** Settings ***
Documentation     Keywords for the Food Committee suite (login, rating, admin roster).
Resource          common.resource

*** Variables ***
${COMMITTEE_LOGIN_URL}    ${BASE_URL}/committee/login
${COMMITTEE_URL}          ${BASE_URL}/committee
${ADMIN_LOGIN_URL}        ${BASE_URL}/admin/login
${ADMIN_MEMBERS_URL}      ${BASE_URL}/admin/members
${COMMITTEE_DASH_URL}     ${BASE_URL}/dashboard/committee?token=${DASHBOARD_TOKEN}

# Supplied by CI secrets. TEST_MEMBER must already exist in the test
# spreadsheet with a known password; ADMIN_PASSWORD gates the roster UI.
${TEST_MEMBER_EMAIL}      %{TEST_COMMITTEE_EMAIL=robot-test-member@sai.edu}
${TEST_MEMBER_PASSWORD}   %{TEST_COMMITTEE_PASSWORD=robot-test-password}
${ADMIN_PASSWORD}         %{ADMIN_PASSWORD=admin-test-password}

*** Keywords ***
Navigate To Committee Login
    [Documentation]    Opens the committee login page.
    Go To    ${COMMITTEE_LOGIN_URL}
    Wait Until Page Contains Element    id=email    timeout=${TIMEOUT}

Login As Committee Member
    [Arguments]    ${email}=${TEST_MEMBER_EMAIL}    ${password}=${TEST_MEMBER_PASSWORD}
    [Documentation]    Signs in as a committee member and waits for the rating page.
    Navigate To Committee Login
    Input Text       id=email       ${email}
    Input Password   id=password    ${password}
    Click Element    id=login-btn

Login As Admin
    [Documentation]    Signs in to the admin roster UI.
    Go To    ${ADMIN_LOGIN_URL}
    Wait Until Page Contains Element    id=password    timeout=${TIMEOUT}
    Input Password   id=password    ${ADMIN_PASSWORD}
    Click Element    id=admin-login-btn
    Wait Until Page Contains Element    id=add-member-form    timeout=${TIMEOUT}

Rate Committee Dimension
    [Arguments]    ${dimension}    ${score}
    [Documentation]    Clicks the emoji button for one dimension (taste, quality, ...).
    Click Element    css=.emoji-btn[data-item="${dimension}"][data-value="${score}"]

Rate All Dimensions
    [Arguments]    ${score}=4
    [Documentation]    Rates all five dimensions with the same score.
    FOR    ${dimension}    IN    taste    quality    variety    hygiene    menu
        Rate Committee Dimension    ${dimension}    ${score}
    END

Add Committee Member Via UI
    [Arguments]    ${name}    ${email}
    [Documentation]    Adds one member through the admin UI. Assumes an admin session.
    Go To    ${ADMIN_MEMBERS_URL}
    Wait Until Page Contains Element    id=add-member-form    timeout=${TIMEOUT}
    Input Text       id=name     ${name}
    Input Text       id=email    ${email}
    Click Element    id=add-btn
    Wait Until Page Contains Element    css=.credential-banner    timeout=${TIMEOUT}

Get Revealed Password
    [Arguments]    ${email}
    [Documentation]    Reads the one-time password out of the credential banner.
    ${password}=    Get Text
    ...    xpath=//table[@class='credential-table']//td[normalize-space()='${email}']/following-sibling::td/code
    RETURN    ${password}

Deactivate Member
    [Arguments]    ${email}
    [Documentation]    Deactivates a member. Used in teardown so test members do
    ...    not accumulate in the shared test spreadsheet.
    Go To    ${ADMIN_MEMBERS_URL}
    ${present}=    Run Keyword And Return Status
    ...    Page Should Contain Element    xpath=//tr[@data-member-row='${email}']
    Run Keyword If    ${present}
    ...    Click Button    xpath=//tr[@data-member-row='${email}']//button[@value='deactivate']

Cleanup Test Members
    [Documentation]    Deactivates every robot-test-* member left behind.
    Run Keyword And Ignore Error    Login As Admin
    ${rows}=    Get WebElements    css=tr[data-member-row^="robot-test-"]
    FOR    ${row}    IN    @{rows}
        ${email}=    Get Element Attribute    ${row}    data-member-row
        Run Keyword And Ignore Error    Deactivate Member    ${email}
    END
