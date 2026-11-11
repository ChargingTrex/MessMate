# MessMate — Test Plan

How to test all of MessMate: what each part of the site must do, how to check
it by hand, and which automated test already checks it. Every manual step
names its automated tests by ID, so a failing run points back to a step here
and a step here points to the code that guards it.

| | |
|---|---|
| Site | Flask app backed by a Google Sheet (`app.py`, `sheets.py`, `auth.py`, `device.py`, `pilot.py`, `ui_config.py`) |
| Automated | 9 Robot browser/HTTP suites (192 cases, TC01–TC210), 8 Python suites against an in-memory sheet (one of them unit tests) |
| Manual only | Section 6 lists what no suite covers |
| Last full run | 2026-11-11: every Python suite green (smoke 46/46); Robot `home_tests` and `menu_categories_tests` green |

---

## 1. The site at a glance

### 1.1 Who uses it

| Role | Signs in with | Can |
|---|---|---|
| **Student** | Nothing — anonymous | See the menu, tap Good / Bad / Skip per meal, fill the per-dish form, suggest dishes |
| **Committee member** | Email + password at `/signin` or `/committee/login` | Review each meal (every dish + five areas), see the committee dashboard |
| **Admin** | `admin@messmate.demo` at `/signin`, or `/admin/login` | Everything: overview, menu editor and uploads, member roster, both dashboards |
| **Dean (viewer)** | `dean@messmate.demo` at `/signin` | Both dashboards, read-only |
| **Token holder** | `?token=` on a dashboard link | Both dashboards, read-only. Never anything that changes state |

### 1.2 Pages and endpoints

| Area | Route | Who | What it does |
|---|---|---|---|
| Student | `GET /home` | anyone | Today's menu by meal, day switcher, quick taps, tallies (admins) |
| | `POST /home/rate`, `POST /home/undo` | anyone | One tap per meal per device per day, after the meal opens; Undo within 10 min |
| | `GET /`, `POST /submit`, `GET /thanks` | anyone | The per-dish form behind the printed QR code; 1 per device per 4 hours |
| Sign-in | `GET/POST /signin`, `POST /signout` | anyone | One front door; the email decides the role; pilot cards in pilot mode |
| | `/admin/login`, `/admin/logout`, `/committee/login`, `/committee/logout` | — | The older per-role doors, still working |
| Committee | `/committee/password` | member | Forced on first sign-in and after a reset |
| | `GET /committee`, `POST /committee/submit`, `GET /committee/thanks` | member | Review a meal: every dish on its menu + Taste, Quality, Variety, Hygiene, Menu |
| | `GET /committee/dashboard` | member | The committee's numbers, the member's own record, today's student context |
| Admin | `GET /admin` | admin | Overview: today's numbers, the week's menu gaps, alerts |
| | `/admin/menu`, `/admin/menu/save`, `/save-week`, `/template.csv`, `/import` | admin | Menu editor, categories, CSV template and uploads |
| | `/admin/members`, `/add`, `/bulk`, `/update` | admin | Roster: add, bulk add, deactivate, reactivate, reset password |
| Dashboards | `GET /dashboard` | admin, dean, token | Student feedback: stat cards, 7/30-day trend, per-dish chart, suggestions |
| | `GET /dashboard/committee` | admin, dean, token | Committee: stat cards, five-area chart, trend, attributed review feed |
| Plumbing | `GET /health`, `GET /ui/tokens.css`, `/static/*` | anyone | Uptime check, design tokens (both themes), assets |

### 1.3 Rules the whole plan relies on

| # | Rule | Where |
|---|---|---|
| R1 | Students are never identified. Student feedback and committee reviews never mix | `sheets.py`, both dashboards |
| R2 | Anything that changes data needs an admin **session** and a CSRF token; `?token=` is read-only | `auth.admin_required`, `csrf.py` |
| R3 | Per-dish form: 1 per device per 4 h. Quick taps: 3 per device per day, one per meal, today only, from the meal's opening time (7:30, 12:00, 19:30); Undo for 10 min | `app.py` limiter, `device.py`, `sheets.MEAL_OPENS` |
| R4 | Committee: one review per member per meal per day; every dish and all five areas rated | `/committee/submit` |
| R5 | Sign-in failures say the same thing whatever was wrong; generated passwords are shown once | `/signin`, roster |
| R6 | Anything typed into the sheet or a form is escaped on every page | templates, `home.js` |
| R7 | A Google Sheets outage degrades a page, never 500s it | every route, `sheets.py` |
| R8 | Reads come from a cache refreshed every 30 min and 10 min before each meal; the app's own writes show at once | `sheets.py` read cache |
| R9 | An unpublished meal says "Menu not published yet" — never a template guess | `/home` |
| R10 | Menus are `Category: Dish` lines; ratings use bare dish names (detail in 5.C) | `sheets.menu_entries` |

---

## 2. Environment and test data

| Need | How |
|---|---|
| Python venv | `source venv/bin/activate` |
| No Google credentials | The suites install `test/fake_sheets.py`, an in-memory stand-in for the sheet. Only the network is faked; `sheets.py` runs for real |
| Browser suites | Chrome + `robotframework-seleniumlibrary` (Selenium Manager fetches chromedriver) |
| Test server | `python test/fake_server.py 5001` — the real app on the fake sheet, plus a test-only `POST /__test__/reset` |
| Live app | `venv/bin/python app.py` (port 5000, the real sheet, `.env`) |

**Seeded by the test server** (`test/fake_server.py`, restored by every suite's setup):

| Data | Value |
|---|---|
| Admin password | `admin-test-password` |
| Members | `robot-test-member@sai.edu` / `robot-test-password` (active) · `robot-test-newbie@sai.edu` (must change password) · `robot-test-retired@sai.edu` (deactivated) · `robot-test-rated@sai.edu` (already reviewed all of today's meals) |
| Dashboard token | `vc2026` |
| Menu | Today all three meals (flat comma lists); tomorrow without dinner; the day after complete |
| Feedback | Six days of committee history, today's quick taps, three days of student responses |

**Pilot / demo** (live app with `PILOT_MODE=true`, data from `seed_demo.py`): the
sign-in page shows one card per role (student, five members, dean). Cards fill
the email only; passwords are handed out separately (`DEMO_LOGINS.md`).

---

## 3. Running the automated suites

### 3.1 Credential-free Python suites (no browser, no server)

```bash
source venv/bin/activate
python test/test_smoke.py            # is each feature switched on at all? ~1 s
python test/test_menu_categories.py  # unit: menu parsing and both CSV layouts
python test/test_cache.py            # the read cache
python test/test_committee.py        # one check per committee checklist item
python test/test_e2e_student.py      # S1–S9  student journeys
python test/test_e2e_home.py         # H1–H8  menu page and quick taps
python test/test_e2e_menu.py         # M1–M7  menu categories and uploads
python test/test_e2e_committee.py    # J1–J10 committee journeys
```

Each prints a PASS/FAIL line per step and exits non-zero on any failure.

### 3.2 Robot suites (browser and HTTP)

```bash
python test/fake_server.py 5001 &
robot --variable BASE_URL:http://127.0.0.1:5001 --outputdir tests/results tests/home_tests.robot
kill %1; pkill -f chromedriver
```

Run **one suite file per invocation, with a fresh test server each time.** Two
headless Chromes at once make chromedriver hang, and every test then fails in
suite setup with `ReadTimeoutError`. That is the machine, not the app: run
`pkill -f chromedriver; pkill -f "Google Chrome.*--enable-automation"` and run
the suite again.

`bash tests/run_tests.sh <tag>` runs every suite with a tag (`smoke`,
`critical`, `security`, `menu`, `upload`, `categories`, …) in one go — fine
on CI, slower to diagnose locally.

### 3.3 Against a live deployment

```bash
python test/test_smoke.py --url https://<app>.onrender.com --token <DASHBOARD_TOKEN>
```

Live mode only reads; write checks are skipped and say so.

### 3.4 Before a demo or a deploy

1. `test_smoke.py` locally — every feature switched on.
2. All Python suites in 3.1 — about 15 s together.
3. The Robot suites for the areas the change touched (section 4 maps areas to suites).
4. After deploy: `test_smoke.py --url …` against the live app, then manual
   section 5.K (live checks).

---

## 4. Coverage map

### 4.1 Area → automated suites

| Area | Unit | Python end to end | Robot |
|---|---|---|---|
| A. Per-dish student form | — | S1–S4, S9 | `form_tests` TC01–TC23, `api_tests` TC41–TC47 |
| B. Menu page & quick taps | — | H1–H8 | `home_tests` TC180–TC191, TC198–TC199 |
| C. Menu editor, categories, uploads | UT-* (61) | H4–H5, M1–M7 | `home_tests` TC192–TC197, `menu_categories_tests` TC200–TC210 |
| D. Sign-in & roles | — | smoke "sign in", J5 | `committee_form_tests` TC60–TC71, `committee_admin_tests` TC90–TC95, `committee_api_tests` TC150–TC163 |
| E. Committee reviews | — | J1–J4, J6, J10, checklist phase 3/3b | `committee_form_tests` TC72–TC85, `committee_api_tests` TC165–TC169, TC210 |
| F. Admin overview & roster | — | J1, J3–J6, checklist phase 2 | `committee_admin_tests` TC96–TC118 |
| G. Dashboards | — | S5–S8, J8, J10, checklist phase 4 | `dashboard_tests` TC24–TC38, `api_tests` TC48–TC52, `committee_dashboard_tests` TC120–TC146 |
| H. Security & privacy | — | S9, J5, J7, H3, H6, M7 | TC21, TC45, TC117, TC150–TC164, TC193 |
| I. Resilience & cache | `test_cache` | S8, J9, H7 | — |
| J. Look & feel, accessibility | — | — | TC209 (phone width) — rest manual |
| K. Operations | — | smoke | `api_tests` TC39–TC40, TC53–TC54, TC170–TC172 |

### 4.2 Rule → tests

| Rule | Guarded by |
|---|---|
| R1 anonymity & separation | S9, J7, H6, TC144, TC145 |
| R2 session + CSRF, token read-only | J5, TC94, TC154–TC164, TC193, E2E-M7.9–M7.10 |
| R3 limits and windows | S4, H3, H8, TC47 |
| R4 one review per meal, all rated | TC73, TC82, TC167–TC169, J2 |
| R5 uniform failures, one-time passwords | TC65, TC103, smoke "sign in" |
| R6 escaping | TC21, TC38, TC45, TC117, E2E-M2.9 |
| R7 outage | S8, J9, H7 |
| R8 cache | `test_cache` (16 checks), H5 |
| R9 honest empty state | TC197, H5, E2E-M2.6 |
| R10 categories | UT-PARSE/GROUP/NORM, M2, M3, TC201–TC203, TC210 |

### 4.3 Known suite caveats

- `test_smoke.py` signs the dean in with `VIEWER_PASSWORD`. It sets its own
  value (commit `e79e0ca`); before that, a local `.env` with a different
  `VIEWER_PASSWORD` made the dean check fail.
- Tests that depend on the clock (serving windows, the "Serving now"
  spotlight) switch `ENFORCE_MEAL_WINDOWS` off, except H8, which pins the time.

---

## 5. Manual test script

For a tester working through the site by hand against the test server
(`http://127.0.0.1:5001`, section 2). Steps within a part build on each
other; parts are independent once the server is reset
(`curl -X POST http://127.0.0.1:5001/__test__/reset`).

Each step: what to do, what must happen, which automated tests cover it.
"manual" means nothing automated does.

### Part A — The per-dish student form (`/`)

| # | Action | Expected | Automated |
|---|---|---|---|
| A1 | Open `/` | The form loads; Submit is disabled | TC01, TC02 |
| A2 | Pick an overall emoji, then another | Only the last is selected; Submit enables; the hidden value matches | TC04–TC07 |
| A3 | Rice dropdown: Curry, Rasam, Both, back to none | Only the chosen rice rows show; resetting clears their ratings | TC08–TC13 |
| A4 | Type in the review | The counter tracks it and stops at 150 | TC14–TC17 |
| A5 | Submit with only the overall rating | Thank-you page, with a link back | TC18, TC20, S1, S2 |
| A6 | Submit again from the same browser | Refused: one review per device per 4 hours | TC47, S4 |
| A7 | Submit `<script>alert(1)</script>` as the review | Saved as text; nothing runs anywhere it is shown | TC21, TC45, TC38 |
| A8 | POST `/submit` without an overall score, or with 9, or with "abc" | Error banner, nothing saved | TC22, TC23, TC42–TC44, S3 |

### Part B — The menu page and quick taps (`/home`)

| # | Action | Expected | Automated |
|---|---|---|---|
| B1 | Open `/home` signed out | Three meal cards with serving times, no login asked | TC180–TC183 |
| B2 | Tap Good on Lunch (after 12:00) | The card shows it was counted, with Undo | TC184, TC185, H1 |
| B3 | Tap Undo within 10 minutes | The tap is withdrawn and can be made again | H8 |
| B4 | Tap a meal that has not opened yet | No buttons; the card says when it opens | H8 |
| B5 | Tap all three meals, then try a fourth tap | The in-page limit banner appears (3 per device per day) | H3 |
| B6 | Open "Add a suggestion", send one with a tap | The field appears only on request; the suggestion is saved | TC188–TC190 |
| B7 | Sign in as admin and open `/home` | Each card shows its tally and score | TC187, H2 |
| B8 | Switch days with the day tabs | Cards redraw without a reload; other days have no buttons | H1, TC205 |
| B9 | Watch "Serving now" and the news strip | The current meal's first 6 dishes + "+N more"; the strip pauses on tap | manual |
| B10 | Check quick taps never appear on the per-dish dashboard or committee scores | They don't | H6 |

### Part C — Menu editor, categories and uploads (`/admin/menu`)

Menus are stored as one entry per line in each meal's cell, `Category: Dish`
or a bare dish. Categories follow the mess's sheet; Snacks are not served.

| Meal | Categories |
|---|---|
| Breakfast | Main Item, Side Dish, Chutney, Vada / Banana, Egg, Bread, Spread, Spread, Beverage |
| Lunch | Bread, Side Dish, Rice, Sambar / Kulambu, Poriyal / Kootu, Rasam, Papad / Fryums, Curd, Pickle, Podi / Oil & Thogayal, Sweet / Fruits |
| Dinner | Rice, Dry Poriyal, Bread / Tiffin, Korma, Rasam, Curd, Pickle, Milk / Tea / Coffee |

| # | Action | Expected | Automated |
|---|---|---|---|
| C1 | Open `/admin/menu` signed out, then with `?token=vc2026` | Sent to sign in both times | TC192, TC193 |
| C2 | Sign in as admin, open Menu | This week, today marked; the hint explains `Category: Dish`; empty fields show the categorised template | TC194, TC195, TC200, E2E-M1.1–M1.3 |
| C3 | Type `Main Item: Pongal` / `Spread: Butter` / `Spread: Jam` / `Beverage: Coffee` in today's Breakfast, Save | `/home` shows three lines: Main Item › Pongal, Spread › Butter, Jam, Beverage › Coffee | TC196, TC201, E2E-M1.4, M2.1–M2.4 |
| C4 | Replace it with `Egg:` and `Bread:` only, Save | "Not published" in the editor; "Menu not published yet" on `/home` | TC197, TC202, E2E-M1.6 |
| C5 | Look at a meal typed as a comma list | Still shown as pills | TC203, E2E-M2.5 |
| C6 | Fill blanks from template, Save all 7 days | The whole week saves in one request, no duplicate rows | H4, E2E-M1.7, M1.8 |
| C7 | Download blank template | `menu_template_<Monday>.csv`: `Meal, Category`, 7 dates, a weekday row, 28 category rows, no Snacks | E2E-M4.1–M4.8 |
| C8 | Fill it like the mess's sheet (Meal only on each meal's first row, `DD-MM-YYYY` dates, a Snacks block, a Notes column) and upload | "Imported N days." and "Skipped Snacks …"; snacks and notes appear nowhere | TC204, E2E-M5.1, M5.5–M5.10 |
| C9 | Upload it again | Same result, still one row per date | E2E-M5.4 |
| C10 | Upload a grid with one date column left empty, for a day already published | That day is unchanged; "Left 1 empty day unchanged." | E2E-M5.9 |
| C11 | Put `Mint Pulao, Steamed Rice` in one cell | Two dishes on one Rice line | E2E-M5.7 |
| C12 | Upload the older `Date, Breakfast, Lunch, Dinner` layout, with one bad date | Imports; the bad line is reported by number | TC206, E2E-M6.1–M6.5 |
| C13 | Upload: no file · over 1 MB · not UTF-8 · weekday headers · `Day,Food` · all blank · only Snacks · empty file | Refused with a reason each time; the sheet unchanged | TC207, TC208, E2E-M7.1–M7.8 |
| C14 | Upload without the CSRF token, or signed out | 403 / sent to sign in; nothing written | E2E-M7.9, M7.10 |
| C15 | Edit a cell directly in the Google Sheet | `/home` shows it after the next refresh, or at once after any editor save | H5 |

### Part D — Sign-in and roles

| # | Action | Expected | Automated |
|---|---|---|---|
| D1 | Open `/signin` (pilot mode on) | The form, plus one card per role; cards carry no password | smoke "sign in" |
| D2 | Sign in as `admin@messmate.demo` with `?next=/admin/menu` | Lands on the menu editor | smoke "sign in" |
| D3 | `?next=https://evil.example` or `//evil.example` | Ignored; lands on the role's default page | manual |
| D4 | Wrong password · unknown email · deactivated member | The same "Incorrect email or password." each time | TC64–TC66, smoke |
| D5 | Sign in as the dean | Both dashboards open; the roster and menu editor do not | smoke "sign in" |
| D6 | Sign in as `robot-test-newbie@sai.edu` | Sent to change the password; nothing else opens until it is changed; mismatched confirmation refused | TC68–TC71 |
| D7 | Every header: signed out shows Sign in; signed in shows Sign out; Sign out ends the session | As described, for each role | TC85, TC95, manual for the header itself |
| D8 | Older doors `/admin/login` and `/committee/login` | Still work; `/committee/login` says reviews are attributed and links to the anonymous form | TC60–TC63, TC90–TC92 |
| D9 | 21 sign-in attempts in an hour from one address | Rate-limited | manual |

### Part E — Committee reviews

| # | Action | Expected | Automated |
|---|---|---|---|
| E1 | Sign in as `robot-test-member@sai.edu` at `/committee/login` (at `/signin` a member lands on their dashboard instead) | The rating page for the next unreviewed meal; the meal toggle marks unreviewed meals yellow | TC63, TC74a, TC74b |
| E2 | Switch meals on the toggle | Each meal lists that meal's dishes from the menu (bare names, no categories) | TC74a, TC210, E2E-M3.2 |
| E3 | Rate some dishes and areas | Submit stays disabled until every dish and all five areas are rated; the progress hint counts | TC72–TC77 |
| E4 | Write a review | Counter; max 500; optional | TC78, TC79, TC81 |
| E5 | Submit | Thank-you page; the review appears on the committee dashboard with the member's name | TC80, TC166, J1 |
| E6 | Try the same meal again (or as `robot-test-rated`) | Refused / the already-reviewed notice | TC82, TC83, TC167 |
| E7 | Double-click Submit | One review saved | TC84 |
| E8 | Open `/committee/dashboard` | Committee numbers, the member's own record, and today's student context in its own card | J10, smoke "member dashboard" |
| E9 | Have the admin deactivate the member mid-session | The next request signs them out | J6 |

### Part F — Admin overview and roster

| # | Action | Expected | Automated |
|---|---|---|---|
| F1 | Open `/admin` | Today's numbers, this week's menu state with gaps (tomorrow's dinner is missing in the seed), pending passwords | smoke "admin overview", E2E-M3.3 |
| F2 | Open Members | Seeded members, active/inactive badges, "must change password" flag, reviews this month, active count | TC96–TC100 |
| F3 | Add a member | A one-time password is shown once; it works; reloading hides it | TC101–TC103, J1 |
| F4 | Add a duplicate, a retired member, a malformed email | Each refused with a reason | TC104–TC106 |
| F5 | Bulk add with some bad lines | Every valid row added with its own password; bad lines reported one by one | TC107–TC109 |
| F6 | Deactivate, then reactivate a member | They lose and regain access; they stay on the roster | TC110–TC113, J3 |
| F7 | Reset a password | A new one is shown; the old one stops working; the member must change it | TC114–TC116, J4 |
| F8 | Add a member named `<img src=x onerror=alert(1)>` | Shown as text | TC117 |
| F9 | From the roster, open both dashboards | Both open | TC118 |

### Part G — Dashboards

| # | Action | Expected | Automated |
|---|---|---|---|
| G1 | `/dashboard` and `/dashboard/committee` with no credential, a wrong token, the right token, an admin session | 403, 403, open, open | TC24–TC26, TC48–TC50, TC120–TC123 |
| G2 | Student dashboard | Stat cards (today, average with colour band, count); trend chart 7 days by default, 30 on toggle; per-dish chart; suggestions, escaped, with a friendly empty state | TC27–TC38, S5, S7 |
| G3 | Committee dashboard | Four stat cards (score, responses, active members excluding retired, participation %); five-area chart; trend with per-area lines hidden at first; 7/30 toggle; attributed review feed newest first | TC126–TC142, J2, J8 |
| G4 | Admin vs token holder on the committee dashboard | Admin sees Manage members; the token holder does not | TC124, TC125 |
| G5 | Compare the two dashboards | No committee review on the student one, no student feedback on the committee one; they link to each other | TC143–TC146, J7 |
| G6 | Many students rate in one service | Averages and counts add up; the daily summary updates its row rather than adding one | S5, S6 |

### Part H — Security and privacy (cross-cutting)

| # | Check | Expected | Automated |
|---|---|---|---|
| H1 | A dashboard token used against admin actions (roster, add, bulk add, reset, menu editor) | Refused; nothing created | TC94, TC156–TC160, TC193, J5 |
| H2 | Every form without its CSRF token, or with a forged one | Refused | TC161–TC164, E2E-M7.9, smoke "csrf" |
| H3 | Student records | A student row carries no identity; the form and menu never ask for a login or redirect to a committee page; the device cookie is signed and stays in the browser | S9, J7 |
| H4 | Text from the sheet or forms (menu cells, member names, reviews, suggestions) | Escaped everywhere, including what `home.js` builds | TC21, TC38, TC45, TC117, E2E-M2.9 |
| H5 | Redirect targets (`next`) | Local paths only | manual (D3) |
| H6 | Passwords | Never in the page source, never on the pilot cards, shown once on creation or reset | smoke, TC103 |

### Part I — Resilience

| # | Action | Expected | Automated |
|---|---|---|---|
| I1 | Make the sheet unreachable (wrong `SPREADSHEET_ID`, or no network) and open each page | Pages render with empty states; no 500s; the per-dish form still loads | S8, J9, H7 |
| I2 | Read cache | Repeat reads cost no API calls; refreshes at :00/:30 and 10 min before each meal; the app's own writes show at once | `test_cache` |
| I3 | Tap a meal, restart the server, open `/home` again | That meal still shows as rated: the record is in the device's signed cookie, not the server's memory | manual |

### Part J — Look and feel, accessibility

| # | Check | Expected | Automated |
|---|---|---|---|
| J1 | Theme switch in the header | Light and dark both apply to every page; the choice survives a reload; no flash of the wrong theme | manual |
| J2 | Every page at 390 px wide | No sideways scroll; the menu category list fits | TC209 (home), manual for the rest |
| J3 | Keyboard only | Every control reachable, visible focus ring, emoji ratings operable with keys | manual |
| J4 | Contrast | Text meets WCAG AA in both themes (see `accessibility-audit.md`) | manual |
| J5 | Moving content | The news strip can be paused by touch and keyboard | manual |
| J6 | Reduced motion set in the OS | Animations stop or shorten | manual |

### Part K — Operations and live checks (once per release)

| # | Action | Expected | Automated |
|---|---|---|---|
| K1 | `GET /health` | `200 {"status": "ok"}` | TC39, TC40, TC170 |
| K2 | `/static/style.css`, `/static/dashboard.js`, `/ui/tokens.css` | Served | TC53, TC54, smoke "static assets" |
| K3 | `test_smoke.py --url <live> --token <token>` | All read checks pass | smoke |
| K4 | Open the live Google Sheet after a menu save | Columns Date, Breakfast, Lunch, Dinner; one `Category: Dish` per line | manual |
| K5 | Re-save the menu template in Excel on an Indian-locale machine and upload | `DD-MM-YYYY` dates import correctly | manual |
| K6 | `python generate_qr.py <live-url>` and scan the PNG | Opens the per-dish form on a phone | manual |
| K7 | Pilot mode off (`PILOT_MODE` unset) | `/signin` shows no cards | manual |

---

## 6. Not automated

| Gap | Why | Covered by |
|---|---|---|
| Theme switch, keyboard use, contrast, reduced motion | Visual and assistive-tech checks | J1, J3–J6 |
| "Serving now" spotlight and the news strip | Depend on the clock | B9 |
| Open-redirect check on `next` | No test yet — worth adding to `test_smoke.py` | D3, H5 |
| Sign-in rate limits | The suites switch the limiter off | D9 |
| Header sign-in / sign-out control on every page | Covered per role, not per page | D7 |
| Real Excel round trips, real Google outages, QR posters | Need real tools and devices | K4–K6, I1 |
| Phone width on pages other than `/home` | Only the menu card has a test | J2 |

---

## 7. Known limits (tested as they are, not defects)

- **US-style dates are not read in menu uploads.** `11/09/2026` is read
  day-first (11 September). Keep date headers as text on a US-locale Excel.
- **Menu category labels are not checked against the list.** Any `Label: Dish`
  is shown, so a typo makes a new category — deliberate, as the mess renames
  rows.
- **A dish containing a colon** (`Ratio 1:2`) is read as category `Ratio 1`.
  Write it as `Category: Ratio 1:2`; only the first colon splits.
- **Quick taps stay open after a meal's window ends** — someone who ate late
  still ate.

---

## 8. Test case catalogue

### 8.1 Unit — `test/test_menu_categories.py` (61 tests)

| IDs | Covers |
|---|---|
| UT-PARSE-01…11 | `Category: Dish` and bare dishes; comma and newline separators; trimming; a category with no dish dropped; empty and `None`; only the first colon splits; a prefix over 40 characters is not a category; `/` and `&` survive; `_split_items` drops categories and keeps its old behaviour |
| UT-GROUP-01…06 | Same category in a row merges; apart stays apart; a bare dish is its own group and breaks a run; order kept; empty input |
| UT-NORM-01…05 | One entry per line; blank template rows dropped; only blank rows becomes `""`; idempotent; `_menu_text` skips empty dishes |
| UT-CAT-01…05 | Lists for exactly Breakfast, Lunch, Dinner; the mess's names in order; sheet typos fixed; only Spread repeats; every name parses |
| UT-WEEK-01…06 | The Sai week: 7 × 3; every dish categorised, in list order; spot checks; blank cells left out; no snacks; template picked by weekday |
| UT-STORE-01…04 | Save normalises; groups and dish names read back; blank rows read as unpublished |
| UT-DATE-01…02 | Four accepted date formats; weekdays, impossible dates, 2-digit years rejected |
| UT-GRID-01…15 | The grid layout, rule by rule, and a full-week round trip |
| UT-MEAL-01…07 | The older layout: order and case, categories in cells, bad dates by line, last row wins, blank lines, missing columns |

### 8.2 Python end-to-end journeys

| Suite | Journeys |
|---|---|
| `test_e2e_student.py` | S1 rate lunch → thank-you · S2 partial ratings · S3 overall score required · S4 one review per device per 4 h · S5 a full service adds up · S6 daily summary upserts · S7 a week builds the trend · S8 dashboard gated and outage-proof · S9 anonymity |
| `test_e2e_home.py` | H1 open the menu and tap once · H2 tallies · H3 bad input and three taps a day · H4 admin publishes the week · H5 unpublished menus and sheet edits · H6 quick taps never mix with other scores · H7 Sheets outage · H8 one tap per meal, today, after opening, with Undo |
| `test_e2e_menu.py` | M1 editor · M2 home shows categories · M3 bare dish names elsewhere · M4 CSV template · M5 grid upload · M6 older layout · M7 refused uploads (E2E-M1.1 … E2E-M7.10) |
| `test_e2e_committee.py` | J1 onboarding · J2 a rating day · J3 term rotation · J4 password reset · J5 leaked token can't escalate · J6 removal mid-session · J7 anonymity vs attribution · J8 a week builds the trend · J9 Sheets outage · J10 member dashboard |
| `test_committee.py` | The committee checklist, by phase: 0 data layer · 1 auth core · 2 member management · 3 rating page · 3b per-meal reviews from the menu · 4 committee dashboard |
| `test_smoke.py` | One switch per feature: service, static assets, student form, submit, home, quick rating, menu editor, thank-you, student dashboard, committee login/auth/submit, member dashboard, sign in, admin login/overview/roster, member management, committee dashboard, privilege split, CSRF |
| `test_cache.py` | Refresh schedule, cached repeat reads, writes visible without a re-read, outage with nothing cached |

### 8.3 Robot — browser and HTTP

192 Robot test cases. Run one suite per invocation (section 3.2).

#### `tests/form_tests.robot` — Per-dish student form (TC01–TC23, 23 cases)

| ID | Test case | Tags |
|---|---|---|
| TC01 | Form Page Loads Successfully | smoke, form |
| TC02 | Submit Button Is Disabled On Page Load | smoke, form, validation |
| TC03 | All Emoji Buttons Are Visible | smoke, form |
| TC04 | Selecting Overall Emoji Enables Submit Button | form, validation |
| TC05 | Overall Emoji Selection Sets Hidden Input Value | form, validation |
| TC06 | Only One Overall Emoji Can Be Selected At A Time | form, validation |
| TC07 | All Five Overall Emoji Values Are Selectable | form, validation |
| TC08 | Rice Rating Rows Hidden By Default | form, rice |
| TC09 | Rice Dropdown Curry Shows Only Curry Row | form, rice |
| TC10 | Rice Dropdown Rasam Shows Only Rasam Row | form, rice |
| TC11 | Rice Dropdown Both Shows Both Rows | form, rice |
| TC12 | Rice Dropdown Reset Hides All Rice Rows | form, rice |
| TC13 | Rice Rating Clears When Dropdown Is Reset | form, rice |
| TC14 | Review Character Counter Starts At Zero | form, review |
| TC15 | Review Character Counter Updates On Input | form, review |
| TC16 | Review Field Enforces 150 Character Limit | form, review, validation |
| TC17 | Review Counter Shows 150 At Limit | form, review |
| TC18 | Minimal Submission Succeeds | form, submission, must |
| TC19 | Full Form Submission Succeeds | form, submission, must |
| TC20 | Thank You Page Has Link Back To Form | form, submission |
| TC21 | XSS In Review Is Not Executed | form, security |
| TC22 | Submitting Without Overall Shows No POST | form, validation |
| TC23 | Error Banner Displays When Flask Returns Error | form, error |

#### `tests/dashboard_tests.robot` — Student dashboard (TC24–TC38, 15 cases)

| ID | Test case | Tags |
|---|---|---|
| TC24 | Dashboard Without Token Returns 403 | dashboard, security, must |
| TC25 | Dashboard With Wrong Token Returns 403 | dashboard, security, must |
| TC26 | Dashboard With Correct Token Loads Successfully | dashboard, smoke, must |
| TC27 | All Three Stat Cards Are Present | dashboard, smoke |
| TC28 | Today Date Card Shows Correct Day | dashboard, smoke |
| TC29 | Average Card Shows Dashes When No Data | dashboard, empty-state |
| TC30 | Average Card Has Correct Colour Class | dashboard, visual |
| TC31 | Trend Chart Canvas Is Present And Rendered | dashboard, charts |
| TC32 | Item Chart Canvas Is Present And Rendered | dashboard, charts |
| TC33 | Trend Chart Defaults To 7 Day View | dashboard, charts |
| TC34 | Trend Chart Toggle Switches To 30 Days | dashboard, charts |
| TC35 | Trend Chart Toggle Switches Back To 7 Days | dashboard, charts |
| TC36 | Suggestions Section Is Present | dashboard, suggestions |
| TC37 | Empty Suggestions Shows Friendly Message | dashboard, suggestions, empty-state |
| TC38 | Suggestions Do Not Show Raw HTML Entities | dashboard, security |

#### `tests/api_tests.robot` — Student HTTP / API (TC39–TC54, 16 cases)

| ID | Test case | Tags |
|---|---|---|
| TC39 | Health Endpoint Returns 200 | api, smoke, must |
| TC40 | Health Endpoint Returns JSON Status OK | api, smoke, must |
| TC41 | Valid Minimal POST Returns 200 Or Redirect | api, submission |
| TC42 | POST Without Overall Returns Error | api, submission, validation |
| TC43 | POST With Invalid Overall Value Returns Error | api, submission, validation |
| TC44 | POST With Non-Numeric Overall Returns Error | api, submission, validation |
| TC45 | POST With XSS In Review Is Accepted But Sanitized | api, security |
| TC46 | POST With Overlong Review Is Truncated Or Rejected | api, submission, validation |
| TC47 | Rate Limit Blocks Second Submission From Same IP | api, rate-limit, must |
| TC48 | Dashboard Without Token Returns 403 | api, security, must |
| TC49 | Dashboard With Wrong Token Returns 403 | api, security |
| TC50 | Dashboard With Correct Token Returns 200 | api, security, must |
| TC51 | Dashboard Response Contains Chart Data Script | api, dashboard |
| TC52 | Dashboard Response Contains All Four Sections | api, dashboard |
| TC53 | CSS File Is Served | api, assets |
| TC54 | Dashboard JS File Is Served | api, assets |

#### `tests/committee_form_tests.robot` — Committee sign-in and rating page (TC60–TC85, 28 cases)

| ID | Test case | Tags |
|---|---|---|
| TC60 | Committee Login Page Loads | smoke, committee |
| TC61 | Login Page States That Reviews Are Attributed | committee, privacy |
| TC62 | Login Page Links Back To The Anonymous Student Form | committee |
| TC63 | Valid Login Reaches The Rating Page | smoke, committee |
| TC64 | Invalid Password Shows The Error Banner | smoke, committee, security |
| TC65 | Unknown Email Gives The Same Message As A Wrong Password | committee, security |
| TC66 | Deactivated Member Cannot Sign In | committee, security |
| TC67 | Rating Page Is Unreachable Without A Session | smoke, committee, security |
| TC68 | First Sign In Is Diverted To The Password Change | committee, security |
| TC69 | Rating Page Stays Blocked Until The Password Is Changed | committee, security |
| TC70 | Mismatched Confirmation Is Rejected | committee |
| TC71 | Changing The Password Unblocks Rating | committee |
| TC72 | All Five Dimensions Are Present | smoke, committee |
| TC73 | Submit Is Disabled Until Every Dish And Dimension Is Rated | smoke, committee |
| TC74 | Progress Hint Tracks How Many Are Rated | committee |
| TC74a | The Meal Toggle Shows Each Meal's Dishes From The Menu | smoke, committee |
| TC74b | Unreviewed Meals Are Yellow On The Toggle | committee |
| TC75 | Selecting An Emoji Marks It And Records The Value | committee |
| TC76 | Ratings Within A Dimension Are Mutually Exclusive | committee |
| TC77 | Dimensions Are Rated Independently | committee |
| TC78 | Review Character Counter Updates | committee |
| TC79 | Review Field Enforces Its Maximum Length | committee |
| TC80 | A Complete Review Submits Successfully | smoke, committee |
| TC81 | Review Is Optional | committee |
| TC82 | A Second Review Of The Same Meal Is Refused | smoke, committee |
| TC83 | A Member Who Already Rated Sees The Notice On Sign In | committee |
| TC84 | Double Submission Is Prevented Client Side | committee |
| TC85 | Signing Out Ends The Session | committee, security |

#### `tests/committee_admin_tests.robot` — Admin sign-in and roster (TC90–TC118, 29 cases)

| ID | Test case | Tags |
|---|---|---|
| TC90 | Admin Login Page Loads | smoke, admin |
| TC91 | Correct Password Opens The Roster | smoke, admin |
| TC92 | Wrong Admin Password Is Refused | smoke, admin, security |
| TC93 | Roster Is Unreachable Without An Admin Session | smoke, admin, security |
| TC94 | Dashboard Token Cannot Open The Roster | smoke, admin, security |
| TC95 | Admin Sign Out Ends The Session | admin, security |
| TC96 | Roster Lists The Seeded Members | smoke, admin |
| TC97 | Active And Inactive Members Are Badged Differently | admin |
| TC98 | A Member Who Has Not Set A Password Is Flagged | admin |
| TC99 | Roster Shows Review Counts For The Month | admin |
| TC100 | Active Member Count Is Displayed | admin |
| TC101 | Adding A Member Reveals A One-Time Password | smoke, admin |
| TC102 | The Generated Password Actually Works | smoke, admin, committee |
| TC103 | The Password Is Not Shown Again After Reload | admin, security |
| TC104 | Duplicate Email Is Rejected | admin |
| TC105 | A Retired Member Cannot Be Re-Added | admin |
| TC106 | Malformed Email Is Rejected | admin |
| TC107 | Bulk Add Creates Every Valid Row | smoke, admin |
| TC108 | Bulk Add Reveals A Password Per Member | admin |
| TC109 | Bulk Add Reports Bad Lines Individually | admin |
| TC110 | Deactivating A Member Retires Them | smoke, admin |
| TC111 | A Deactivated Member Can No Longer Sign In | admin, security |
| TC112 | Deactivation Keeps The Member On The Roster | admin |
| TC113 | Reactivating Restores Access | admin |
| TC114 | Resetting A Password Issues A New One | smoke, admin |
| TC115 | The Old Password Stops Working After A Reset | admin, security |
| TC116 | A Reset Password Forces Another Change | admin, security |
| TC117 | Member Names Are Escaped Not Executed | admin, security |
| TC118 | Admin Can Reach Both Dashboards From The Roster | admin |

#### `tests/committee_dashboard_tests.robot` — Committee dashboard (TC120–TC146, 27 cases)

| ID | Test case | Tags |
|---|---|---|
| TC120 | Dashboard Without A Credential Is Denied | smoke, dashboard, security |
| TC121 | Dashboard With A Wrong Token Is Denied | dashboard, security |
| TC122 | Dashboard Opens With The Read-Only Token | smoke, dashboard |
| TC123 | Dashboard Opens With An Admin Session | dashboard |
| TC124 | Admin Session Sees The Manage Members Link | dashboard |
| TC125 | Token Holder Is Not Shown The Manage Members Link | dashboard, security |
| TC126 | All Four Stat Cards Render | smoke, dashboard |
| TC127 | Today's Score Reflects The Seeded Review | dashboard |
| TC128 | Response Count Matches The Reviews Filed Today | dashboard |
| TC129 | Active Member Count Excludes Retired Members | dashboard |
| TC130 | Participation Is A Percentage Of Active Members | dashboard |
| TC131 | Score Card Is Colour Coded | dashboard |
| TC132 | Both Chart Canvases Render | smoke, dashboard |
| TC133 | Chart.js Actually Draws The Dimension Chart | dashboard |
| TC134 | The Dimension Chart Plots All Five Areas | dashboard |
| TC135 | The Trend Chart Carries Overall Plus Each Dimension | dashboard |
| TC136 | Per-Dimension Trend Lines Start Hidden | dashboard |
| TC137 | Trend Toggle Buttons Render | smoke, dashboard |
| TC138 | Seven Day View Is Active By Default | dashboard |
| TC139 | Switching To One Month Updates The Chart Title | dashboard |
| TC140 | Toggling Back To Seven Days Restores The View | dashboard |
| TC141 | Review Feed Renders With Attribution | smoke, dashboard |
| TC142 | Review Feed Is Newest First | dashboard |
| TC143 | Student Dashboard Still Renders | smoke, dashboard |
| TC144 | Committee Reviews Do Not Appear On The Student Dashboard | dashboard, security |
| TC145 | Student Feedback Does Not Appear On The Committee Dashboard | dashboard |
| TC146 | The Two Dashboards Cross-Link | dashboard |

#### `tests/committee_api_tests.robot` — Committee HTTP / security (TC150–TC172, 23 cases)

| ID | Test case | Tags |
|---|---|---|
| TC150 | Committee Login Page Returns 200 | smoke, api, committee |
| TC151 | Admin Login Page Returns 200 | smoke, api, admin |
| TC152 | Rating Page Redirects When Unauthenticated | smoke, api, security |
| TC153 | Roster Redirects When Unauthenticated | smoke, api, security |
| TC154 | Token Opens The Committee Dashboard | smoke, api |
| TC155 | Committee Dashboard Without A Token Is 403 | smoke, api, security |
| TC156 | Token Does Not Open The Roster | smoke, api, security |
| TC157 | Token Cannot Add A Member | smoke, api, security |
| TC158 | Token Cannot Bulk Add Members | api, security |
| TC159 | Token Cannot Reset A Password | api, security |
| TC160 | The Attacker Created Nothing | api, security |
| TC161 | Login Without A CSRF Token Is Rejected | smoke, api, security |
| TC162 | Admin Login Without A CSRF Token Is Rejected | api, security |
| TC163 | A Forged CSRF Token Is Rejected | api, security |
| TC164 | Review Submission Without A CSRF Token Is Rejected | api, security |
| TC165 | A Member Can Sign In And Submit Over Plain HTTP | smoke, api, committee |
| TC166 | The Submitted Review Reaches The Dashboard | api, committee |
| TC167 | A Second Submission Of The Same Meal Is Refused | api, committee |
| TC168 | An Out Of Range Rating Is Rejected | api, committee |
| TC169 | A Missing Dimension Is Rejected | api, committee |
| TC170 | Health Endpoint Still Responds | smoke, api |
| TC171 | Student Form Still Serves | smoke, api |
| TC172 | Student Dashboard Still Serves | smoke, api |

#### `tests/home_tests.robot` — Menu page, quick taps, menu editor (TC180–TC199, 20 cases)

| ID | Test case | Tags |
|---|---|---|
| TC180 | Home Page Loads Without A Login | smoke, home |
| TC181 | All Three Meals Are Shown | smoke, home |
| TC182 | Today's Dishes Are Listed As Separate Items | home |
| TC183 | Serving Times Are Shown | home |
| TC184 | Each Meal Offers Good Bad And Skip | smoke, home |
| TC185 | Tapping Good Records A Reaction | smoke, home |
| TC186 | Tapping Skip Is Recorded Too | home |
| TC187 | A Tally Appears Once A Meal Has Been Rated | home |
| TC188 | The Suggestion Box Is Hidden Until Asked For | home |
| TC189 | Opening The Disclosure Reveals The Suggestion Field | home |
| TC190 | A Suggestion Can Be Sent With A Reaction | home |
| TC191 | Home Links Through To The Detailed Form | home |
| TC192 | Menu Editor Is Closed Without An Admin Session | smoke, home, security |
| TC193 | Dashboard Token Cannot Open The Menu Editor | smoke, home, security |
| TC194 | Menu Editor Opens For An Admin | smoke, home |
| TC195 | Today Is Marked In The Editor | home |
| TC196 | Publishing A Menu Reaches Students | smoke, home |
| TC197 | An Unpublished Day Says So | home |
| TC198 | The Per-Dish Form Is Untouched | smoke, home |
| TC199 | The Committee Flow Is Unaffected | home |

#### `tests/menu_categories_tests.robot` — Menu categories and CSV uploads (TC200–TC210, 11 cases)

| ID | Test case | Tags |
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
