"""
MessMate Student Home — End-to-End Journeys (test/test_e2e_home.py)
---------------------------------------------------------------------
Covers the menu page and the one-tap reaction per meal, plus the admin menu
editor that publishes what students see.

The point of this surface is that it is the cheapest thing a student can do:
one tap, no login, no eleven-dish form. These journeys check that the cheap
path stays cheap and that its data never gets mixed into the other two
feedback layers.

Runs with NO Google credentials.

Usage:
    python test/test_e2e_home.py
"""

import io
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["FLASK_SECRET_KEY"] = "e2e-home-secret-key"
os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
os.environ["DASHBOARD_TOKEN"] = "vc2026"

import auth      # noqa: E402
import sheets    # noqa: E402

ADMIN_PASSWORD = "e2e-home-admin"
os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(ADMIN_PASSWORD)

import fake_sheets        # noqa: E402
import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True
LIMITER = app_module.limiter
LIMITER.enabled = False
# Serving windows are wall-clock rules; the journeys must pass at 6 am too.
# H8 switches it on deliberately to test it.
app.config["ENFORCE_MEAL_WINDOWS"] = False

BOOK = fake_sheets.install()
TODAY = datetime.now().strftime("%Y-%m-%d")

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')

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
    return app.test_client().get("/home" + query)


def rate(meal, rating, suggestion="", client=None):
    return (client or app.test_client()).post(
        "/home/rate",
        data={"meal": meal, "rating": rating, "suggestion": suggestion})


class Admin:
    def __init__(self):
        self.client = app.test_client()

    def _csrf(self, path):
        html = self.client.get(path).get_data(as_text=True)
        match = CSRF_RE.search(html)
        return match.group(1) if match else ""

    def login(self):
        token = self._csrf("/admin/login")
        return self.client.post("/admin/login",
                                data={"password": ADMIN_PASSWORD,
                                      "csrf_token": token})

    def save_week(self, start, days):
        """days: {date: (breakfast, lunch, dinner)} — the Save-all-7-days request."""
        token = self._csrf("/admin/menu")
        data = {"csrf_token": token, "start": start}
        for date, (b, l, d) in days.items():
            data[f"Breakfast__{date}"] = b
            data[f"Lunch__{date}"] = l
            data[f"Dinner__{date}"] = d
        return self.client.post("/admin/menu/save-week", data=data)

    def save_menu(self, date, breakfast="", lunch="", dinner=""):
        token = self._csrf("/admin/menu")
        return self.client.post("/admin/menu/save", data={
            "date": date, "Breakfast": breakfast, "Lunch": lunch,
            "Dinner": dinner, "csrf_token": token})


# ══════════════════════════════════════════════════════════════════════════════
# H1 — A student checks what's for lunch and reacts
# ══════════════════════════════════════════════════════════════════════════════

def h1_menu_and_reaction():
    journey("H1 — A student opens the menu and taps once")
    BOOK.reset()
    BOOK.seed_menu(TODAY,
                   breakfast="Idli, Sambar, Coconut Chutney",
                   lunch="Rice, Sambar, Poriyal, Curd",
                   dinner="Chapati, Paneer Gravy, Salad")

    page = home()
    html = page.get_data(as_text=True)

    step("the home page serves without a login", page.status_code == 200)

    step("all three meals are shown",
         all(f'data-meal="{meal}"' in html for meal in sheets.MEALS))

    step("today's dishes are listed",
         "Coconut Chutney" in html and "Poriyal" in html and
         "Paneer Gravy" in html)

    step("items are split into separate entries, not one blob",
         html.count("<li>") >= 10, f"list items={html.count('<li>')}")

    step("serving times are shown", "12:00" in html)

    step("each meal offers good, bad and skip",
         all(html.count(f'data-rating="{r}"') == 3 for r in sheets.RATINGS),
         "expected three of each button, one per meal")

    result = rate("Lunch", "good", "More curd please")
    step("a reaction redirects back to the menu",
         result.status_code == 302 and "/home" in result.headers.get("Location", ""),
         f"status={result.status_code}")

    row = BOOK.meal_ratings().rows[0]
    step("the reaction is stored against the right meal",
         len(BOOK.meal_ratings().rows) == 1 and row[2] == "Lunch" and
         row[3] == "good", f"row={row}")

    step("the suggestion rides along with it",
         row[4] == "More curd please", f"stored={row[4]!r}")

    step("nothing identifying is stored",
         not any(marker in " ".join(str(c) for c in row).lower()
                 for marker in ("@", "127.0.0.1", "session", "cookie")),
         f"row={row}")

    step("the confirmation names the meal just rated",
         "lunch" in home("?rated=lunch").get_data(as_text=True).lower())


# ══════════════════════════════════════════════════════════════════════════════
# H2 — The day's tallies build up
# ══════════════════════════════════════════════════════════════════════════════

def h2_tallies():
    journey("H2 — Reactions accumulate into a per-meal tally")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice, Sambar")

    for rating in ["good"] * 7 + ["bad"] * 3 + ["skip"] * 5:
        BOOK.seed_meal_rating(TODAY, "Lunch", rating)

    summary = sheets.summarise_meal_ratings(TODAY)["Lunch"]
    step("each reaction type is counted",
         summary["good"] == 7 and summary["bad"] == 3 and summary["skip"] == 5,
         f"summary={summary}")

    step("the score is good as a share of those who ate, not of everyone",
         summary["score"] == 70,
         f"expected 70 (7 of 10 who ate), got {summary['score']}")

    step("skips are counted but kept out of the score",
         summary["total"] == 15 and summary["score"] == 70,
         f"summary={summary}")

    html = home().get_data(as_text=True)
    step("the tally shows on the lunch card", "70%" in html and "15 rated" in html)

    step("meals nobody rated show no tally",
         html.count("tally-score") == 1,
         "an unrated meal is displaying a tally")

    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice")
    for rating in ["skip"] * 4:
        BOOK.seed_meal_rating(TODAY, "Lunch", rating)
    only_skips = sheets.summarise_meal_ratings(TODAY)["Lunch"]
    step("a meal everyone skipped scores 0 rather than dividing by zero",
         only_skips["score"] == 0 and only_skips["total"] == 4,
         f"summary={only_skips}")


# ══════════════════════════════════════════════════════════════════════════════
# H3 — Validation and limits
# ══════════════════════════════════════════════════════════════════════════════

def h3_validation():
    journey("H3 — Bad input is refused, and one device gets three taps a day")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice")

    for meal, rating in [("Brunch", "good"), ("Lunch", "amazing"),
                         ("", "good"), ("Lunch", "")]:
        rate(meal, rating)
    step("unknown meals and ratings write nothing",
         len(BOOK.meal_ratings().rows) == 0,
         f"rows={len(BOOK.meal_ratings().rows)}")

    step("an invalid attempt says so rather than failing silently",
         "invalid" in rate("Brunch", "good").headers.get("Location", ""))

    rate("Lunch", "good", suggestion="x" * 500)
    step("an overlong suggestion is truncated to 200 characters",
         len(BOOK.meal_ratings().rows[0][4]) == 200,
         f"length={len(BOOK.meal_ratings().rows[0][4])}")

    step("meal names are accepted case-insensitively",
         rate("lunch", "good").status_code == 302 and
         BOOK.meal_ratings().rows[-1][2] == "Lunch",
         f"stored={BOOK.meal_ratings().rows[-1][2]!r}")

    # Three meals a day, so three taps a day per device (one browser =
    # one cookie; the fourth, on an already-rated meal, is refused)
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice")
    LIMITER.enabled = True
    try:
        client = app.test_client()
        codes = [rate("Breakfast", "good", client=client).status_code,
                 rate("Lunch", "good", client=client).status_code,
                 rate("Dinner", "good", client=client).status_code,
                 rate("Lunch", "bad", client=client).status_code]
        step("three reactions are allowed and the fourth is refused",
             codes[:3] == [302, 302, 302] and codes[3] == 429,
             f"codes={codes}")
        step("only the first three were stored",
             len(BOOK.meal_ratings().rows) == 3,
             f"rows={len(BOOK.meal_ratings().rows)}")
    finally:
        LIMITER.enabled = False


# ══════════════════════════════════════════════════════════════════════════════
# H4 — Publishing a menu through the admin UI
# ══════════════════════════════════════════════════════════════════════════════

def h4_admin_editor():
    journey("H4 — An admin publishes the week, and students see it")
    BOOK.reset()

    step("the editor is closed without an admin session",
         app.test_client().get("/admin/menu").status_code == 302)

    step("a dashboard token cannot open it",
         app.test_client().get("/admin/menu?token=vc2026").status_code == 302,
         "the read-only token reached the menu editor")

    admin = Admin()
    admin.login()
    page = admin.client.get("/admin/menu")
    html = page.get_data(as_text=True)

    step("the editor opens for an admin", page.status_code == 200)
    # Count real dates: the template's header comment documents the attribute
    # as data-menu-day="<YYYY-MM-DD>", which a bare substring count picks up too
    day_forms = re.findall(r'data-menu-day="\d{4}-\d{2}-\d{2}"', html)
    step("it offers a week of days", len(day_forms) == 7,
         f"days={len(day_forms)}")
    step("today is marked", "menu-day-today" in html)

    admin.save_menu(TODAY, breakfast="Poha, Tea",
                    lunch="Lemon Rice, Rasam", dinner="Chapati, Dal")
    step("saving writes one row", len(BOOK.menu().rows) == 1,
         f"rows={len(BOOK.menu().rows)}")

    student_html = home().get_data(as_text=True)
    step("students see it immediately, without waiting out a cache",
         "Lemon Rice" in student_html and "Poha" in student_html)

    admin.save_menu(TODAY, breakfast="Upma, Tea",
                    lunch="Curd Rice", dinner="Chapati, Dal")
    step("re-saving the same day updates rather than duplicating",
         len(BOOK.menu().rows) == 1, f"rows={len(BOOK.menu().rows)}")

    updated = home().get_data(as_text=True)
    step("the correction reaches students",
         "Upma" in updated and "Lemon Rice" not in updated)

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    admin.save_menu(tomorrow, lunch="Biryani")
    step("a different day appends a new row",
         len(BOOK.menu().rows) == 2, f"rows={len(BOOK.menu().rows)}")

    # The page embeds the whole week's published menus for its day switcher,
    # so the check is on what is rendered for today, not the page source
    rendered_lunch = re.search(r'<ul class="menu-items" id="menu-lunch">.*?</ul>',
                               home().get_data(as_text=True), re.S)
    step("tomorrow's menu does not leak onto today's page",
         rendered_lunch is not None and "Biryani" not in rendered_lunch.group(0)
         and "Curd Rice" in rendered_lunch.group(0),
         rendered_lunch.group(0) if rendered_lunch else "lunch list not found")

    step("a malformed date is refused",
         admin.save_menu("not-a-date", lunch="x").status_code == 400)

    step("the editor requires a CSRF token",
         admin.client.post("/admin/menu/save",
                           data={"date": TODAY, "Lunch": "x"}).status_code == 403)

    # ── Save all 7 days at once ───────────────────────────────────────────
    BOOK.reset()
    start = sheets.week_start(TODAY)
    week_dates = [(datetime.strptime(start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range(7)]
    response = admin.save_week(start, {d: (f"B{i}", f"L{i}", f"D{i}")
                                       for i, d in enumerate(week_dates)})
    step("saving the whole week writes one row per day",
         response.status_code == 200 and len(BOOK.menu().rows) == 7,
         f"status={response.status_code} rows={len(BOOK.menu().rows)}")

    idx = week_dates.index(TODAY)
    step("today's row from the week save reaches students",
         f"L{idx}" in home().get_data(as_text=True))

    response = admin.save_week(start, {TODAY: ("Only today", "", "")})
    step("a week save carrying one day touches only that day",
         len(BOOK.menu().rows) == 7 and
         BOOK.menu().rows[idx][1] == "Only today" and
         sum(1 for r in BOOK.menu().rows if r[2].startswith("L")) == 6,
         f"rows={[r[1] for r in BOOK.menu().rows]}")

    step("a malformed week start is refused",
         admin.save_week("next-week", {TODAY: ("x", "", "")}).status_code == 400)


# ══════════════════════════════════════════════════════════════════════════════
# H5 — Unpublished menus, and the sheet as the other editor
# ══════════════════════════════════════════════════════════════════════════════

def h5_unpublished_and_sheet():
    journey("H5 — An unpublished menu, and edits made in the spreadsheet")
    BOOK.reset()

    html = home().get_data(as_text=True)
    step("an unpublished day says so instead of showing an empty card",
         html.count("Menu not published yet") == 3,
         f"placeholders={html.count('Menu not published yet')}")

    step("students can still react to an unpublished meal",
         rate("Lunch", "bad").status_code == 302 and
         len(BOOK.meal_ratings().rows) == 1)

    # The sheet is the other half of the answer to "where does the menu live"
    BOOK.seed_menu(TODAY, lunch="Sheet-entered Rice, Sheet-entered Dal")
    step("a menu typed straight into the sheet reaches students",
         "Sheet-entered Rice" in home().get_data(as_text=True))

    step("items typed on separate lines split the same as commas",
         sheets._split_items("Rice\nDal\nCurd") == ["Rice", "Dal", "Curd"],
         str(sheets._split_items("Rice\nDal\nCurd")))

    step("stray separators do not produce blank items",
         sheets._split_items("Rice,, Dal , ") == ["Rice", "Dal"],
         str(sheets._split_items("Rice,, Dal , ")))


# ══════════════════════════════════════════════════════════════════════════════
# H6 — Three feedback layers, kept apart
# ══════════════════════════════════════════════════════════════════════════════

def h6_layers_stay_separate():
    journey("H6 — Quick reactions never mix with per-dish or committee scores")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice, Sambar")
    BOOK.seed_member("member@sai.edu", "Committee Member", "password123")
    BOOK.seed_review("member@sai.edu", "Committee Member", TODAY,
                     [5, 5, 5, 5, 5], "Committee verdict")

    rate("Lunch", "bad", "Quick reaction suggestion")
    app.test_client().post("/submit", data={"overall": "3",
                                            "suggestion": "Per-dish suggestion"})

    step("each layer writes to its own tab",
         len(BOOK.meal_ratings().rows) == 1 and
         len(BOOK.responses().rows) == 1 and
         len(BOOK.reviews().rows) == 1,
         f"meal={len(BOOK.meal_ratings().rows)} "
         f"responses={len(BOOK.responses().rows)} "
         f"reviews={len(BOOK.reviews().rows)}")

    student_dash = app.test_client().get("/dashboard?token=vc2026").get_data(as_text=True)
    step("the per-dish dashboard shows its own suggestion",
         "Per-dish suggestion" in student_dash)

    # The student dashboard shows quick taps too, but in their own labelled
    # section. The dish-form suggestion list must not absorb them.
    dish_list = re.search(r"Student Suggestions.*?</div>\s*</div>", student_dash, re.S)
    step("quick reactions stay out of the per-dish suggestion list",
         dish_list is not None
         and "Per-dish suggestion" in dish_list.group(0)
         and "Quick reaction suggestion" not in dish_list.group(0)
         and "Quick reaction suggestion" in student_dash,
         "the two suggestion lists have merged")

    committee_dash = app.test_client().get(
        "/dashboard/committee?token=vc2026").get_data(as_text=True)
    step("the committee dashboard shows only committee reviews",
         "Committee verdict" in committee_dash and
         "Quick reaction suggestion" not in committee_dash)

    step("a bad quick reaction does not drag the per-dish average",
         ">3.0<" in re.sub(r"\s+", "", student_dash),
         "the quick reaction leaked into the 1-5 average")

    step("the home page links students to the detailed form",
         'href="/"' in home().get_data(as_text=True))


# ══════════════════════════════════════════════════════════════════════════════
# H7 — Degraded backend
# ══════════════════════════════════════════════════════════════════════════════

def h7_outage():
    journey("H7 — A Sheets outage leaves the menu page standing")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice")

    BOOK.mode = "raise"
    sheets.invalidate_menu_cache()
    try:
        page = home()
        step("the home page still renders", page.status_code == 200,
             f"status={page.status_code}")
        step("it falls back to the unpublished state rather than erroring",
             "Menu not published yet" in page.get_data(as_text=True))
        step("a reaction during an outage fails without a stack trace",
             rate("Lunch", "good").status_code == 302)
    finally:
        BOOK.mode = "ok"
        sheets.invalidate_menu_cache()

    step("service resumes once the backend recovers",
         "Rice" in home().get_data(as_text=True))


# ══════════════════════════════════════════════════════════════════════════════
# H8 — Rating integrity: one tap per meal, today only, once it is served; Undo
# ══════════════════════════════════════════════════════════════════════════════

def h8_integrity_and_undo():
    journey("H8 — A tap counts once, for today, after the meal is served, and can be undone")
    BOOK.reset()
    BOOK.seed_menu(TODAY, lunch="Rice, Sambar")

    client = app.test_client()
    first = rate("Lunch", "good", client=client)
    step("the confirmation names the reaction as well as the meal",
         "rated=lunch" in first.headers.get("Location", "") and
         "as=good" in first.headers.get("Location", ""),
         first.headers.get("Location", ""))

    page = client.get("/home").get_data(as_text=True)
    step("the lunch card now shows what this device said",
         'data-rated="good"' in page and "You said" in page)
    step("the other two meals still offer their buttons",
         page.count('data-rating="good"') == 2,
         f"good buttons={page.count('data-rating=\"good\"')}")
    step("the banner is announced to assistive tech",
         'id="rated-banner" role="status"' in
         client.get("/home?rated=lunch&as=good").get_data(as_text=True))

    second = rate("Lunch", "bad", client=client)
    step("a second tap on the same meal from the same device is refused",
         "rated=already" in second.headers.get("Location", "") and
         len(BOOK.meal_ratings().rows) == 1,
         f"location={second.headers.get('Location', '')} rows={len(BOOK.meal_ratings().rows)}")

    step("a different device can still rate lunch",
         rate("Lunch", "bad").status_code == 302 and
         len(BOOK.meal_ratings().rows) == 2)

    # Undo removes exactly this device's row and brings the buttons back
    undo = client.post("/home/undo", data={"meal": "Lunch"})
    step("undo is acknowledged",
         "rated=undone" in undo.headers.get("Location", ""),
         undo.headers.get("Location", ""))
    step("undo deletes this device's row and no other",
         len(BOOK.meal_ratings().rows) == 1 and
         BOOK.meal_ratings().rows[0][3] == "bad",
         f"rows={BOOK.meal_ratings().rows}")
    page = client.get("/home").get_data(as_text=True)
    step("after undo the lunch buttons are offered again",
         page.count('data-rating="good"') == 3)
    step("a second undo with nothing to undo is harmless",
         client.post("/home/undo", data={"meal": "Lunch"}).status_code == 302 and
         len(BOOK.meal_ratings().rows) == 1)

    # Only today can be rated: the day switcher shows the week, not a form
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    other = rate("Lunch", "good", client=app.test_client())
    posted = app.test_client().post("/home/rate", data={
        "meal": "Dinner", "rating": "good", "date": tomorrow})
    step("a tap carrying another date is refused",
         "rated=notyet" in posted.headers.get("Location", "") and
         len(BOOK.meal_ratings().rows) == 2,
         posted.headers.get("Location", ""))
    other_day = home(f"?date={tomorrow}").get_data(as_text=True)
    step("another day's page offers no reaction form",
         'class="rate-slot is-other-day"' in other_day and
         "Ratings open on the day itself" in other_day)

    # Serving windows, switched on for this block only
    app.config["ENFORCE_MEAL_WINDOWS"] = True
    try:
        from datetime import datetime as real_datetime
        early = real_datetime.now().replace(hour=6, minute=0)
        late = real_datetime.now().replace(hour=22, minute=0)
        step("before 7:30 nothing is open; by 10 pm every meal is",
             not any(sheets.meal_is_open(m, early) for m in sheets.MEALS) and
             all(sheets.meal_is_open(m, late) for m in sheets.MEALS))
        step("lunch opens at noon exactly",
             sheets.meal_is_open("Lunch", real_datetime.now().replace(hour=12, minute=0)) and
             not sheets.meal_is_open("Lunch", real_datetime.now().replace(hour=11, minute=59)))

        state = app_module._meal_open_state(early)
        step("the page is told which meals are closed and when they open",
             not state["Breakfast"]["open"] and state["Breakfast"]["opens"] == "7:30 am")

        # Whether a live tap is refused depends on the clock; assert the
        # consistent pair: refused ⇔ the page renders that meal's buttons disabled
        now_state = app_module._meal_open_state()
        probe = app.test_client()
        html = probe.get("/home").get_data(as_text=True)
        result = probe.post("/home/rate", data={"meal": "Dinner", "rating": "skip"})
        if now_state["Dinner"]["open"]:
            step("dinner is open now: the tap is stored and its buttons are live",
                 "as=skip" in result.headers.get("Location", "") and
                 'data-rating="skip"\n                                disabled' not in html)
        else:
            step("dinner is not open yet: the tap is refused and its buttons are disabled",
                 "rated=notopen" in result.headers.get("Location", "") and
                 "Dinner opens at 7:30 pm" in html)
    finally:
        app.config["ENFORCE_MEAL_WINDOWS"] = False

    # The daily cap only counts stored taps: refusals are free
    BOOK.reset()
    LIMITER.enabled = True
    try:
        client = app.test_client()
        rate("Lunch", "good", client=client)
        for _ in range(3):
            rate("Lunch", "good", client=client)       # refused: already rated
        codes = [rate("Breakfast", "good", client=client).status_code,
                 rate("Dinner", "good", client=client).status_code]
        step("refused taps do not spend the day's three",
             codes == [302, 302] and len(BOOK.meal_ratings().rows) == 3,
             f"codes={codes} rows={len(BOOK.meal_ratings().rows)}")
        capped = rate("Lunch", "bad", app.test_client())
        step("a fresh device is not capped by another device's taps",
             capped.status_code == 302 and len(BOOK.meal_ratings().rows) == 4)
        client.post("/home/undo", data={"meal": "Lunch"})
        over = rate("Lunch", "bad", client=client)
        step("over the cap, the home page itself answers with the limit banner",
             over.status_code == 429 and
             "used today's three quick ratings" in over.get_data(as_text=True) and
             'data-meal="Lunch"' in over.get_data(as_text=True),
             f"status={over.status_code}")
    finally:
        LIMITER.enabled = False


# ══════════════════════════════════════════════════════════════════════════════
# H9 — The mess's categorised menu, typed or uploaded
# ══════════════════════════════════════════════════════════════════════════════

def h9_categories_and_grid_import():
    journey("H9 — A categorised menu reaches students, by editor or CSV grid")
    BOOK.reset()
    admin = Admin()
    admin.login()

    step("a cell parses into categories and dishes",
         sheets.menu_entries("Main Item: Pongal\nSpread: Butter\nSpread: Jam\nTea")
         == [("Main Item", "Pongal"), ("Spread", "Butter"), ("Spread", "Jam"), ("", "Tea")])
    step("consecutive dishes in one category share a line",
         sheets.menu_groups("Spread: Butter\nSpread: Jam")
         == [{"category": "Spread", "dishes": ["Butter", "Jam"]}])
    step("ratings still key on the bare dish names",
         sheets._split_items("Rice: Steamed Rice, Curd") == ["Steamed Rice", "Curd"])

    admin.save_menu(TODAY, breakfast="Main Item: Pongal\nEgg:\nChutney: Coconut Chutney")
    stored = BOOK.menu().rows[0][1] if BOOK.menu().rows else ""
    step("a template row left blank is not stored",
         stored == "Main Item: Pongal\nChutney: Coconut Chutney", repr(stored))

    breakfast = re.search(r'<ul class="menu-items[^"]*" id="menu-breakfast">.*?</ul>',
                          home().get_data(as_text=True), re.S)
    html = breakfast.group(0) if breakfast else ""
    step("the home card shows each category beside its dish",
         "menu-items-categorised" in html
         and '<span class="menu-cat">Main Item</span>' in html
         and '<span class="menu-dish">Pongal</span>' in html, html[:300])

    # ── The download is the mess's grid ───────────────────────────────────
    start = sheets.week_start(TODAY)
    template = admin.client.get(f"/admin/menu/template.csv?start={start}").get_data(as_text=True)
    lines = template.splitlines()
    step("the template has a column per date and a row per category",
         lines[0].startswith("Meal,Category," + start)
         and "Breakfast,Main Item" in template and "Dinner,Korma" in template
         and len(lines) == 2 + sum(len(c) for c in sheets.MENU_CATEGORIES.values()),
         lines[0])

    # ── Upload a filled grid, the way the mess writes it ──────────────────
    BOOK.reset()
    d1 = datetime.strptime(start, "%Y-%m-%d")
    d2 = d1 + timedelta(days=1)
    grid = "\n".join([
        f"Meal,Category,{d1:%d-%m-%Y},{d2:%d-%m-%Y},Notes",
        ",,Monday,Tuesday,",
        "Breakfast,Main Item,Mix Veg Sevai,Idly,",
        ",Spread,Butter,Butter,",
        ",Spread,Jam,Jam,",
        "Snacks,Tea,Tea,Tea,",
        ",Snack 1,Aloo Samosa,Veg Puff,",
        "Dinner,Rice,\"Mint Pulao, Steamed Rice\",,",
    ])
    token = admin._csrf("/admin/menu")
    response = admin.client.post("/admin/menu/import", data={
        "csrf_token": token, "start": start,
        "file": (io.BytesIO(grid.encode()), "week.csv")},
        content_type="multipart/form-data")
    body = response.get_data(as_text=True)
    rows = {r[0]: r for r in BOOK.menu().rows}
    step("a grid with day-first dates imports both days",
         response.status_code == 200 and set(rows) == {d1.strftime("%Y-%m-%d"),
                                                      d2.strftime("%Y-%m-%d")},
         f"status={response.status_code} rows={list(rows)}")
    first = rows.get(d1.strftime("%Y-%m-%d"), ["", "", "", ""])
    step("categories come from the Category column, the meal carries down",
         first[1] == "Main Item: Mix Veg Sevai\nSpread: Butter\nSpread: Jam"
         and first[3] == "Rice: Mint Pulao\nRice: Steamed Rice", repr(first))
    step("snack rows are skipped, and the admin is told",
         "Snack" not in " ".join(" ".join(r) for r in rows.values())
         and "Skipped Snacks" in body)

    old = "Date,Breakfast,Lunch,Dinner\n" + f'{TODAY},"Idli, Sambar",,\n'
    token = admin._csrf("/admin/menu")
    response = admin.client.post("/admin/menu/import", data={
        "csrf_token": token, "start": start,
        "file": (io.BytesIO(old.encode()), "old.csv")},
        content_type="multipart/form-data")
    step("the older Date/Breakfast/Lunch/Dinner layout still imports",
         response.status_code == 200
         and any(r[0] == TODAY and r[1] == "Idli\nSambar" for r in BOOK.menu().rows),
         str(BOOK.menu().rows))


def report():
    print(f"\n{'=' * 70}\nSTUDENT HOME END-TO-END SUMMARY\n{'=' * 70}")
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
    print("MessMate — student home end-to-end journeys")
    print("(in-memory sheets backend; no Google credentials required)")
    h1_menu_and_reaction()
    h2_tallies()
    h3_validation()
    h4_admin_editor()
    h5_unpublished_and_sheet()
    h6_layers_stay_separate()
    h7_outage()
    h8_integrity_and_undo()
    h9_categories_and_grid_import()
    sys.exit(report())
