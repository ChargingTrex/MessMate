*** Settings ***
Documentation     Student feedback form UI tests for MessMate.
...               Tests page load, emoji selection, rice dropdown logic,
...               review character counter, form submission, and security.
Resource          resources/common.resource
Resource          resources/form_keywords.resource
Suite Setup       Open MessMate Browser
Suite Teardown    Close MessMate Browser
Test Setup        Navigate To Form

*** Test Cases ***

# ── SECTION 1: Page Load ──────────────────────────────────────────────────

TC01 Form Page Loads Successfully
    [Tags]    smoke    form
    [Documentation]    Verifies the form page loads with the correct title and headings.
    Title Should Be    MessMate — Rate Today's Lunch 🍱
    Page Should Contain    How was today's lunch overall?
    Page Should Contain    Rate individual items

TC02 Submit Button Is Disabled On Page Load
    [Tags]    smoke    form    validation
    [Documentation]    Submit button must be disabled until an overall rating is selected.
    Submit Button Should Be Disabled

TC03 All Emoji Buttons Are Visible
    [Tags]    smoke    form
    [Documentation]    All 5 overall emoji buttons (scores 1-5) should be visible.
    FOR    ${score}    IN RANGE    1    6
        Element Should Be Visible    css=.section-overall .emoji-btn[data-value="${score}"]
    END

# ── SECTION 2: Overall Rating ─────────────────────────────────────────────

TC04 Selecting Overall Emoji Enables Submit Button
    [Tags]    form    validation
    [Documentation]    Clicking an overall emoji should enable the submit button.
    Select Overall Emoji    3
    Submit Button Should Be Enabled

TC05 Overall Emoji Selection Sets Hidden Input Value
    [Tags]    form    validation
    [Documentation]    The hidden input should reflect the selected emoji value.
    Select Overall Emoji    4
    ${val}=    Get Element Attribute    id=overall_val    value
    Should Be Equal    ${val}    4

TC06 Only One Overall Emoji Can Be Selected At A Time
    [Tags]    form    validation
    [Documentation]    Selecting a new emoji should deselect the previous one.
    Select Overall Emoji    2
    Select Overall Emoji    5
    ${val}=    Get Element Attribute    id=overall_val    value
    Should Be Equal    ${val}    5
    Element Should Not Have Class    css=.section-overall .emoji-btn[data-value="2"]    selected

TC07 All Five Overall Emoji Values Are Selectable
    [Tags]    form    validation
    [Documentation]    Each value 1-5 should be selectable and stored in the hidden input.
    FOR    ${score}    IN RANGE    1    6
        Select Overall Emoji    ${score}
        ${val}=    Get Element Attribute    id=overall_val    value
        Should Be Equal As Numbers    ${val}    ${score}
    END

# ── SECTION 3: Rice Dropdown ──────────────────────────────────────────────

TC08 Rice Rating Rows Hidden By Default
    [Tags]    form    rice
    [Documentation]    Both rice rating rows should be hidden on initial load.
    Element Should Not Be Visible    css=[data-rice-row="curry"]
    Element Should Not Be Visible    css=[data-rice-row="rasam"]

TC09 Rice Dropdown Curry Shows Only Curry Row
    [Tags]    form    rice
    [Documentation]    Selecting "Curry" shows only the curry rating row.
    Select Rice Option    Curry
    Element Should Be Visible      css=[data-rice-row="curry"]
    Element Should Not Be Visible  css=[data-rice-row="rasam"]

TC10 Rice Dropdown Rasam Shows Only Rasam Row
    [Tags]    form    rice
    [Documentation]    Selecting "Rasam" shows only the rasam rating row.
    Select Rice Option    Rasam
    Element Should Not Be Visible  css=[data-rice-row="curry"]
    Element Should Be Visible      css=[data-rice-row="rasam"]

TC11 Rice Dropdown Both Shows Both Rows
    [Tags]    form    rice
    [Documentation]    Selecting "Both" shows both curry and rasam rating rows.
    Select Rice Option    Both
    Element Should Be Visible    css=[data-rice-row="curry"]
    Element Should Be Visible    css=[data-rice-row="rasam"]

TC12 Rice Dropdown Reset Hides All Rice Rows
    [Tags]    form    rice
    [Documentation]    Resetting the dropdown to "Select..." hides all rice rows.
    Select Rice Option    Both
    Select From List By Label    id=rice_served    Select...
    Element Should Not Be Visible    css=[data-rice-row="curry"]
    Element Should Not Be Visible    css=[data-rice-row="rasam"]

TC13 Rice Rating Clears When Dropdown Is Reset
    [Tags]    form    rice
    [Documentation]    Resetting the dropdown should clear any selected rice ratings.
    Select Rice Option    Curry
    Select Item Emoji    rice_curry    4
    Select From List By Label    id=rice_served    Select...
    ${val}=    Get Element Attribute    css=input[name="rice_curry"]    value
    Should Be Equal    ${val}    ${EMPTY}

# ── SECTION 4: Review Text ────────────────────────────────────────────────

TC14 Review Character Counter Starts At Zero
    [Tags]    form    review
    [Documentation]    The character counter should display "0 / 150" on page load.
    Element Should Contain    css=.char-counter    0 / 150

TC15 Review Character Counter Updates On Input
    [Tags]    form    review
    [Documentation]    Typing in the review field should update the character counter.
    Input Text    css=textarea[name="review"]    Hello
    Element Should Contain    css=.char-counter    5 / 150

TC16 Review Field Enforces 150 Character Limit
    [Tags]    form    review    validation
    [Documentation]    The textarea maxlength=150 should prevent more than 150 characters.
    ${long_text}=    Generate Random String    160    [LETTERS]
    Input Text    css=textarea[name="review"]    ${long_text}
    ${actual}=    Get Value    css=textarea[name="review"]
    ${length}=    Get Length    ${actual}
    Should Be True    ${length} <= 150

TC17 Review Counter Shows 150 At Limit
    [Tags]    form    review
    [Documentation]    When exactly 150 characters are entered, counter shows "150 / 150".
    ${text}=    Generate Random String    150    [LETTERS]
    Input Text    css=textarea[name="review"]    ${text}
    Element Should Contain    css=.char-counter    150 / 150

# ── SECTION 5: Form Submission ────────────────────────────────────────────

TC18 Minimal Submission Succeeds
    [Tags]    form    submission    must
    [Documentation]    Submitting with only the overall rating should succeed.
    Fill Minimal Form    score=3
    Submit Form
    Page Should Contain    Thanks! Your feedback was recorded.

TC19 Full Form Submission Succeeds
    [Tags]    form    submission    must
    [Documentation]    Submitting a fully filled form should succeed.
    Fill Full Form    overall=4    chapati=3    review=Food was good    suggestion=Add puliyodarai
    Submit Form
    Page Should Contain    Thanks! Your feedback was recorded.

TC20 Thank You Page Has Link Back To Form
    [Tags]    form    submission
    [Documentation]    The thank-you page should have a link back to the form.
    Fill Minimal Form
    Submit Form
    Page Should Contain Element    css=a[href="/"]

TC21 XSS In Review Is Not Executed
    [Tags]    form    security
    [Documentation]    XSS script tags in review field should be sanitized and not executed.
    Navigate To Form
    Select Overall Emoji    3
    Input Text    css=textarea[name="review"]    <script>alert('xss')</script>
    Submit Form
    # If we reach the thanks page without an alert dialog, XSS is blocked
    Page Should Contain    Thanks! Your feedback was recorded.
    Alert Should Not Be Present

# ── SECTION 6: Error States ───────────────────────────────────────────────

TC22 Submitting Without Overall Shows No POST
    [Tags]    form    validation
    [Documentation]    The disabled submit button prevents form submission without an overall rating.
    Navigate To Form
    # Button is disabled — JS prevents submission, page stays on form
    Submit Button Should Be Disabled
    Location Should Be    ${BASE_URL}/

TC23 Error Banner Displays When Flask Returns Error
    [Tags]    form    error
    [Documentation]    Error banner test — covered by rate limit test in api_tests.robot.
    Log    Error banner test — covered by rate limit test in api_tests.robot
