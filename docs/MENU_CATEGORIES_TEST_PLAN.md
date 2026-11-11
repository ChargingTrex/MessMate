# Menu Categories & Upload Layouts — Test Plan

How to check that categorised menus and both CSV upload layouts work, by hand
and through the automated suites. Each test case below has an ID, and the
automated tests use the same IDs, so a failing run points back to a case here.

| | |
|---|---|
| Feature | Dishes stored as `Category: Dish` inside the existing Breakfast/Lunch/Dinner cells; the home page shows each category beside its dishes; the CSV template and importer use the mess's weekly grid layout |
| Code under test | `sheets.py` (`MENU_CATEGORIES`, `menu_entries`, `menu_groups`, `normalise_menu_text`, `save_menu_week`, `get_menu_groups_for_date`), `app.py` (`admin_menu_template_csv`, `admin_menu_import`, `_parse_menu_grid`, `_parse_menu_by_meal`, `_grid_date`, the `dishes` template filter), `templates/home.html`, `templates/admin_menu.html`, `static/home.js`, `static/style.css` |
| Automated suites | `test/test_menu_categories.py` (61 unit tests), `test/test_e2e_menu.py` (57 end-to-end steps), `tests/menu_categories_tests.robot` (TC200–TC210, browser) |

---

## 1. What is being tested

**Storage format.** A meal cell holds one entry per line. An entry is either
`Category: Dish` or a bare dish. Commas also separate entries, so older menus
and hand-typed cells keep working.

```
Main Item: Mix Veg Sevai
Spread: Butter
Spread: Jam
Beverage: Coffee
```

**Categories.** These come from the mess's own sheet, in its order. Snacks are
left out because the app has no Snacks meal.

| Meal | Categories |
|---|---|
| Breakfast | Main Item, Side Dish, Chutney, Vada / Banana, Egg, Bread, Spread, Spread, Beverage |
| Lunch | Bread, Side Dish, Rice, Sambar / Kulambu, Poriyal / Kootu, Rasam, Papad / Fryums, Curd, Pickle, Podi / Oil & Thogayal, Sweet / Fruits |
| Dinner | Rice, Dry Poriyal, Bread / Tiffin, Korma, Rasam, Curd, Pickle, Milk / Tea / Coffee |

**Upload layouts.**

| Layout | Header | One row per |
|---|---|---|
| Grid (the template) | `Meal, Category, <date>, <date>, …` | category of a meal |
| By meal (older) | `Date, Breakfast, Lunch, Dinner` | date |

The importer picks the grid layout when the header has both `Meal` and
`Category`. Otherwise it uses the by-meal layout.

**Rules every case relies on**

1. A category with nothing after it (`Egg:`) is dropped, never stored.
2. Dishes in a row under the same category show as one line
   (`Spread: Butter, Jam`).
3. Ratings, the committee form and the dashboards always see bare dish names.
4. In a grid, a blank Meal cell takes the meal from the row above.
5. In a grid, a date column with nothing in it is left alone. It never blanks
   a day that is already published.
6. Rows for any meal other than Breakfast, Lunch and Dinner are skipped, and
   the admin is told.
7. Grid date headers can be `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY` or
   `DD.MM.YYYY`.

---

## 2. Environment

| Need | How |
|---|---|
| Python venv | `source venv/bin/activate` |
| No Google credentials | The suites install `test/fake_sheets.py`, an in-memory stand-in for the sheet |
| Browser suite | Chrome, plus `robotframework-seleniumlibrary` (Selenium Manager fetches chromedriver) |
| Test server for the browser suite | `python test/fake_server.py 5001`, which seeds members and today's flat menu |
| Admin password (test server) | `admin-test-password` |
| Committee member (test server) | `robot-test-member@sai.edu` / `robot-test-password` |

---

## 3. Running the automated suites

```bash
source venv/bin/activate

# Unit — pure parsing and storage rules, < 1 s
python test/test_menu_categories.py

# End to end — real routes and templates against the in-memory sheet, ~3 s
python test/test_e2e_menu.py

# Browser — start a fresh test server, run the one suite, stop the server
python test/fake_server.py 5001 &
robot --variable BASE_URL:http://127.0.0.1:5001 tests/menu_categories_tests.robot
kill %1; pkill -f chromedriver

# Or by tag across all suites
bash tests/run_tests.sh categories
bash tests/run_tests.sh upload
```

Run Robot suites **one file at a time**, and close any other headless Chrome
first. With two at once, chromedriver hangs, and every test fails with
`ReadTimeoutError` in suite setup. That is the environment, not the app: run
`pkill -f chromedriver; pkill -f "Google Chrome.*--enable-automation"` and
run the suite again.

**Expected result:** all three report 0 failures. That is 61 unit tests,
57/57 end-to-end steps and 11/11 browser tests.

---

## 4. Manual test script

These steps are for a tester working through the feature by hand against the
test server (`http://127.0.0.1:5001`). Each step names the automated case that
covers the same thing. Run them in order, because later steps build on
earlier ones.

### Part A — The editor

| # | Action | Expected | Automated |
|---|---|---|---|
| A1 | Sign in as admin and open **Menu** | The editor says "One dish per line as `Category: Dish`" and the import card describes `Meal, Category` | TC200, E2E-M1.1, E2E-M4.9 |
| A2 | Look at an empty Monday Breakfast field | The placeholder shows the categorised template (`Main Item: Mix Veg Sevai` …) and the field is tall enough to show it | E2E-M1.2, E2E-M1.3 |
| A3 | In today's Breakfast type `Main Item: Pongal`, `Spread: Butter`, `Spread: Jam`, `Beverage: Coffee` on separate lines, then **Save** | A green "Menu saved" banner appears | TC201, E2E-M1.4 |
| A4 | Open **/home** | The Breakfast card is a two-column list with 3 lines: Main Item / Pongal, Spread / Butter, Jam, Beverage / Coffee | TC201, E2E-M2.1–M2.4 |
| A5 | Replace today's Breakfast with `Egg:` and `Bread:` only, then **Save** | The editor shows "Not published" for that meal, and /home shows "Menu not published yet" | TC202, E2E-M1.6 |
| A6 | Look at today's Lunch on /home (the test server seeds it as a comma list) | It is still pills, with no category column | TC203, E2E-M2.5 |
| A7 | Click **Fill blanks from template**, then **Save all 7 days** | Every empty field fills with the categorised Sai week and saves in one request | E2E-M1.7, E2E-M1.8 |

### Part B — The template download

| # | Action | Expected | Automated |
|---|---|---|---|
| B1 | Click **Download blank template** | You get `menu_template_<Monday>.csv` | E2E-M4.2 |
| B2 | Open it in a spreadsheet | Row 1 is `Meal, Category` and then the 7 dates. Row 2 has the weekday names. Then there are 28 category rows, Breakfast to Dinner, with no Snacks. All dish cells are empty | E2E-M4.3–M4.6 |
| B3 | Sign out, then open `/admin/menu/template.csv` | You are sent to sign in | E2E-M4.1 |

### Part C — Uploading the grid

| # | Action | Expected | Automated |
|---|---|---|---|
| C1 | Fill B2's file with a real week (copy from the mess's printed sheet). Leave Meal blank under the first row of each meal, like a merged cell. Upload it | "Imported 7 days." The editor shows the uploaded week with all 7 days marked saved | E2E-M5.1–M5.3 |
| C2 | Upload the same file again | Same message, and the sheet still has one row per date | E2E-M5.4 |
| C3 | Change the date headers to `DD-MM-YYYY` and upload | It imports the same | TC204, E2E-M5.5 |
| C4 | Add a Snacks block (`Snacks, Tea, …` and `, Snack 1 ( Fried ), Aloo Samosa, …`) and upload | The banner says "Skipped Snacks — only Breakfast, Lunch, Dinner are published." No snack appears anywhere | TC204, E2E-M5.8 |
| C5 | Put `Mint Pulao, Steamed Rice` in one Dinner › Rice cell | Home shows `Rice   Mint Pulao, Steamed Rice` | E2E-M5.7 |
| C6 | Publish a day, then upload a grid whose column for that day is empty | That day is unchanged, and the banner says "Left 1 empty day unchanged." | E2E-M5.9 |
| C7 | Add a `Notes` column with text in it | Ignored | TC204, E2E-M5.10 |
| C8 | On /home, click tomorrow's tab after uploading tomorrow with categories | The card redraws with the category column, without a page reload | TC205 |
| C9 | Save the CSV from Excel (adds a byte-order mark) and upload | It imports | E2E-M5.12 |

### Part D — The older layout

| # | Action | Expected | Automated |
|---|---|---|---|
| D1 | Upload `Date,Breakfast,Lunch,Dinner` with `"Idli, Sambar"` for one day | "Imported 1 day." Home shows Idli and Sambar as pills | TC206, E2E-M6.1, E2E-M6.2, E2E-M6.5 |
| D2 | Put `Main Item: Idly` in a cell of the older layout | It is stored and shown with its category | E2E-M6.3 |
| D3 | Include a row dated `next week` | "Skipped line N (bad date)." The other rows still import | E2E-M6.4 |

### Part E — Refusals (nothing may change in the sheet)

| # | Upload | Expected message | Automated |
|---|---|---|---|
| E1 | No file chosen (the browser blocks this; send it without a file) | Choose a CSV file to import. | E2E-M7.1 |
| E2 | A file over 1 MB | That file is too large (max 1 MB). | E2E-M7.2 |
| E3 | A file that is not UTF-8 | Could not read that file — save it as UTF-8 CSV. | E2E-M7.3 |
| E4 | A grid whose headers are weekdays, not dates | No date columns found. … | TC207, E2E-M7.4 |
| E5 | Header `Day,Food` | CSV needs a header row with columns Meal, Category … | TC208, E2E-M7.5 |
| E6 | A grid with every dish cell blank | No valid rows found in that CSV. | E2E-M7.6 |
| E7 | A grid of only Snacks rows | No valid rows found … Skipped Snacks … | E2E-M7.7 |
| E8 | An empty file | CSV needs a header row … | E2E-M7.8 |
| E9 | Any upload without the CSRF token | HTTP 403 | E2E-M7.9 |
| E10 | Any upload while signed out | Sent to sign in | E2E-M7.10 |

### Part F — Everywhere else a menu appears

| # | Action | Expected | Automated |
|---|---|---|---|
| F1 | Sign in as a committee member and open today's Breakfast | Each dish is rated by its bare name (Pongal, not "Main Item: Pongal") | TC210, E2E-M3.2 |
| F2 | Open the admin **Overview** | The meal chips are dish names, not raw cells | E2E-M3.3 |
| F3 | Open the student dashboard (`/dashboard?token=vc2026`) | The menu chips are dish names | E2E-M3.4 |
| F4 | Put `<b>Main</b>: <img src=x onerror=alert(1)>` in the sheet | Home shows the text escaped, and no alert fires | E2E-M2.9 |
| F5 | Open /home on a phone (390 px) | The category list fits, with no sideways scroll | TC209 |
| F6 | Watch the "Serving now" box during a meal with 10+ dishes | It shows the first 6 dishes and then "+N more" | manual only (it depends on the clock) |
| F7 | Watch the scrolling news strip | It lists dish names without category labels | manual only |

### Part G — Live checks (real sheet, do once per release)

| # | Action | Expected |
|---|---|---|
| G1 | Open the Google Sheet's `menu` tab after an upload | Each meal cell holds one `Category: Dish` per line. Columns are still Date, Breakfast, Lunch, Dinner |
| G2 | Edit a cell directly in the sheet (add `Pickle: Lime Pickle`), wait out the cache or save any menu in the editor | Home shows the new line |
| G3 | Open the template in Excel on an Indian-locale machine, fill it and save it as CSV | The re-saved dates (`09-11-2026`) import correctly |

---

## 5. Test case catalogue

### 5.1 Unit — `test/test_menu_categories.py`

| ID | Covers |
|---|---|
| UT-PARSE-01…11 | `Category: Dish` and bare dishes; comma and newline separators; trimming; a category with no dish dropped; empty and `None` input; only the first colon splits; a prefix over 40 characters is not a category; `/` and `&` survive; `_split_items` drops categories and keeps its old behaviour |
| UT-GROUP-01…06 | Same category in a row merges into one line; same category apart stays apart; a bare dish is a group of its own and breaks a run; order is kept; empty input |
| UT-NORM-01…05 | Stored form is one entry per line; blank template rows dropped; only blank rows becomes `""`; normalising twice changes nothing; `_menu_text` skips empty dishes |
| UT-CAT-01…05 | Category lists exist for exactly Breakfast, Lunch and Dinner (no Snacks); the mess's names in its order; sheet typos fixed (`kottu`, `&n`, `Spread 1/2`); only Spread repeats; every name parses as a category |
| UT-WEEK-01…06 | The Sai week: 7 days × 3 meals; every dish has a category, in list order; spot checks against the printed sheet; its blank cells are left out; no snacks; `menu_template_for_date` picks by weekday |
| UT-STORE-01…04 | `save_menu_week` normalises; groups and dish names read back by date; a meal of only blank rows reads as unpublished |
| UT-DATE-01…02 | The four accepted date formats, single-digit days included; weekdays, impossible dates and 2-digit years rejected |
| UT-GRID-01…15 | Basic grid; weekday row skipped; Meal carried down; Snacks skipped with a note; meal names in any case; header in any case and order; a comma cell gives several dishes; a blank category gives a bare dish; an empty date column is left alone; a blank meal on a filled day stays blank; non-date columns ignored; no date columns is an error; ragged rows; an all-blank file; the whole Sai week round-trips through the grid unchanged |
| UT-MEAL-01…07 | The older layout: basic; header in any case and order; categories in cells; bad dates reported by line number; the last row for a date wins; blank lines skipped; missing columns is an error |

### 5.2 End to end — `test/test_e2e_menu.py`

| Journey | Steps | Covers |
|---|---|---|
| M1 Editor | E2E-M1.1–M1.8 | Hint, placeholder, field height; saving one day and the whole week; blank rows dropped; upsert, not duplicate |
| M2 Home | E2E-M2.1–M2.9 | Two-column list; category beside dish; Spread merged; order; flat menus keep pills; unpublished message; the day-switcher data; `?date=`; escaping |
| M3 Other surfaces | E2E-M3.1–M3.4 | Rating lookup, committee form, admin overview and student dashboard all get bare dish names |
| M4 Template | E2E-M4.1–M4.9 | Admin only; file name and type; header; weekday row; category rows; blank cells; mid-week and invalid `?start`; editor copy |
| M5 Grid upload | E2E-M5.1–M5.12 | Download-fill-upload round trip; editor after import; re-upload upserts; day-first dates; Meal carried down; comma cells; Snacks; empty day left alone; Notes ignored; reaches students; Excel byte-order mark |
| M6 Older layout | E2E-M6.1–M6.5 | Imports; comma lists stored per line; categories kept; bad dates reported; flat display |
| M7 Refusals | E2E-M7.1–M7.10 | Every refusal in Part E, each checked to leave the sheet untouched |

### 5.3 Browser — `tests/menu_categories_tests.robot`

| ID | Title | Tags |
|---|---|---|
| TC200 | Editor Explains The Category Format | smoke, menu, categories |
| TC201 | A Categorised Menu Shows Each Category Beside Its Dishes | critical, menu, categories, home |
| TC202 | Template Rows Left Blank Are Not Published | menu, categories |
| TC203 | A Menu Without Categories Keeps Its Chips | menu, categories, regression |
| TC204 | A Grid Upload Publishes Categories And Skips Snacks | critical, menu, upload |
| TC205 | The Day Switcher Renders Uploaded Categories | menu, upload, home |
| TC206 | The Older Layout Still Uploads | menu, upload, regression |
| TC207 | A Grid Without Dates Is Refused | menu, upload, validation |
| TC208 | A File In Neither Layout Is Refused | menu, upload, validation |
| TC209 | A Categorised Card Fits A Phone Screen | menu, categories, responsive |
| TC210 | The Committee Form Rates Bare Dish Names | menu, categories, committee |

---

## 6. Known limits (tested as they are, not defects)

- **US-style dates are not read.** `11/09/2026` is read day-first, as
  11 September. A US-locale Excel that re-saves the template as `M/D/YYYY`
  imports to the wrong days. If that machine is ever used, keep the headers
  as text.
- **Category labels are not checked against the list.** Any `Label: Dish` is
  accepted and shown, so a typo makes a new category. That is deliberate,
  because the mess renames rows from time to time.
- **A dish containing a colon** (`Ratio 1:2`) is read as category `Ratio 1`.
  Write it without the colon, or as `Category: Ratio 1:2` (only the first
  colon splits).
- **"Serving now" and the news strip** depend on the clock, so they are only
  checked by hand (F6, F7).
