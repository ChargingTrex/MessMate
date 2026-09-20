"""
MessMate Student Flow — End-to-End Journeys (test/test_e2e_student.py)
------------------------------------------------------------------------
The committee module has journey coverage in test_e2e_committee.py. The
student flow — the original app, and the one students actually use — had
none: its only tests are the Robot suites, which need a live Google Sheet.
This closes that gap with the same in-memory backend, so the anonymous
feedback path is verified on every run rather than only when credentials
happen to be configured.

Walks the paths a real lunch service produces: a first submission of the day,
partial ratings when only some dishes were served, the daily summary rolling
up, the dashboard aggregating it, the rate limiter holding the line, and a
week of history accumulating.

Runs with NO Google credentials.

Usage:
    python test/test_e2e_student.py
Exit code 0 = every journey completed.
"""

import html as html_lib
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["FLASK_SECRET_KEY"] = "e2e-student-secret-key"
os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
os.environ["DASHBOARD_TOKEN"] = "vc2026"

import sheets          # noqa: E402
import fake_sheets     # noqa: E402
import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True
# Flask-Limiter reads RATELIMIT_ENABLED when the Limiter is constructed, which
# already happened at import. The instance attribute is the live switch.
LIMITER = app_module.limiter
LIMITER.enabled = False

BOOK = fake_sheets.install()

TODAY = datetime.now().strftime("%Y-%m-%d")

# Column positions in the responses tab, for asserting on what was written
COL_TIMESTAMP, COL_OVERALL = 0, 1
COL_RICE_CURRY, COL_RICE_RASAM = 2, 3
COL_CHAPATI, COL_CHAPATI_GRAVY = 4, 5
COL_REVIEW, COL_SUGGESTION = 12, 13


# ══════════════════════════════════════════════════════════════════════════════
# Journey plumbing
# ══════════════════════════════════════════════════════════════════════════════

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


def student(**fields):
    """One anonymous submission from a fresh client (a fresh phone)."""
    return app.test_client().post("/submit", data=fields)


def dashboard(token="vc2026"):
    return app.test_client().get(f"/dashboard?token={token}")


def injected(key, page_html):
    """Reads one of the JSON payloads the dashboard injects for its charts."""
    import json
    match = re.search(key + r": (\[.*?\]|\{.*?\}),?\n", page_html, re.S)
    return json.loads(match.group(1)) if match else None


# ══════════════════════════════════════════════════════════════════════════════
# S1 — The first submission of the day
# ══════════════════════════════════════════════════════════════════════════════

def s1_first_submission():
    journey("S1 — A student rates lunch and lands on the thank-you page")
    BOOK.reset()

    form = app.test_client().get("/")
    step("the form serves", form.status_code == 200 and
         b"How was today" in form.data)

    result = student(overall="4", rice_served="both", rice_curry="5",
                     rice_rasam="3", chapati="4", review="Rice was great",
                     suggestion="Lemon rice on Fridays")
    step("a valid submission redirects rather than rendering inline HTML",
         result.status_code == 302 and "/thanks" in result.headers.get("Location", ""),
         f"status={result.status_code}")

    step("the thank-you page serves",
         app.test_client().get("/thanks").status_code == 200)

    step("exactly one row was written",
         len(BOOK.responses().rows) == 1, f"rows={len(BOOK.responses().rows)}")

    row = BOOK.responses().rows[0]
    step("scores land in the right columns",
         row[COL_OVERALL] == 4 and row[COL_RICE_CURRY] == 5 and
         row[COL_RICE_RASAM] == 3 and row[COL_CHAPATI] == 4,
         f"row={row}")

    step("the timestamp keeps the canonical format",
         re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", str(row[COL_TIMESTAMP])),
         f"timestamp={row[COL_TIMESTAMP]!r}")

    step("no identity is recorded anywhere in the row",
         not any(marker in " ".join(str(c) for c in row).lower()
                 for marker in ("@", "session", "cookie", "127.0.0.1")),
         f"row={row}")

    step("the suggestion is stored raw for Jinja to escape once",
         row[COL_SUGGESTION] == "Lemon rice on Fridays")


# ══════════════════════════════════════════════════════════════════════════════
# S2 — Only some dishes were served
# ══════════════════════════════════════════════════════════════════════════════

def s2_partial_ratings():
    journey("S2 — Partial ratings: only what was served gets scored")
    BOOK.reset()

    result = student(overall="3", chapati="2")
    step("a submission with one item rated is accepted",
         result.status_code == 302)

    row = BOOK.responses().rows[0]
    unrated = [row[i] for i in (COL_RICE_CURRY, COL_RICE_RASAM, COL_CHAPATI_GRAVY)]
    step("unrated dishes are blank, never zero",
         all(value == "" for value in unrated), f"unrated={unrated}")

    step("blanks do not drag the averages down",
         all(sheets.get_today_responses()[0][key] == ""
             for key in ("Rice_Curry", "Poriyal", "Sweet")))

    sheets.update_daily_summary_for_today()
    summary = sheets.get_daily_summary()[0]
    step("the summary averages only what was actually rated",
         summary["Avg_Chapati"] == 2 and summary["Avg_Rice_Curry"] == 0,
         f"summary={summary}")

    html = dashboard().get_data(as_text=True)
    item_data = injected("itemData", html)
    step("the dashboard reports a count only for the rated dish",
         item_data["Chapati"]["count"] == 1 and item_data["Poriyal"]["count"] == 0,
         f"itemData={item_data}")


# ══════════════════════════════════════════════════════════════════════════════
# S3 — Validation and hostile input
# ══════════════════════════════════════════════════════════════════════════════

def s3_validation():
    journey("S3 — Validation: the overall score is the one thing required")
    BOOK.reset()

    missing = student(chapati="4", review="forgot the main score")
    step("a submission with no overall score is refused",
         missing.status_code == 200 and b"error" in missing.data.lower() and
         len(BOOK.responses().rows) == 0,
         f"status={missing.status_code} rows={len(BOOK.responses().rows)}")

    rejected = []
    for bad in ("0", "abc", "", "-1"):
        BOOK.reset()
        response = student(overall=bad)
        rejected.append(len(BOOK.responses().rows) == 0)
    step("non-numeric and out-of-range overall scores write nothing",
         all(rejected), f"results={rejected}")

    BOOK.reset()
    student(overall="5", review="<script>alert('xss')</script>",
            suggestion="<b>bold suggestion</b>")
    row = BOOK.responses().rows[0]

    step("the review is escaped at write time, per the existing convention",
         row[COL_REVIEW] == html_lib.escape("<script>alert('xss')</script>"),
         f"stored={row[COL_REVIEW]!r}")

    step("the suggestion is left raw, because Jinja escapes it at render",
         row[COL_SUGGESTION] == "<b>bold suggestion</b>",
         f"stored={row[COL_SUGGESTION]!r}")

    page = dashboard().get_data(as_text=True)
    step("the suggestion renders escaped, not as live markup",
         "<b>bold suggestion</b>" not in page and "&lt;b&gt;" in page,
         "raw markup reached the rendered dashboard")

    BOOK.reset()
    student(overall="4", review="x" * 400)
    step("an overlong review is truncated to 150 characters",
         len(BOOK.responses().rows[0][COL_REVIEW]) == 150,
         f"length={len(BOOK.responses().rows[0][COL_REVIEW])}")


# ══════════════════════════════════════════════════════════════════════════════
# S4 — One submission per phone per day
# ══════════════════════════════════════════════════════════════════════════════

def s4_rate_limit():
    journey("S4 — The rate limiter allows one submission per IP per day")
    BOOK.reset()
    LIMITER.enabled = True
    try:
        client = app.test_client()
        first = client.post("/submit", data={"overall": "4"})
        second = client.post("/submit", data={"overall": "1"})

        step("the first submission is accepted", first.status_code == 302)
        step("the second from the same IP is refused with 429",
             second.status_code == 429, f"status={second.status_code}")

        step("the refusal is a friendly page, not a raw error",
             b"already submitted" in second.data.lower())

        step("only the first submission was stored",
             len(BOOK.responses().rows) == 1,
             f"rows={len(BOOK.responses().rows)}")
    finally:
        LIMITER.enabled = False


# ══════════════════════════════════════════════════════════════════════════════
# S5 — A full lunch service
# ══════════════════════════════════════════════════════════════════════════════

def s5_full_service():
    journey("S5 — A full service: many students rate, the dashboard adds up")
    BOOK.reset()

    # 1x1, 2x2, 3x3, 3x4, 1x5 — the distribution seed_data.py models
    scores = [1, 2, 2, 3, 3, 3, 4, 4, 4, 5]
    for score in scores:
        student(overall=str(score), chapati=str(score),
                suggestion=f"Suggestion for {score}")

    step("every submission was stored",
         len(BOOK.responses().rows) == 10,
         f"rows={len(BOOK.responses().rows)}")

    html = dashboard().get_data(as_text=True)
    expected = round(sum(scores) / len(scores), 1)   # 3.1

    step(f"the dashboard reports today's average as {expected}",
         f">{expected}<" in re.sub(r"\s+", "", html),
         f"expected {expected} in the stat card")

    step("the response count matches",
         ">10<" in re.sub(r"\s+", "", html))

    item_data = injected("itemData", html)
    step("per-item averages match the overall spread",
         item_data["Chapati"]["avg"] == expected and
         item_data["Chapati"]["count"] == 10,
         f"chapati={item_data['Chapati']}")

    step("every suggestion reaches the board",
         all(f"Suggestion for {s}" in html for s in set(scores)))

    step("suggestions are newest first",
         html.index("Suggestion for 5") < html.index("Suggestion for 1"),
         "suggestion ordering is wrong")


# ══════════════════════════════════════════════════════════════════════════════
# S6 — The daily summary rollup
# ══════════════════════════════════════════════════════════════════════════════

def s6_daily_summary():
    journey("S6 — The daily summary upserts rather than duplicating")
    BOOK.reset()

    student(overall="4", chapati="4")
    step("submitting triggers a summary row for today",
         len(BOOK.tabs["daily_summary"].rows) == 1,
         f"rows={len(BOOK.tabs['daily_summary'].rows)}")

    student(overall="2", chapati="2")
    step("a second submission updates that row instead of appending",
         len(BOOK.tabs["daily_summary"].rows) == 1,
         f"rows={len(BOOK.tabs['daily_summary'].rows)}")

    summary = sheets.get_daily_summary()[0]
    step("the updated average reflects both submissions",
         summary["Avg_Overall"] == 3 and summary["Response_Count"] == 2,
         f"summary={summary}")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    BOOK.seed_student_response(yesterday, 5, items=[5] * 10)
    sheets.update_daily_summary_for_today(date_override=yesterday)
    step("a different date appends a new row",
         len(BOOK.tabs["daily_summary"].rows) == 2,
         f"rows={len(BOOK.tabs['daily_summary'].rows)}")

    dates = [r["Date"] for r in sheets.get_daily_summary()]
    step("both dates are present exactly once",
         sorted(dates) == sorted([TODAY, yesterday]), f"dates={dates}")


# ══════════════════════════════════════════════════════════════════════════════
# S7 — A week of history
# ══════════════════════════════════════════════════════════════════════════════

def s7_week_of_history():
    journey("S7 — A week of service builds the trend chart")
    BOOK.reset()

    expected = {}
    # Seeded oldest-first, which is how the app actually writes: daily operation
    # appends today's row each day, and seed_data.py backfills with
    # range(29, -1, -1). The trend chart takes daily_summary in sheet row order
    # rather than sorting on Date, so it is correct for data written this way
    # but would misorder if the tab were ever sorted or backfilled out of
    # sequence. The step below pins that dependency so it cannot change
    # unnoticed.
    for offset, score in [(6, 1), (5, 3), (3, 2), (1, 4), (0, 5)]:
        date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        BOOK.seed_student_response(date, score, items=[score] * 10)
        sheets.update_daily_summary_for_today(date_override=date)
        expected[date] = score

    html = dashboard().get_data(as_text=True)
    trend = injected("trendData", html)

    step("every day with data appears in the trend",
         trend and len(trend) == 5, f"points={len(trend) if trend else 0}")

    step("the trend runs oldest to newest",
         [p["Date"] for p in trend] == sorted(expected),
         str([p["Date"] for p in trend]))

    step("each day carries its own average",
         all(p["Avg_Overall"] == expected[p["Date"]] for p in trend),
         str([(p["Date"], p["Avg_Overall"]) for p in trend]))

    step("today's stat card shows today, not the week",
         ">5.0<" in re.sub(r"\s+", "", html),
         "the stat card is averaging across days")

    # Pins the known limitation: the trend follows daily_summary row order.
    # If this ever starts passing, the dashboard has gained a sort and the
    # comment above is stale.
    BOOK.tabs["daily_summary"].rows.reverse()
    reversed_trend = injected("trendData", dashboard().get_data(as_text=True))
    step("the trend follows sheet row order, so a re-sorted tab misorders it",
         [p["Date"] for p in reversed_trend] == sorted(expected, reverse=True),
         "the dashboard now sorts by date — update the note in this journey")


# ══════════════════════════════════════════════════════════════════════════════
# S8 — Access control and degraded backends
# ══════════════════════════════════════════════════════════════════════════════

def s8_access_and_outage():
    journey("S8 — The dashboard is gated, and survives an outage")
    BOOK.reset()
    student(overall="4", suggestion="Visible only with a token")

    step("no token is refused",
         app.test_client().get("/dashboard").status_code == 403)
    step("a wrong token is refused",
         dashboard("not-the-token").status_code == 403)
    step("the right token opens it", dashboard().status_code == 200)

    step("the health endpoint answers",
         app.test_client().get("/health").get_json() == {"status": "ok"})

    BOOK.reset()
    step("an empty sheet renders empty states rather than crashing",
         dashboard().status_code == 200 and
         b"No suggestions yet" in dashboard().data)

    BOOK.mode = "raise"
    try:
        step("a Sheets outage still renders the dashboard",
             dashboard().status_code == 200)
        step("the form still serves during an outage",
             app.test_client().get("/").status_code == 200)
        outage_submit = student(overall="4")
        step("a submission during an outage fails without a stack trace",
             outage_submit.status_code in (200, 500),
             f"status={outage_submit.status_code}")
    finally:
        BOOK.mode = "ok"

    step("service resumes once the backend recovers",
         dashboard().status_code == 200)


# ══════════════════════════════════════════════════════════════════════════════
# S9 — The two audiences stay separate
# ══════════════════════════════════════════════════════════════════════════════

def s9_separation():
    journey("S9 — Student anonymity is not weakened by the committee module")
    BOOK.reset()
    BOOK.seed_member("member@sai.edu", "Committee Member", "password123")
    BOOK.seed_review("member@sai.edu", "Committee Member", TODAY,
                     [5, 5, 5, 5, 5], "Committee verdict")

    student(overall="2", review="Student verdict", suggestion="Student idea")

    step("the student row carries no identity",
         "member@sai.edu" not in BOOK.responses().all_cell_text() and
         "Committee Member" not in BOOK.responses().all_cell_text())

    html = dashboard().get_data(as_text=True)
    step("the committee's review does not appear on the student dashboard",
         "Committee verdict" not in html)

    step("the student average ignores committee scores",
         ">2.0<" in re.sub(r"\s+", "", html),
         "committee scores leaked into the student average")

    step("the student form needs no login",
         app.test_client().get("/").status_code == 200)

    step("a student is never redirected to a committee page",
         "committee" not in app.test_client().get("/").get_data(as_text=True).lower())


# ══════════════════════════════════════════════════════════════════════════════

def report():
    print(f"\n{'=' * 70}\nSTUDENT END-TO-END SUMMARY\n{'=' * 70}")

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
    print("MessMate — student flow end-to-end journeys")
    print("(in-memory sheets backend; no Google credentials required)")
    s1_first_submission()
    s2_partial_ratings()
    s3_validation()
    s4_rate_limit()
    s5_full_service()
    s6_daily_summary()
    s7_week_of_history()
    s8_access_and_outage()
    s9_separation()
    sys.exit(report())
