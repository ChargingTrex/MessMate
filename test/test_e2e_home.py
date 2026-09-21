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
    journey("H3 — Bad input is refused, and one IP gets three taps a day")
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

    # Three meals a day, so three taps a day
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

    step("tomorrow's menu does not leak onto today's page",
         "Biryani" not in home().get_data(as_text=True))

    step("a malformed date is refused",
         admin.save_menu("not-a-date", lunch="x").status_code == 400)

    step("the editor requires a CSRF token",
         admin.client.post("/admin/menu/save",
                           data={"date": TODAY, "Lunch": "x"}).status_code == 403)


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
    step("quick reactions do not appear on the per-dish dashboard",
         "Quick reaction suggestion" not in student_dash)

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
    sys.exit(report())
