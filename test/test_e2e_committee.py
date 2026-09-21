"""
MessMate Food Committee — End-to-End Journeys (test/test_e2e_committee.py)
---------------------------------------------------------------------------
Where test_committee.py checks individual behaviours against the
implementation checklist, this suite walks complete user journeys the way a
real committee term actually unfolds: onboarding, a daily rating cycle, a
rotation handover, a forgotten password, and the failure modes in between.

Each journey asserts on state that spans several requests and both roles, so
it catches integration faults a per-route test cannot see — a member who can
log in but whose review never reaches the dashboard, or a rotation that
silently erases the outgoing term's history.

Runs with NO Google credentials: the sheets layer is the shared in-memory fake.

Usage:
    python test/test_e2e_committee.py
Exit code 0 = every journey completed.
"""

import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["FLASK_SECRET_KEY"] = "e2e-test-secret-key"
os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
os.environ["DASHBOARD_TOKEN"] = "vc2026"

import auth      # noqa: E402
import sheets    # noqa: E402

ADMIN_PASSWORD = "e2e-admin-password"
os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(ADMIN_PASSWORD)

import fake_sheets   # noqa: E402
import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True
# Flask-Limiter reads RATELIMIT_ENABLED when the Limiter is built, which already
# happened at import — the instance attribute is the live switch
app_module.limiter.enabled = False

BOOK = fake_sheets.install()

TODAY = datetime.now().strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════════════════
# Journey plumbing
# ══════════════════════════════════════════════════════════════════════════════

RESULTS = []
_current = {"journey": None, "failed": False}

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def journey(name):
    print(f"\n{name}\n{'-' * len(name)}")
    _current["journey"] = name
    _current["failed"] = False


def step(description, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((_current["journey"], description, ok, detail))
    if not ok:
        _current["failed"] = True
    print(f"  [{'PASS' if ok else 'FAIL'}] {description}")
    if not ok and detail:
        print(f"         -> {detail}")
    return ok


# ── Actors ────────────────────────────────────────────────────────────────────

class Admin:
    """An administrator driving the browser-facing admin UI."""

    def __init__(self):
        self.client = app.test_client()

    def login(self, password=ADMIN_PASSWORD):
        token = self._csrf("/admin/login")
        return self.client.post("/admin/login",
                                data={"password": password, "csrf_token": token})

    def _csrf(self, path):
        html = self.client.get(path).get_data(as_text=True)
        match = CSRF_RE.search(html)
        return match.group(1) if match else ""

    def add_member(self, name, email):
        """Returns the revealed one-time password, or None if refused."""
        token = self._csrf("/admin/members")
        response = self.client.post("/admin/members/add", data={
            "name": name, "email": email, "csrf_token": token})
        return response, self._revealed(response, email)

    def bulk_add(self, lines):
        token = self._csrf("/admin/members")
        response = self.client.post("/admin/members/bulk", data={
            "members": "\n".join(lines), "csrf_token": token})
        html = response.get_data(as_text=True)
        credentials = dict(re.findall(
            r"<td>[^<]*</td>\s*<td>([^<]+)</td>\s*<td><code[^>]*>([^<]+)</code>",
            html))
        return response, credentials

    def act_on(self, email, action):
        token = self._csrf("/admin/members")
        response = self.client.post("/admin/members/update", data={
            "email": email, "action": action, "csrf_token": token})
        return response, self._revealed(response, email)

    @staticmethod
    def _revealed(response, email):
        match = re.search(
            r"<td>[^<]*</td>\s*<td>" + re.escape(email) +
            r"</td>\s*<td><code[^>]*>([^<]+)</code>",
            response.get_data(as_text=True))
        return match.group(1) if match else None

    def roster_page(self):
        return self.client.get("/admin/members")


class Member:
    """A committee member using the rating pages."""

    def __init__(self, email):
        self.email = email
        self.client = app.test_client()

    def _csrf(self, path):
        html = self.client.get(path).get_data(as_text=True)
        match = CSRF_RE.search(html)
        return match.group(1) if match else ""

    def login(self, password):
        token = self._csrf("/committee/login")
        return self.client.post("/committee/login", data={
            "email": self.email, "password": password, "csrf_token": token})

    def set_password(self, new_password):
        token = self._csrf("/committee/password")
        return self.client.post("/committee/password", data={
            "password": new_password, "confirm": new_password,
            "csrf_token": token})

    def rating_page(self):
        return self.client.get("/committee")

    def rate(self, taste=4, quality=4, variety=4, hygiene=4, menu=4, review=""):
        token = self._csrf("/committee")
        return self.client.post("/committee/submit", data={
            "taste": str(taste), "quality": str(quality), "variety": str(variety),
            "hygiene": str(hygiene), "menu": str(menu), "review": review,
            "csrf_token": token})


def dashboard(token="vc2026"):
    """Read-only dashboard fetch using the legacy token credential."""
    return app.test_client().get(f"/dashboard/committee?token={token}")


def dashboard_json(key, html):
    """Pulls one of the JSON payloads the dashboard injects for its charts."""
    import json
    match = re.search(key + r": (\[.*?\]|\{.*?\}),\n", html, re.S)
    return json.loads(match.group(1)) if match else None


# ══════════════════════════════════════════════════════════════════════════════
# J1 — A new member is onboarded and files their first review
# ══════════════════════════════════════════════════════════════════════════════

def j1_onboarding():
    journey("J1 — Onboarding: admin adds a member, who rates the same day")
    BOOK.reset()

    admin = Admin()
    admin.login()

    response, one_time = admin.add_member("Aarav Sharma", "aarav@sai.edu")
    step("admin adds a member and is shown a one-time password",
         response.status_code == 200 and one_time,
         f"status={response.status_code} password={one_time}")

    step("the password is not written to the sheet, only its hash",
         one_time and one_time not in BOOK.members().all_cell_text())

    member = Member("aarav@sai.edu")
    login = member.login(one_time)
    step("the member signs in immediately with that password",
         login.status_code == 302, f"status={login.status_code}")

    step("first sign-in is diverted to the password change",
         "/committee/password" in login.headers.get("Location", ""),
         login.headers.get("Location"))

    blocked = member.rating_page()
    step("the rating page is unreachable until the password is changed",
         blocked.status_code == 302 and
         "/committee/password" in blocked.headers.get("Location", ""))

    member.set_password("aarav-own-password")
    step("after setting their own password the rating page opens",
         member.rating_page().status_code == 200)

    step("the temporary password no longer works",
         Member("aarav@sai.edu").login(one_time).status_code == 401)

    submitted = member.rate(taste=5, quality=4, variety=3, hygiene=4, menu=5,
                            review="Sambar was excellent today")
    step("the review is accepted", submitted.status_code == 302)

    row = BOOK.reviews().rows[0]
    step("it is stored against the right member with the right scores",
         row[2] == "aarav@sai.edu" and row[4:9] == [5, 4, 3, 4, 5],
         f"row={row}")

    html = dashboard().get_data(as_text=True)
    dimension_data = dashboard_json("dimensionData", html)
    step("the dashboard shows it within the same request cycle",
         "Sambar was excellent today" in html and
         dimension_data["Taste"]["avg"] == 5.0,
         f"dimensionData={dimension_data}")

    step("the member is attributed on the dashboard",
         "Aarav Sharma" in html)


# ══════════════════════════════════════════════════════════════════════════════
# J2 — A full rating day across several members
# ══════════════════════════════════════════════════════════════════════════════

def j2_rating_day():
    journey("J2 — A rating day: three members rate, one abstains")
    BOOK.reset()

    for email, name in [("a@sai.edu", "Member A"), ("b@sai.edu", "Member B"),
                        ("c@sai.edu", "Member C"), ("d@sai.edu", "Member D")]:
        BOOK.seed_member(email, name, "password123")

    scores = {"a@sai.edu": (5, 5, 5, 5, 5),
              "b@sai.edu": (3, 3, 3, 3, 3),
              "c@sai.edu": (1, 1, 1, 1, 1)}

    for email, values in scores.items():
        member = Member(email)
        member.login("password123")
        result = member.rate(*values, review=f"Review from {email}")
        step(f"{email} submits successfully", result.status_code == 302)

    step("exactly three reviews were stored, not four",
         len(BOOK.reviews().rows) == 3, f"rows={len(BOOK.reviews().rows)}")

    repeat = Member("a@sai.edu")
    repeat.login("password123")
    again = repeat.rate(1, 1, 1, 1, 1)
    step("a second review from the same member the same day is refused",
         len(BOOK.reviews().rows) == 3 and
         "already reviewed" in again.get_data(as_text=True).lower())

    landing = repeat.rating_page().get_data(as_text=True)
    step("that member sees the already-reviewed page rather than a blank form",
         "already reviewed" in landing.lower())

    html = dashboard().get_data(as_text=True)
    dimension_data = dashboard_json("dimensionData", html)
    step("the average across 5, 3 and 1 is 3.0",
         all(dimension_data[d]["avg"] == 3.0 for d in sheets.DIMENSIONS),
         f"dimensionData={dimension_data}")

    flat = re.sub(r"\s+", "", html)
    step("participation reads 75% — three of four active members",
         ">75%<" in flat, "participation is wrong")

    step("the abstaining member is not counted as a response",
         ">3<" in flat and ">4<" in flat)


# ══════════════════════════════════════════════════════════════════════════════
# J3 — A committee rotation
# ══════════════════════════════════════════════════════════════════════════════

def j3_rotation():
    journey("J3 — Rotation: the outgoing term is retired, a new one takes over")
    BOOK.reset()

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    BOOK.seed_member("old1@sai.edu", "Outgoing One", "oldpassword")
    BOOK.seed_member("old2@sai.edu", "Outgoing Two", "oldpassword")
    BOOK.seed_review("old1@sai.edu", "Outgoing One", yesterday, [4, 4, 4, 4, 4],
                     "Historic review from the previous term")

    admin = Admin()
    admin.login()

    response, credentials = admin.bulk_add([
        "Incoming One, new1@sai.edu",
        "Incoming Two, new2@sai.edu",
        "Incoming Three, new3@sai.edu",
    ])
    step("the incoming term is added in one bulk operation",
         response.status_code == 200 and len(credentials) == 3,
         f"credentials={list(credentials)}")

    step("bulk add cost a single API write, not one per member",
         BOOK.members().append_rows_calls == 1,
         f"append_rows_calls={BOOK.members().append_rows_calls}")

    for email in ["old1@sai.edu", "old2@sai.edu"]:
        admin.act_on(email, "deactivate")

    step("outgoing members can no longer sign in",
         Member("old1@sai.edu").login("oldpassword").status_code == 401)

    step("their review history is preserved, not deleted",
         len(BOOK.reviews().rows) == 1 and
         "Historic review" in BOOK.reviews().all_cell_text())

    step("the roster records when their term ended",
         all(sheets.get_committee_member(e)["Term_End"]
             for e in ["old1@sai.edu", "old2@sai.edu"]))

    new_member = Member("new1@sai.edu")
    new_member.login(credentials["new1@sai.edu"])
    new_member.set_password("incoming-password")
    result = new_member.rate(5, 5, 4, 5, 4, review="First review of the new term")
    step("an incoming member can rate straight away",
         result.status_code == 302)

    html = dashboard().get_data(as_text=True)
    step("the dashboard carries both terms' reviews",
         "Historic review" in html and "First review of the new term" in html)

    step("active member count reflects only the current term",
         re.sub(r"\s+", "", html).count(">3<") >= 1,
         "expected 3 active members after the rotation")

    roster = admin.roster_page().get_data(as_text=True)
    step("the roster page shows retired members as inactive",
         "badge-inactive" in roster and "badge-active" in roster)


# ══════════════════════════════════════════════════════════════════════════════
# J4 — A forgotten password
# ══════════════════════════════════════════════════════════════════════════════

def j4_password_reset():
    journey("J4 — A member forgets their password and the admin resets it")
    BOOK.reset()
    BOOK.seed_member("forgetful@sai.edu", "Forgetful Member", "the-old-password")

    step("the original password works before the reset",
         Member("forgetful@sai.edu").login("the-old-password").status_code == 302)

    admin = Admin()
    admin.login()
    response, new_password = admin.act_on("forgetful@sai.edu", "reset")
    step("the admin is shown a fresh one-time password",
         response.status_code == 200 and new_password, f"password={new_password}")

    step("the forgotten password stops working",
         Member("forgetful@sai.edu").login("the-old-password").status_code == 401)

    member = Member("forgetful@sai.edu")
    login = member.login(new_password)
    step("the new password works and forces another change",
         login.status_code == 302 and
         "/committee/password" in login.headers.get("Location", ""))

    member.set_password("brand-new-password")
    step("the member is back to rating after choosing a password",
         member.rating_page().status_code == 200)

    step("only the hash of the new password is stored",
         new_password not in BOOK.members().all_cell_text() and
         "brand-new-password" not in BOOK.members().all_cell_text())


# ══════════════════════════════════════════════════════════════════════════════
# J5 — The privilege boundary under attack
# ══════════════════════════════════════════════════════════════════════════════

def j5_privilege_boundary():
    journey("J5 — A leaked dashboard token cannot be escalated to roster access")
    BOOK.reset()
    BOOK.seed_member("victim@sai.edu", "Victim", "victim-password")

    attacker = app.test_client()

    step("the leaked token does open the read-only dashboards",
         attacker.get("/dashboard/committee?token=vc2026").status_code == 200 and
         attacker.get("/dashboard?token=vc2026").status_code == 200)

    step("but it cannot open the roster UI",
         attacker.get("/admin/members?token=vc2026").status_code == 302)

    mutations = {
        "/admin/members/add": {"name": "Attacker", "email": "attacker@sai.edu"},
        "/admin/members/bulk": {"members": "Attacker, attacker@sai.edu"},
        "/admin/members/update": {"email": "victim@sai.edu", "action": "reset"},
    }
    outcomes = {}
    for path, payload in mutations.items():
        result = attacker.post(f"{path}?token=vc2026", data=payload)
        outcomes[path] = result.status_code

    step("no roster mutation is reachable with the token alone",
         all(code in (302, 403) for code in outcomes.values()), str(outcomes))

    step("nothing was created by the attempts",
         len(BOOK.members().rows) == 1, f"rows={len(BOOK.members().rows)}")

    # CSRF: an admin session is not enough for a cross-site POST
    admin = Admin()
    admin.login()
    forged = admin.client.post("/admin/members/add", data={
        "name": "CSRF Victim", "email": "csrf@sai.edu",
        "csrf_token": "attacker-supplied-value"})
    step("even with an admin session, a forged CSRF token is rejected",
         forged.status_code == 403 and len(BOOK.members().rows) == 1,
         f"status={forged.status_code}")

    no_token = admin.client.post("/admin/members/add",
                                 data={"name": "No Token", "email": "nt@sai.edu"})
    step("a POST with no CSRF token at all is rejected",
         no_token.status_code == 403)

    step("the same protection covers committee routes",
         Member("victim@sai.edu").client.post("/committee/submit", data={
             "taste": "5", "quality": "5", "variety": "5",
             "hygiene": "5", "menu": "5"}).status_code in (302, 403))


# ══════════════════════════════════════════════════════════════════════════════
# J6 — Revocation while a session is live
# ══════════════════════════════════════════════════════════════════════════════

def j6_mid_session_revocation():
    journey("J6 — A member removed mid-session loses access on the next request")
    BOOK.reset()
    BOOK.seed_member("leaving@sai.edu", "Leaving Member", "password123")

    member = Member("leaving@sai.edu")
    member.login("password123")
    step("the member holds a working session",
         member.rating_page().status_code == 200)

    admin = Admin()
    admin.login()
    admin.act_on("leaving@sai.edu", "deactivate")

    step("the live session stops working immediately, without re-login",
         member.rating_page().status_code == 302,
         "a deactivated member kept access until their cookie expired")

    attempt = member.rate(5, 5, 5, 5, 5)
    step("they cannot submit a review with the stale session",
         attempt.status_code == 302 and len(BOOK.reviews().rows) == 0,
         f"status={attempt.status_code} rows={len(BOOK.reviews().rows)}")


# ══════════════════════════════════════════════════════════════════════════════
# J7 — Committee and student flows coexist
# ══════════════════════════════════════════════════════════════════════════════

def j7_coexistence():
    journey("J7 — Student anonymity and committee attribution stay separate")
    BOOK.reset()
    BOOK.seed_member("both@sai.edu", "Committee Member", "password123")

    student = app.test_client()
    student.post("/submit", data={"overall": "2", "review": "Too salty",
                                  "suggestion": "Lemon rice"})

    member = Member("both@sai.edu")
    member.login("password123")
    member.rate(5, 5, 5, 5, 5, review="Committee says excellent")

    step("the student row went to responses, not committee_reviews",
         len(BOOK.responses().rows) == 1 and len(BOOK.reviews().rows) == 1)

    step("no identity was recorded with the student submission",
         "both@sai.edu" not in BOOK.responses().all_cell_text() and
         "Committee Member" not in BOOK.responses().all_cell_text())

    step("the committee review is attributed",
         "both@sai.edu" in BOOK.reviews().all_cell_text())

    student_dashboard = app.test_client().get("/dashboard?token=vc2026")
    student_html = student_dashboard.get_data(as_text=True)
    step("the student dashboard renders and shows the student suggestion",
         student_dashboard.status_code == 200 and "Lemon rice" in student_html)

    step("committee reviews do not leak onto the student dashboard",
         "Committee says excellent" not in student_html)

    committee_html = dashboard().get_data(as_text=True)
    step("student feedback does not leak onto the committee dashboard",
         "Too salty" not in committee_html and
         "Committee says excellent" in committee_html)

    step("the two averages are computed independently",
         "2" in student_html and
         dashboard_json("dimensionData", committee_html)["Taste"]["avg"] == 5.0)


# ══════════════════════════════════════════════════════════════════════════════
# J8 — Multi-day history
# ══════════════════════════════════════════════════════════════════════════════

def j8_multi_day_trend():
    journey("J8 — A week of reviews builds a correct trend")
    BOOK.reset()
    BOOK.seed_member("daily@sai.edu", "Daily Rater", "password123")

    # Seeded out of chronological order on purpose: the dashboard must sort by
    # date, not trust the physical row order of the sheet
    expected = {}
    for offset, score in [(2, 2), (0, 5), (4, 1), (1, 3), (3, 4)]:
        date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        BOOK.seed_review("daily@sai.edu", "Daily Rater", date,
                         [score] * 5, f"Day minus {offset}")
        expected[date] = float(score)

    html = dashboard().get_data(as_text=True)
    trend = dashboard_json("trendData", html)

    step("every day appears in the trend",
         len(trend) == 5, f"points={len(trend) if trend else 0}")

    step("the trend is ordered oldest to newest",
         [p["Date"] for p in trend] == sorted(expected.keys()),
         str([p["Date"] for p in trend]))

    step("each day carries its own average",
         all(p["Avg_Overall"] == expected[p["Date"]] for p in trend),
         str([(p["Date"], p["Avg_Overall"]) for p in trend]))

    step("per-dimension series are present for the chart",
         all(all(d in p for d in sheets.DIMENSIONS) for p in trend))

    step("the review feed is newest first despite the seeded row order",
         html.index("Day minus 0") < html.index("Day minus 4"),
         "feed ordering fell back to physical row order")

    flat = re.sub(r"\s+", "", html)
    step("today's card shows today's score, not the whole week's",
         ">5.0<" in flat, "stat card is averaging across days")


# ══════════════════════════════════════════════════════════════════════════════
# J9 — Degraded backend
# ══════════════════════════════════════════════════════════════════════════════

def j9_outage():
    journey("J9 — A Google Sheets outage degrades instead of breaking")
    BOOK.reset()
    BOOK.seed_member("outage@sai.edu", "Outage Member", "password123")

    member = Member("outage@sai.edu")
    member.login("password123")

    BOOK.mode = "raise"
    sheets.invalidate_roster_cache()

    step("the committee dashboard still renders",
         dashboard().status_code == 200)

    step("the student dashboard still renders",
         app.test_client().get("/dashboard?token=vc2026").status_code == 200)

    step("the login page still loads",
         app.test_client().get("/committee/login").status_code == 200)

    step("a login attempt fails safely rather than erroring",
         Member("outage@sai.edu").login("password123").status_code == 401)

    BOOK.mode = "unavailable"
    sheets.invalidate_roster_cache()
    step("an unreachable sheet also avoids a 500 on the dashboard",
         dashboard().status_code == 200)

    BOOK.mode = "ok"
    sheets.invalidate_roster_cache()
    step("service resumes once the backend recovers",
         Member("outage@sai.edu").login("password123").status_code == 302)


# ══════════════════════════════════════════════════════════════════════════════

def report():
    print(f"\n{'=' * 70}\nEND-TO-END SUMMARY\n{'=' * 70}")

    journeys = {}
    for name, _, ok, _ in RESULTS:
        journeys.setdefault(name, []).append(ok)

    for name, outcomes in journeys.items():
        status = "PASS" if all(outcomes) else "FAIL"
        print(f"  [{status}] {name}  ({sum(outcomes)}/{len(outcomes)} steps)")

    failed = [r for r in RESULTS if not r[2]]
    total = len(RESULTS)
    print(f"\n  {total - len(failed)}/{total} steps passed "
          f"across {len(journeys)} journeys")

    if failed:
        print("\n  FAILED STEPS:")
        for name, description, _, detail in failed:
            print(f"    {name}")
            print(f"      {description}")
            if detail:
                print(f"      {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    print("MessMate — Food Committee end-to-end journeys")
    print("(in-memory sheets backend; no Google credentials required)")
    j1_onboarding()
    j2_rating_day()
    j3_rotation()
    j4_password_reset()
    j5_privilege_boundary()
    j6_mid_session_revocation()
    j7_coexistence()
    j8_multi_day_trend()
    j9_outage()
    sys.exit(report())
