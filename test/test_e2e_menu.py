"""
MessMate Menu Categories & Uploads — End-to-End Journeys (test/test_e2e_menu.py)
---------------------------------------------------------------------------------
The categorised menu from the admin's hands to every screen that shows it,
and both CSV upload layouts, through the real Flask routes against the
in-memory sheets backend.

  M1  An admin types a categorised menu in the editor
  M2  Students see each category beside its dishes
  M3  Ratings, the committee form and the dashboards get bare dish names
  M4  The CSV template is the mess's weekly grid
  M5  A filled grid uploads, the way the mess writes it
  M6  The older Date/Breakfast/Lunch/Dinner layout still uploads
  M7  Bad uploads are refused without touching the sheet

Step IDs (E2E-Mn.k) match docs/MENU_CATEGORIES_TEST_PLAN.md. The pure parsing
rules are unit-tested in test/test_menu_categories.py; this file checks that
the routes, templates and storage put them together correctly.

Runs with NO Google credentials, no browser, no server.

Usage:
    python test/test_e2e_menu.py

Exit code 0 = every step passed.
"""

import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["FLASK_SECRET_KEY"] = "e2e-menu-secret-key"
os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
os.environ["DASHBOARD_TOKEN"] = "vc2026"

import auth      # noqa: E402
import sheets    # noqa: E402

ADMIN_PASSWORD = "e2e-menu-admin"
os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(ADMIN_PASSWORD)

import fake_sheets        # noqa: E402
import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True
app_module.limiter.enabled = False
app.config["ENFORCE_MEAL_WINDOWS"] = False

BOOK = fake_sheets.install()
TODAY = datetime.now().strftime("%Y-%m-%d")
WEEK = sheets.week_start(TODAY)
WEEK_DT = datetime.strptime(WEEK, "%Y-%m-%d")
WEEK_DATES = [(WEEK_DT + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
# Day-first, as the mess's sheet and Excel on an Indian locale write it
DAY_FIRST = {d: datetime.strptime(d, "%Y-%m-%d").strftime("%d-%m-%Y") for d in WEEK_DATES}

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
WEEK_JSON_RE = re.compile(r"window\.MESSMATE_WEEK = (\{.*?\});\n", re.S)

RESULTS = []
_current = {"journey": None}


def journey(name):
    print(f"\n{name}\n{'-' * len(name)}")
    _current["journey"] = name


def step(description, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((_current["journey"], description, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {description}")
    if not ok and detail:
        print(f"         -> {detail}")
    return ok


def home(query=""):
    return app.test_client().get("/home" + query).get_data(as_text=True)


def meal_list(html, meal):
    """The rendered <ul> for one meal card, or ""."""
    match = re.search(rf'<ul class="menu-items[^"]*" id="menu-{meal.lower()}">.*?</ul>',
                      html, re.S)
    return match.group(0) if match else ""


def rows_by_date():
    return {r[0]: r for r in BOOK.menu().rows}


def stored_cell(date, meal):
    """One stored meal cell, "" when the date has no row — a failing step
    reports, it never crashes the run."""
    row = rows_by_date().get(date)
    return row[1 + sheets.MEALS.index(meal)] if row else ""


def in_order(text, *parts):
    positions = [text.find(p) for p in parts]
    return all(p >= 0 for p in positions) and positions == sorted(positions)


def csv_text(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


class Admin:
    def __init__(self):
        self.client = app.test_client()

    def _csrf(self, path="/admin/menu"):
        match = CSRF_RE.search(self.client.get(path).get_data(as_text=True))
        return match.group(1) if match else ""

    def login(self):
        token = self._csrf("/admin/login")
        return self.client.post("/admin/login", data={
            "password": ADMIN_PASSWORD, "csrf_token": token})

    def save_menu(self, date, breakfast="", lunch="", dinner=""):
        return self.client.post("/admin/menu/save", data={
            "date": date, "Breakfast": breakfast, "Lunch": lunch,
            "Dinner": dinner, "csrf_token": self._csrf()})

    def save_week(self, start, days):
        data = {"csrf_token": self._csrf(), "start": start}
        for date, (b, l, d) in days.items():
            data[f"Breakfast__{date}"], data[f"Lunch__{date}"], data[f"Dinner__{date}"] = b, l, d
        return self.client.post("/admin/menu/save-week", data=data)

    def template(self, start=""):
        return self.client.get("/admin/menu/template.csv" + (f"?start={start}" if start else ""))

    def upload(self, payload, filename="menu.csv", start=WEEK, csrf=True):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        data = {"start": start}
        if csrf:
            data["csrf_token"] = self._csrf()
        if payload is not None:
            data["file"] = (io.BytesIO(payload), filename)
        return self.client.post("/admin/menu/import", data=data,
                                content_type="multipart/form-data")


def signed_in_admin():
    admin = Admin()
    admin.login()
    return admin


# ══════════════════════════════════════════════════════════════════════════════
# M1 — An admin types a categorised menu in the editor
# ══════════════════════════════════════════════════════════════════════════════

def m1_editor():
    journey("M1 — An admin types a categorised menu in the editor")
    BOOK.reset()
    admin = signed_in_admin()

    page = admin.client.get(f"/admin/menu?start={WEEK}").get_data(as_text=True)
    step("E2E-M1.1 the editor explains the Category: Dish format",
         "<code>Category: Dish</code>" in page)
    monday_bf = sheets.WEEKLY_MENU_DEFAULTS[0]["Breakfast"].split("\n")[0]
    step("E2E-M1.2 the placeholder is the categorised weekly template",
         f'placeholder="{monday_bf}' in page, monday_bf)
    rows_attr = re.search(rf'id="{WEEK_DATES[0]}-Lunch" name="Lunch"', page) and \
        re.search(rf'<textarea class="menu-input" rows="(\d+)"\s+id="{WEEK_DATES[0]}-Lunch"', page)
    step("E2E-M1.3 a field is tall enough for a categorised meal",
         rows_attr and int(rows_attr.group(1)) >= 10,
         rows_attr.group(1) if rows_attr else "no rows attribute")

    response = admin.save_menu(TODAY,
                               breakfast="Main Item: Pongal\nEgg:\nChutney: Coconut Chutney",
                               lunch="Rice: Steamed Rice, Curd: Curd")
    stored = rows_by_date().get(TODAY, [""] * 4)
    step("E2E-M1.4 saving one day stores one Category: Dish per line",
         response.status_code == 200 and stored[2] == "Rice: Steamed Rice\nCurd: Curd",
         repr(stored))
    step("E2E-M1.5 a template row left blank is not stored",
         stored[1] == "Main Item: Pongal\nChutney: Coconut Chutney", repr(stored[1]))

    admin.save_menu(TODAY, breakfast="Egg:\nBread:")
    page = admin.client.get(f"/admin/menu?start={WEEK}").get_data(as_text=True)
    step("E2E-M1.6 a meal of only blank rows counts as not published",
         TODAY in rows_by_date() and stored_cell(TODAY, "Breakfast") == ""
         and "Not published" in page)

    days = {d: (sheets.menu_template_for_date(d)["Breakfast"],
                sheets.menu_template_for_date(d)["Lunch"],
                sheets.menu_template_for_date(d)["Dinner"]) for d in WEEK_DATES}
    response = admin.save_week(WEEK, days)
    stored = rows_by_date()
    step("E2E-M1.7 Save all 7 days writes the whole categorised week",
         response.status_code == 200 and all(
             stored.get(d, [])[1:] == list(days[d]) for d in WEEK_DATES),
         f"status={response.status_code}")
    step("E2E-M1.8 re-saving updates rows rather than adding them",
         len(BOOK.menu().rows) == 7, f"rows={len(BOOK.menu().rows)}")


# ══════════════════════════════════════════════════════════════════════════════
# M2 — Students see each category beside its dishes
# ══════════════════════════════════════════════════════════════════════════════

def m2_home():
    journey("M2 — Students see each category beside its dishes")
    BOOK.reset()
    BOOK.seed_menu(TODAY,
                   breakfast="Main Item: Pongal\nSpread: Butter\nSpread: Jam\nBeverage: Coffee",
                   lunch="Rice, Sambar, Curd")
    html = home()
    breakfast, lunch = meal_list(html, "Breakfast"), meal_list(html, "Lunch")

    step("E2E-M2.1 a categorised meal uses the two-column list",
         'class="menu-items menu-items-categorised"' in breakfast, breakfast[:120])
    step("E2E-M2.2 each line pairs a category with its dishes",
         '<span class="menu-cat">Main Item</span> <span class="menu-dish">Pongal</span>' in breakfast)
    step("E2E-M2.3 consecutive Spread rows read as one line",
         '<span class="menu-cat">Spread</span> <span class="menu-dish">Butter, Jam</span>' in breakfast
         and breakfast.count('menu-cat">Spread') == 1)
    step("E2E-M2.4 lines keep the mess's order",
         in_order(breakfast, "Main Item", "Spread", "Beverage"))
    step("E2E-M2.5 a menu without categories keeps one chip per dish",
         'class="menu-items" id="menu-lunch"' in lunch and lunch.count("<li>") == 3
         and "menu-cat" not in lunch, lunch)
    dinner = meal_list(html, "Dinner")
    step("E2E-M2.6 an unpublished meal still says so",
         "Menu not published yet" in dinner and "menu-items-categorised" not in dinner)

    match = WEEK_JSON_RE.search(html)
    week = json.loads(match.group(1)) if match else {}
    step("E2E-M2.7 the day switcher gets the same groups",
         week.get(TODAY, {}).get("Breakfast", [None])[1:2] ==
         [{"category": "Spread", "dishes": ["Butter", "Jam"]}],
         str(week.get(TODAY, {}).get("Breakfast")))

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    BOOK.seed_menu(tomorrow, dinner="Korma: Egg Curry")
    other = meal_list(home(f"?date={tomorrow}"), "Dinner")
    step("E2E-M2.8 another day's page shows that day's categories",
         '<span class="menu-cat">Korma</span> <span class="menu-dish">Egg Curry</span>' in other,
         other)

    BOOK.seed_menu(TODAY, breakfast="<b>Main</b>: <img src=x onerror=alert(1)>")
    escaped = meal_list(home(), "Breakfast")
    step("E2E-M2.9 categories and dishes from the sheet are escaped",
         "<img" not in escaped and "&lt;b&gt;Main&lt;/b&gt;" in escaped, escaped)


# ══════════════════════════════════════════════════════════════════════════════
# M3 — Everything that rates dishes gets bare dish names
# ══════════════════════════════════════════════════════════════════════════════

def m3_other_surfaces():
    journey("M3 — Ratings, the committee form and the dashboards get bare dish names")
    BOOK.reset()
    BOOK.seed_menu(TODAY,
                   breakfast="Main Item: Pongal\nChutney: Coconut Chutney",
                   lunch="Rice: Steamed Rice\nCurd: Curd",
                   dinner="Bread / Tiffin: Chappathi")

    step("E2E-M3.1 the menu lookup ratings use returns dish names",
         sheets.get_menu_for_date(TODAY)["Lunch"] == ["Steamed Rice", "Curd"])

    email, password = "menu-e2e@sai.edu", "menu-e2e-password"
    BOOK.seed_member(email, "Menu Tester", password)
    member = app.test_client()
    token = CSRF_RE.search(member.get("/committee/login").get_data(as_text=True)).group(1)
    member.post("/committee/login", data={"email": email, "password": password,
                                          "csrf_token": token})
    form = member.get("/committee?meal=Breakfast").get_data(as_text=True)
    step("E2E-M3.2 the committee form lists each dish once, without its category",
         'data-dish-name="Pongal"' in form and 'data-dish-name="Coconut Chutney"' in form
         and "Main Item:" not in form, re.findall(r'data-dish-name="([^"]*)"', form))

    admin = signed_in_admin()
    overview = admin.client.get("/admin").get_data(as_text=True)
    step("E2E-M3.3 the admin overview shows dish chips, not raw cells",
         "Steamed Rice" in overview and "Rice: Steamed Rice" not in overview
         and "Main Item:" not in overview)

    dashboard = app.test_client().get("/dashboard?token=vc2026").get_data(as_text=True)
    step("E2E-M3.4 the student dashboard shows dish chips",
         "Chappathi" in dashboard and "Bread / Tiffin:" not in dashboard)


# ══════════════════════════════════════════════════════════════════════════════
# M4 — The CSV template is the mess's weekly grid
# ══════════════════════════════════════════════════════════════════════════════

def m4_template():
    journey("M4 — The CSV template is the mess's weekly grid")
    BOOK.reset()

    anonymous = app.test_client().get("/admin/menu/template.csv")
    step("E2E-M4.1 the template needs an admin session",
         anonymous.status_code == 302 and "signin" in anonymous.headers.get("Location", ""),
         f"status={anonymous.status_code}")

    admin = signed_in_admin()
    response = admin.template(WEEK)
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    step("E2E-M4.2 it downloads as a CSV named for the week",
         response.status_code == 200 and response.mimetype == "text/csv"
         and f"menu_template_{WEEK}.csv" in response.headers.get("Content-Disposition", ""))
    step("E2E-M4.3 the header is Meal, Category, then the seven dates",
         rows and rows[0] == ["Meal", "Category"] + WEEK_DATES, rows[0] if rows else None)
    step("E2E-M4.4 the second row names the weekdays",
         len(rows) > 1 and rows[1][2:] == ["Monday", "Tuesday", "Wednesday", "Thursday",
                                           "Friday", "Saturday", "Sunday"])
    expected = [[m, c] for m in sheets.MEALS for c in sheets.MENU_CATEGORIES[m]]
    step("E2E-M4.5 one row per category, Breakfast to Dinner, no Snacks",
         [r[:2] for r in rows[2:]] == expected and not any(r[0] == "Snacks" for r in rows),
         f"{len(rows) - 2} category rows")
    step("E2E-M4.6 every dish cell starts blank",
         all(cell == "" for r in rows[2:] for cell in r[2:]))

    midweek = (WEEK_DT + timedelta(days=3)).strftime("%Y-%m-%d")
    snapped = list(csv.reader(io.StringIO(admin.template(midweek).get_data(as_text=True))))
    step("E2E-M4.7 a mid-week ?start snaps to that week's Monday",
         snapped[0][2] == WEEK, snapped[0][2])
    default = list(csv.reader(io.StringIO(admin.template("garbage").get_data(as_text=True))))
    step("E2E-M4.8 a bad ?start falls back to the current week",
         default[0][2] == sheets.week_start(), default[0][2])

    page = admin.client.get("/admin/menu").get_data(as_text=True)
    step("E2E-M4.9 the editor describes the grid layout and the old one",
         "<code>Meal, Category</code>" in page and "<code>Date, Breakfast, Lunch, Dinner</code>" in page)


# ══════════════════════════════════════════════════════════════════════════════
# M5 — A filled grid uploads, the way the mess writes it
# ══════════════════════════════════════════════════════════════════════════════

def filled_template(admin, fill):
    """Downloads the template and fills it: fill(meal, category, date) -> cell."""
    rows = list(csv.reader(io.StringIO(admin.template(WEEK).get_data(as_text=True))))
    dates = rows[0][2:]
    for row in rows[2:]:
        row[2:] = [fill(row[0], row[1], d) or "" for d in dates]
    return rows


def m5_grid_upload():
    journey("M5 — A filled grid uploads, the way the mess writes it")
    BOOK.reset()
    admin = signed_in_admin()

    # Round trip: download, fill every day with the Sai week, upload
    spreads = {}

    def sai(meal, category, date):
        weekday = WEEK_DATES.index(date)
        entries = sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[weekday][meal])
        matches = [d for c, d in entries if c == category]
        if category == "Spread":            # two template rows: Butter, then Jam
            n = spreads.get((meal, date), 0)
            spreads[(meal, date)] = n + 1
            return matches[n] if n < len(matches) else ""
        return matches[0] if matches else ""

    rows = filled_template(admin, sai)
    response = admin.upload(csv_text(rows), "week.csv")
    body = response.get_data(as_text=True)
    stored = rows_by_date()
    step("E2E-M5.1 the filled template imports all seven days",
         response.status_code == 200 and "Imported 7 days." in body
         and sorted(stored) == WEEK_DATES, f"status={response.status_code}")
    step("E2E-M5.2 what is stored is the week that was filled in",
         all(stored.get(d, [])[1:] == [sheets.WEEKLY_MENU_DEFAULTS[i][m] for m in sheets.MEALS]
             for i, d in enumerate(WEEK_DATES)))
    step("E2E-M5.3 the editor comes back on the imported week, days marked saved",
         f'data-menu-day="{WEEK_DATES[0]}"' in body and body.count("menu-day-saved") == 7)

    response = admin.upload(csv_text(rows), "week.csv")
    step("E2E-M5.4 uploading the same file again updates, never duplicates",
         response.status_code == 200 and len(BOOK.menu().rows) == 7,
         f"rows={len(BOOK.menu().rows)}")

    # The mess's own habits: day-first dates, merged Meal cells, a Snacks block
    BOOK.reset()
    keep = WEEK_DATES[2]
    BOOK.seed_menu(keep, lunch="Rice: Already Published")
    d0, d1 = WEEK_DATES[0], WEEK_DATES[1]
    sheet = csv_text([
        ["Meal", "Category", DAY_FIRST[d0], DAY_FIRST[d1], DAY_FIRST[keep], "Notes"],
        ["", "", "Monday", "Tuesday", "Wednesday", ""],
        ["Breakfast", "Main Item", "Mix Veg Sevai", "Idly", "", "from the mess"],
        ["", "Spread", "Butter", "Butter", "", ""],
        ["", "Spread", "Jam", "Jam", "", ""],
        ["Snacks", "Tea", "Tea", "Tea", "", ""],
        ["", "Snack 1 ( Fried )", "Aloo Samosa", "Veg Puff", "", ""],
        ["Dinner", "Rice", "Mint Pulao, Steamed Rice", "Steamed Rice", "", ""],
    ])
    response = admin.upload(sheet, "mess.csv")
    body = response.get_data(as_text=True)
    stored = rows_by_date()
    step("E2E-M5.5 day-first date headers are read as dates",
         response.status_code == 200 and d0 in stored and d1 in stored, list(stored))
    step("E2E-M5.6 a blank Meal cell carries the meal from above",
         stored.get(d0, [""] * 4)[1] == "Main Item: Mix Veg Sevai\nSpread: Butter\nSpread: Jam",
         repr(stored.get(d0)))
    step("E2E-M5.7 a comma cell becomes two dishes in one category",
         stored.get(d0, [""] * 4)[3] == "Rice: Mint Pulao\nRice: Steamed Rice")
    step("E2E-M5.8 Snacks rows are skipped and the admin is told",
         "Samosa" not in str(stored) and "Puff" not in str(stored)
         and "Skipped Snacks — only Breakfast, Lunch, Dinner are published." in body)
    step("E2E-M5.9 an empty date column leaves a published day alone",
         stored.get(keep, [""] * 4)[2] == "Rice: Already Published"
         and "Left 1 empty day unchanged." in body, repr(stored.get(keep)))
    step("E2E-M5.10 a Notes column is ignored",
         "from the mess" not in str(stored))

    home_html = home(f"?date={d0}")
    step("E2E-M5.11 the uploaded day reaches students with its categories",
         '<span class="menu-cat">Spread</span> <span class="menu-dish">Butter, Jam</span>'
         in meal_list(home_html, "Breakfast"))

    bom = "﻿" + csv_text([["Meal", "Category", d0], ["Lunch", "Rice", "Lemon Rice"]])
    response = admin.upload(bom, "excel.csv")
    step("E2E-M5.12 an Excel byte-order mark does not hide the Meal column",
         response.status_code == 200 and stored_cell(d0, "Lunch") == "Rice: Lemon Rice")


# ══════════════════════════════════════════════════════════════════════════════
# M6 — The older layout still uploads
# ══════════════════════════════════════════════════════════════════════════════

def m6_by_meal_upload():
    journey("M6 — The older Date/Breakfast/Lunch/Dinner layout still uploads")
    BOOK.reset()
    admin = signed_in_admin()
    d0, d1 = WEEK_DATES[0], WEEK_DATES[1]

    response = admin.upload(csv_text([
        ["Date", "Breakfast", "Lunch", "Dinner"],
        [d0, "Idli, Sambar", "", "Chapati"],
        [d1, "Main Item: Idly\nChutney: Peanut Chutney", "", ""],
        ["next week", "x", "", ""],
    ]))
    body = response.get_data(as_text=True)
    step("E2E-M6.1 the older layout imports",
         response.status_code == 200 and "Imported 2 days." in body)
    step("E2E-M6.2 its comma lists are stored one dish per line",
         stored_cell(d0, "Breakfast") == "Idli\nSambar", repr(stored_cell(d0, "Breakfast")))
    step("E2E-M6.3 categories typed into its cells are kept",
         stored_cell(d1, "Breakfast") == "Main Item: Idly\nChutney: Peanut Chutney")
    step("E2E-M6.4 a bad date is skipped and reported by line",
         "Skipped line 4 (bad date)." in body)
    lunch = meal_list(home(f"?date={d0}"), "Breakfast")
    step("E2E-M6.5 an uncategorised upload still shows as chips",
         "menu-items-categorised" not in lunch and "<li>Idli</li>" in lunch, lunch)


# ══════════════════════════════════════════════════════════════════════════════
# M7 — Bad uploads are refused without touching the sheet
# ══════════════════════════════════════════════════════════════════════════════

def m7_refusals():
    journey("M7 — Bad uploads are refused without touching the sheet")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice: Untouched")
    admin = signed_in_admin()
    d0 = WEEK_DATES[0]

    def untouched():
        return BOOK.menu().rows == [[TODAY, "", "Rice: Untouched", ""]]

    cases = [
        ("E2E-M7.1 no file chosen", admin.upload(None),
         400, "Choose a CSV file to import."),
        ("E2E-M7.2 a file over 1 MB",
         admin.upload("x" * (app_module.MENU_IMPORT_MAX_BYTES + 1)),
         400, "That file is too large (max 1 MB)."),
        ("E2E-M7.3 a file that is not UTF-8",
         admin.upload("Meal,Category\n".encode() + b"\xff\xfe\x00bad"),
         400, "save it as UTF-8 CSV"),
        ("E2E-M7.4 a grid with no date columns",
         admin.upload(csv_text([["Meal", "Category", "Monday"], ["Lunch", "Rice", "x"]])),
         400, "No date columns found."),
        ("E2E-M7.5 a header matching neither layout",
         admin.upload(csv_text([["Day", "Food"], [d0, "Rice"]])),
         400, "CSV needs a header row with columns Meal, Category"),
        ("E2E-M7.6 a grid with every cell blank",
         admin.upload(csv_text([["Meal", "Category", d0], ["Lunch", "Rice", ""]])),
         400, "No valid rows found in that CSV."),
        ("E2E-M7.7 a grid of only Snacks",
         admin.upload(csv_text([["Meal", "Category", d0], ["Snacks", "Tea", "Tea"]])),
         400, "Skipped Snacks"),
        ("E2E-M7.8 an empty file",
         admin.upload(""),
         400, "CSV needs a header row"),
    ]
    for description, response, status, message in cases:
        body = response.get_data(as_text=True)
        step(f"{description} is refused with a reason",
             response.status_code == status and message in body and untouched(),
             f"status={response.status_code}")

    no_csrf = admin.upload(csv_text([["Meal", "Category", d0], ["Lunch", "Rice", "x"]]),
                           csrf=False)
    step("E2E-M7.9 an upload without a CSRF token is refused",
         no_csrf.status_code == 403 and untouched(), f"status={no_csrf.status_code}")

    stranger = app.test_client().post(
        "/admin/menu/import",
        data={"start": WEEK, "file": (io.BytesIO(b"Meal,Category\n"), "x.csv")},
        content_type="multipart/form-data")
    step("E2E-M7.10 a signed-out upload is sent to sign in, nothing written",
         stranger.status_code in (302, 403) and untouched(), f"status={stranger.status_code}")


def report():
    print(f"\n{'=' * 70}\nMENU CATEGORIES & UPLOADS END-TO-END SUMMARY\n{'=' * 70}")
    journeys = {}
    for name, _, ok, _ in RESULTS:
        journeys.setdefault(name, []).append(ok)
    for name, outcomes in journeys.items():
        print(f"  [{'PASS' if all(outcomes) else 'FAIL'}] {name}  "
              f"({sum(outcomes)}/{len(outcomes)} steps)")
    failed = [r for r in RESULTS if not r[2]]
    print(f"\n  {len(RESULTS) - len(failed)}/{len(RESULTS)} steps passed "
          f"across {len(journeys)} journeys")
    if failed:
        print("\n  FAILED STEPS:")
        for name, description, _, detail in failed:
            print(f"    {name}\n      {description}")
            if detail:
                print(f"      {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    print("MessMate — menu categories & uploads end-to-end journeys")
    print("(in-memory sheets backend; no Google credentials required)")
    m1_editor()
    m2_home()
    m3_other_surfaces()
    m4_template()
    m5_grid_upload()
    m6_by_meal_upload()
    m7_refusals()
    sys.exit(report())
