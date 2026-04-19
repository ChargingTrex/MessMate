*** Settings ***
Documentation     Keywords specific to the student feedback form.
Resource          common.resource

*** Keywords ***
Fill Minimal Form
    [Arguments]    ${score}=3
    [Documentation]    Fills only the required Overall rating.
    Navigate To Form
    Select Overall Emoji    ${score}

Fill Full Form
    [Arguments]    ${overall}=4    ${chapati}=3    ${review}=Test review    ${suggestion}=Test suggestion
    [Documentation]    Fills the form with overall rating, one item, review, and suggestion.
    Navigate To Form
    Select Overall Emoji    ${overall}
    Select Item Emoji    chapati    ${chapati}
    Input Text    css=textarea[name="review"]    ${review}
    Input Text    css=input[name="suggestion"]    ${suggestion}

Select Rice Option
    [Arguments]    ${option}
    [Documentation]    Selects from the Rice dropdown: Curry, Rasam, or Both.
    Select From List By Label    id=rice_served    ${option}

Submit Button Should Be Disabled
    [Documentation]    Verifies the submit button is disabled (greyed out).
    Element Should Be Disabled    id=submit-btn

Submit Button Should Be Enabled
    [Documentation]    Verifies the submit button is enabled (clickable).
    Element Should Be Enabled    id=submit-btn
