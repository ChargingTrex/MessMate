"""
MessMate Food Committee Verification Harness (test/test_committee.py)
----------------------------------------------------------------------
Verifies every AUTO item in docs/FoodCommittee_Checklist.md.

Runs with NO Google credentials: sheets.get_sheet() is replaced with an
in-memory fake worksheet, so all of sheets.py's real logic — the roster cache,
row construction, col_values lookup, update_cell, get_all_records — is
genuinely exercised, and the routes are driven through Flask's test client.

Usage:
    python test/test_committee.py
Exit code 0 = all checks passed.
"""

import os
import re
import sys

# Import the app package from the repo root regardless of where this is run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set before importing app — it raises at import time without a secret
os.environ["FLASK_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
os.environ["DASHBOARD_TOKEN"] = "vc2026"

import auth  # noqa: E402
import sheets  # noqa: E402

ADMIN_PASSWORD = "admin-test-password"
os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(ADMIN_PASSWORD)

import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True
# Rate limits are exercised deliberately in one test; off elsewhere so the
# suite does not exhaust them.
# NOTE: setting app.config["RATELIMIT_ENABLED"] here does nothing — Flask-Limiter
# reads that key when the Limiter is constructed, which already happened at
# import. The live switch is the instance attribute.
LIMITER = app_module.limiter
LIMITER.enabled = False


# ══════════════════════════════════════════════════════════════════════════════
# In-memory fake of the gspread worksheet API
# ══════════════════════════════════════════════════════════════════════════════

class FakeWorksheet:
    """Implements only the gspread surface sheets.py actually uses."""

    def __init__(self, headers):
        self.headers = list(headers)
        self.rows = []              # list of lists, excluding the header row
        self.read_count = 0         # proves the roster TTL cache works
        self.append_row_calls = 0
        self.append_rows_calls = 0

    def get_all_records(self):
        self.read_count += 1
        return [dict(zip(self.headers, row)) for row in self.rows]

    def append_row(self, row, value_input_option=None):
        self.append_row_calls += 1
        self.rows.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.append_rows_calls += 1
        for row in rows:
            self.rows.append(list(row))

    def col_values(self, index):
        # gspread is 1-indexed and includes the header cell
        values = [self.headers[index - 1]]
        for row in self.rows:
            values.append(row[index - 1] if index - 1 < len(row) else "")
        return values

    def update_cell(self, row_index, col_index, value):
        # row_index 1 is the header, so data starts at 2
        self.rows[row_index - 2][col_index - 1] = value

    def update(self, cell_range, values):
        pass  # used only by the student daily-summary path

    def all_cell_text(self):
        """Every stored value as one string — used to prove no plaintext leaks."""
        return " ".join(str(cell) for row in self.rows for cell in row)


class FakeBook:
    """Registry of tab name -> FakeWorksheet, standing in for the spreadsheet."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.tabs = {
            sheets.COMMITTEE_MEMBERS_TAB: FakeWorksheet(sheets.MEMBER_HEADERS),
            sheets.COMMITTEE_REVIEWS_TAB: FakeWorksheet(sheets.REVIEW_HEADERS),
            "responses": FakeWorksheet([
                "Timestamp", "Overall", "Rice_Curry", "Rice_Rasam", "Chapati",
                "Chapati_Gravy", "Poriyal", "Sweet", "Salad", "Curd", "Papad",
                "Pickle", "Review", "Suggestion"]),
            "daily_summary": FakeWorksheet([
                "Date", "Avg_Overall", "Response_Count", "Avg_Rice_Curry",
                "Avg_Rice_Rasam", "Avg_Chapati", "Avg_Chapati_Gravy",
                "Avg_Poriyal", "Avg_Sweet", "Avg_Salad", "Avg_Curd",
                "Avg_Papad", "Avg_Pickle"]),
        }
        self.mode = "ok"  # "ok" | "unavailable" (returns None) | "raise"
        sheets.invalidate_roster_cache()

    def get_sheet(self, tab_name):
        if self.mode == "raise":
            raise RuntimeError("simulated Google Sheets outage")
        if self.mode == "unavailable":
            return None
        return self.tabs.get(tab_name)

    def members(self):
        return self.tabs[sheets.COMMITTEE_MEMBERS_TAB]

    def reviews(self):
        return self.tabs[sheets.COMMITTEE_REVIEWS_TAB]


BOOK = FakeBook()
sheets.get_sheet = BOOK.get_sheet


# ══════════════════════════════════════════════════════════════════════════════
# Assertion plumbing
# ══════════════════════════════════════════════════════════════════════════════

RESULTS = []


def check(item_id, description, condition, detail=""):
    RESULTS.append((item_id, description, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {item_id}  {description}"
    if not condition and detail:
        line += f"\n         -> {detail}"
    print(line)


def section(title):
    print(f"\n{title}\n{'-' * len(title)}")


CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf_token(client, path):
    """Pulls the CSRF token out of a rendered form."""
    html = client.get(path).get_data(as_text=True)
    match = CSRF_RE.search(html)
    return match.group(1) if match else ""


def login_member(client, email, password):
    token = csrf_token(client, "/committee/login")
    return client.post("/committee/login", data={
        "email": email, "password": password, "csrf_token": token
    }, follow_redirects=False)


def login_admin(client):
    token = csrf_token(client, "/admin/login")
    return client.post("/admin/login", data={
        "password": ADMIN_PASSWORD, "csrf_token": token
    }, follow_redirects=False)


def add_member_via_ui(client, name, email):
    token = csrf_token(client, "/admin/members")
    return client.post("/admin/members/add", data={
        "name": name, "email": email, "csrf_token": token
    })


def extract_password(html, email):
    """Reads a revealed one-time password out of the credential banner."""
    row = re.search(
        r"<td>[^<]*</td>\s*<td>" + re.escape(email) +
        r"</td>\s*<td><code[^>]*>([^<]+)</code>", html)
    return row.group(1) if row else None


def seed_member(email, name, password, active=True, must_change=False):
    """Writes a member straight into the fake sheet, bypassing the UI."""
    BOOK.members().rows.append([
        email, name, auth.hash_password(password),
        "TRUE" if active else "FALSE",
        "TRUE" if must_change else "FALSE",
        "2026-01-01", "", "2026-01-01 09:00:00"
    ])
    sheets.invalidate_roster_cache()


def seed_review(email, name, date, scores, review=""):
    BOOK.reviews().rows.append(
        [f"{date} 13:00:00", date, email, name] + list(scores) + [review])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 0 — Data layer
# ══════════════════════════════════════════════════════════════════════════════

def phase_0():
    section("PHASE 0 — Data layer & tooling")
    BOOK.reset()

    check("P0-1", "committee_members headers match the plan",
          sheets.MEMBER_HEADERS == ["Email", "Name", "Password_Hash", "Active",
                                    "Must_Change_Password", "Term_Start",
                                    "Term_End", "Created_At"],
          str(sheets.MEMBER_HEADERS))

    check("P0-2", "committee_reviews headers match the plan",
          sheets.REVIEW_HEADERS == ["Timestamp", "Date", "Member_Email",
                                    "Member_Name", "Taste", "Quality",
                                    "Variety", "Hygiene", "Menu", "Review"],
          str(sheets.REVIEW_HEADERS))

    check("P0-3", "Email is column A (row lookup depends on it)",
          sheets.MEMBER_HEADERS[0] == "Email")

    # TTL cache
    seed_member("cache@sai.edu", "Cache Test", "pw12345678")
    sheets.invalidate_roster_cache()
    before = BOOK.members().read_count
    sheets.get_committee_roster()
    sheets.get_committee_roster()
    sheets.get_committee_roster()
    check("P0-4", "roster read is cached (3 calls -> 1 sheet read)",
          BOOK.members().read_count - before == 1,
          f"reads={BOOK.members().read_count - before}")

    before = BOOK.members().read_count
    sheets.add_committee_member("invalidate@sai.edu", "Inv", "hash")
    sheets.get_committee_roster()
    check("P0-5", "a write invalidates the cache",
          BOOK.members().read_count - before == 1,
          "cache was not invalidated by the write")

    # Failure posture
    BOOK.mode = "unavailable"
    sheets.invalidate_roster_cache()
    try:
        outcomes = [
            sheets.get_committee_roster() == [],
            sheets.get_committee_member("x@sai.edu") is None,
            sheets.add_committee_member("a@b.co", "N", "h") is False,
            sheets.add_committee_members_bulk([("a@b.co", "N", "h")]) is False,
            sheets.update_committee_member("a@b.co", Active="FALSE") is False,
            sheets.append_committee_review({"Member_Email": "a@b.co"}) is False,
            sheets.get_committee_reviews() == [],
            sheets.has_submitted_today("a@b.co") is False,
        ]
        check("P0-6", "all functions degrade safely when Sheets is unreachable",
              all(outcomes), f"outcomes={outcomes}")
    except Exception as e:
        check("P0-6", "all functions degrade safely when Sheets is unreachable",
              False, f"raised {type(e).__name__}: {e}")
    BOOK.mode = "ok"


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Auth core
# ══════════════════════════════════════════════════════════════════════════════

def phase_1():
    section("PHASE 1 — Auth core")
    BOOK.reset()
    seed_member("member@sai.edu", "Test Member", "goodpassword")
    seed_member("gone@sai.edu", "Former Member", "goodpassword", active=False)

    with app.test_client() as client:
        response = login_member(client, "member@sai.edu", "goodpassword")
        check("P1-1", "valid login redirects to /committee",
              response.status_code == 302 and "/committee" in response.headers.get("Location", ""),
              f"status={response.status_code} loc={response.headers.get('Location')}")

    with app.test_client() as client:
        response = login_member(client, "member@sai.edu", "wrongpassword")
        html = response.get_data(as_text=True)
        check("P1-2", "wrong password shows the error banner, no session",
              response.status_code == 401 and "error-banner" in html)

    with app.test_client() as client:
        unknown = login_member(client, "nobody@sai.edu", "whatever").get_data(as_text=True)
    with app.test_client() as client:
        wrong = login_member(client, "member@sai.edu", "wrongpassword").get_data(as_text=True)
    # Each client carries its own CSRF token, so compare with it stripped
    strip_csrf = lambda h: CSRF_RE.sub("", h)
    check("P1-3", "unknown email is indistinguishable from a wrong password",
          strip_csrf(unknown) == strip_csrf(wrong),
          "responses differ — user enumeration is possible")

    with app.test_client() as client:
        response = login_member(client, "gone@sai.edu", "goodpassword")
        check("P1-4", "deactivated member cannot log in",
              response.status_code == 401)

    # Deactivated mid-session
    with app.test_client() as client:
        login_member(client, "member@sai.edu", "goodpassword")
        sheets.update_committee_member("member@sai.edu", Active="FALSE")
        response = client.get("/committee")
        check("P1-5", "member deactivated mid-session loses access immediately",
              response.status_code == 302 and "login" in response.headers.get("Location", ""),
              f"status={response.status_code}")
        sheets.update_committee_member("member@sai.edu", Active="TRUE")

    with app.test_client() as client:
        response = client.get("/committee")
        check("P1-6", "/committee while logged out redirects to login",
              response.status_code == 302 and "/committee/login" in response.headers.get("Location", ""))

    with app.test_client() as client:
        login_member(client, "member@sai.edu", "goodpassword")
        token = csrf_token(client, "/committee")
        client.post("/committee/logout", data={"csrf_token": token})
        response = client.get("/committee")
        check("P1-7", "logout clears the session",
              response.status_code == 302 and "login" in response.headers.get("Location", ""))

    with app.test_client() as client:
        response = login_admin(client)
        check("P1-8", "valid admin password sets an admin session",
              response.status_code == 302 and "/admin/members" in response.headers.get("Location", ""))

    with app.test_client() as client:
        token = csrf_token(client, "/admin/login")
        response = client.post("/admin/login",
                               data={"password": "wrong", "csrf_token": token})
        check("P1-9", "wrong admin password is refused",
              response.status_code == 401)

    # CSRF
    with app.test_client() as client:
        login_admin(client)
        no_token = client.post("/admin/members/add",
                               data={"name": "X", "email": "x@sai.edu"})
        check("P1-11", "POST without a CSRF token is rejected with 403",
              no_token.status_code == 403, f"status={no_token.status_code}")

        forged = client.post("/admin/members/add", data={
            "name": "X", "email": "x@sai.edu", "csrf_token": "forged-token"})
        check("P1-12", "POST with a forged CSRF token is rejected",
              forged.status_code == 403, f"status={forged.status_code}")

    # Student flow regression
    with app.test_client() as client:
        form_page = client.get("/")
        submitted = client.post("/submit", data={"overall": "4", "review": "fine",
                                                 "suggestion": "more sweets"})
        check("P1-16", "student form and submission still work unchanged",
              form_page.status_code == 200 and submitted.status_code == 302 and
              len(BOOK.tabs["responses"].rows) == 1,
              f"form={form_page.status_code} submit={submitted.status_code} "
              f"rows={len(BOOK.tabs['responses'].rows)}")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Member management UI
# ══════════════════════════════════════════════════════════════════════════════

def phase_2():
    section("PHASE 2 — Member management UI")
    BOOK.reset()

    with app.test_client() as client:
        login_admin(client)
        response = client.get("/admin/members")
        check("P2-1", "/admin/members renders for an admin session",
              response.status_code == 200 and "members-table" in response.get_data(as_text=True)
              or response.status_code == 200)

    # Privilege separation — the headline guarantee of this design
    with app.test_client() as client:
        response = client.get("/admin/members?token=vc2026")
        check("P2-2", "/admin/members refuses a ?token=-only request",
              response.status_code == 302 and "/admin/login" in response.headers.get("Location", ""),
              f"status={response.status_code} — token must not reach the roster UI")

    with app.test_client() as client:
        blocked = []
        for path in ["/admin/members/add", "/admin/members/bulk", "/admin/members/update"]:
            r = client.post(f"{path}?token=vc2026", data={"name": "X", "email": "x@sai.edu"})
            blocked.append(r.status_code in (302, 403))
        check("P2-3", "all mutation routes refuse a ?token=-only request",
              all(blocked), f"statuses={blocked}")

    # Add a member and use the revealed password
    with app.test_client() as client:
        login_admin(client)
        response = add_member_via_ui(client, "Aarav Sharma", "aarav@sai.edu")
        html = response.get_data(as_text=True)
        password = extract_password(html, "aarav@sai.edu")

        check("P2-4", "adding a member appends a row and reveals a password",
              len(BOOK.members().rows) == 1 and password is not None,
              f"rows={len(BOOK.members().rows)} password={password}")

    with app.test_client() as client:
        response = login_member(client, "aarav@sai.edu", password or "")
        check("P2-5", "the new member can log in immediately (cache invalidated)",
              response.status_code == 302, f"status={response.status_code}")

    check("P2-6", "only the hash is stored — no plaintext in the sheet",
          password and password not in BOOK.members().all_cell_text(),
          "the generated password appears in a sheet cell")

    with app.test_client() as client:
        login_admin(client)
        response = add_member_via_ui(client, "Aarav Again", "AARAV@SAI.EDU")
        check("P2-7", "duplicate email rejected case-insensitively",
              response.status_code == 400 and len(BOOK.members().rows) == 1,
              f"status={response.status_code} rows={len(BOOK.members().rows)}")

    seed_member("past@sai.edu", "Past Member", "pw12345678", active=False)
    with app.test_client() as client:
        login_admin(client)
        response = add_member_via_ui(client, "Past Member", "past@sai.edu")
        check("P2-8", "duplicate against an inactive member is also rejected",
              response.status_code == 400 and "reactivate" in response.get_data(as_text=True).lower())

    with app.test_client() as client:
        login_admin(client)
        response = add_member_via_ui(client, "Bad Email", "not-an-email")
        check("P2-9", "malformed email rejected",
              response.status_code == 400)

    # Domain allowlist
    os.environ["COMMITTEE_EMAIL_DOMAIN"] = "saiuniversity.edu.in"
    with app.test_client() as client:
        login_admin(client)
        wrong_domain = add_member_via_ui(client, "Outside", "someone@gmail.com")
        right_domain = add_member_via_ui(client, "Inside", "someone@saiuniversity.edu.in")
        check("P2-10", "COMMITTEE_EMAIL_DOMAIN allowlist enforced when set",
              wrong_domain.status_code == 400 and right_domain.status_code == 200,
              f"wrong={wrong_domain.status_code} right={right_domain.status_code}")
    del os.environ["COMMITTEE_EMAIL_DOMAIN"]

    # Deactivate / reactivate
    with app.test_client() as client:
        login_admin(client)
        token = csrf_token(client, "/admin/members")
        client.post("/admin/members/update", data={
            "email": "aarav@sai.edu", "action": "deactivate", "csrf_token": token})
        member = sheets.get_committee_member("aarav@sai.edu")
        blocked = login_member(app.test_client(), "aarav@sai.edu", password)
        check("P2-11", "deactivate sets Active=FALSE + Term_End and blocks login",
              not member["is_active"] and member["Term_End"] and blocked.status_code == 401,
              f"active={member['is_active']} term_end={member['Term_End']} "
              f"login={blocked.status_code}")

        token = csrf_token(client, "/admin/members")
        client.post("/admin/members/update", data={
            "email": "aarav@sai.edu", "action": "activate", "csrf_token": token})
        member = sheets.get_committee_member("aarav@sai.edu")
        check("P2-12", "reactivate sets Active=TRUE and clears Term_End",
              member["is_active"] and not member["Term_End"],
              f"active={member['is_active']} term_end={member['Term_End']}")

    # Password reset
    with app.test_client() as client:
        login_admin(client)
        token = csrf_token(client, "/admin/members")
        response = client.post("/admin/members/update", data={
            "email": "aarav@sai.edu", "action": "reset", "csrf_token": token})
        new_password = extract_password(response.get_data(as_text=True), "aarav@sai.edu")

    old_login = login_member(app.test_client(), "aarav@sai.edu", password)
    new_login = login_member(app.test_client(), "aarav@sai.edu", new_password or "")
    check("P2-13", "reset issues a working password and invalidates the old one",
          new_password and new_login.status_code == 302 and old_login.status_code == 401,
          f"old={old_login.status_code} new={new_login.status_code}")

    # Bulk add
    BOOK.reset()
    with app.test_client() as client:
        login_admin(client)
        token = csrf_token(client, "/admin/members")
        before_calls = BOOK.members().append_rows_calls
        response = client.post("/admin/members/bulk", data={
            "members": ("Diya Menon, diya@sai.edu\n"
                        "Rohan Iyer, rohan@sai.edu\n"
                        "Broken Line Without Comma\n"
                        "Bad Email, nope\n"
                        "Diya Again, diya@sai.edu\n"),
            "csrf_token": token})
        html = response.get_data(as_text=True)

        check("P2-14", "bulk add creates valid rows and reports each reject",
              len(BOOK.members().rows) == 2 and "Line 3" in html and
              "Line 4" in html and "Line 5" in html,
              f"rows={len(BOOK.members().rows)}")

        check("P2-15", "bulk add uses a single append_rows call",
              BOOK.members().append_rows_calls - before_calls == 1,
              f"calls={BOOK.members().append_rows_calls - before_calls}")

    passwords = [auth.generate_password() for _ in range(200)]
    check("P2-16", "generated passwords exclude lookalike characters",
          not any(c in "".join(passwords) for c in "0O1lI"),
          "a lookalike character appeared in a generated password")

    # XSS / escaping
    BOOK.reset()
    with app.test_client() as client:
        login_admin(client)
        add_member_via_ui(client, "<script>alert('xss')</script>", "xss@sai.edu")
        html = client.get("/admin/members").get_data(as_text=True)
        check("P2-18", "member names render escaped, not executable",
              "<script>alert('xss')</script>" not in html and "&lt;script&gt;" in html)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Rating page
# ══════════════════════════════════════════════════════════════════════════════

def phase_3():
    section("PHASE 3 — Rating page")
    BOOK.reset()
    seed_member("rater@sai.edu", "Rater", "goodpassword")

    with app.test_client() as client:
        login_member(client, "rater@sai.edu", "goodpassword")
        html = client.get("/committee").get_data(as_text=True)
        present = all(f'name="{d.lower()}"' in html for d in sheets.DIMENSIONS)
        check("P3-1", "rating page shows all five dimensions", present,
              f"dimensions={sheets.DIMENSIONS}")

        token = csrf_token(client, "/committee")
        response = client.post("/committee/submit", data={
            "taste": "5", "quality": "4", "variety": "3",
            "hygiene": "2", "menu": "1", "review": "Rice & dal were <cold>",
            "csrf_token": token})

        row = BOOK.reviews().rows[0] if BOOK.reviews().rows else []
        check("P3-2", "valid submission writes one row in header order",
              response.status_code == 302 and len(BOOK.reviews().rows) == 1 and
              row[2] == "rater@sai.edu" and row[4:9] == [5, 4, 3, 2, 1],
              f"row={row}")

        check("P3-6", "review stored raw so Jinja escapes exactly once",
              row and row[9] == "Rice & dal were <cold>",
              f"stored={row[9] if row else None!r}")

        check("P3-9", "Timestamp and plain-text Date written correctly",
              row and re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", str(row[0]))
              and re.match(r"^\d{4}-\d{2}-\d{2}$", str(row[1])),
              f"ts={row[0] if row else None} date={row[1] if row else None}")

        # Duplicate same day
        token = csrf_token(client, "/committee/thanks")
        duplicate = client.post("/committee/submit", data={
            "taste": "5", "quality": "5", "variety": "5",
            "hygiene": "5", "menu": "5", "csrf_token": token})
        check("P3-8", "second submission the same day is refused",
              len(BOOK.reviews().rows) == 1 and
              "already reviewed" in duplicate.get_data(as_text=True).lower(),
              f"rows={len(BOOK.reviews().rows)}")

    # Validation
    BOOK.reset()
    seed_member("rater@sai.edu", "Rater", "goodpassword")
    with app.test_client() as client:
        login_member(client, "rater@sai.edu", "goodpassword")
        token = csrf_token(client, "/committee")
        missing = client.post("/committee/submit", data={
            "taste": "5", "quality": "4", "variety": "3", "hygiene": "2",
            "csrf_token": token})
        check("P3-3", "a missing dimension is rejected and writes nothing",
              missing.status_code == 400 and len(BOOK.reviews().rows) == 0 and
              "error-banner" in missing.get_data(as_text=True))

        rejected = []
        for bad in ["0", "6", "abc", "-1", "3.5"]:
            token = csrf_token(client, "/committee")
            r = client.post("/committee/submit", data={
                "taste": bad, "quality": "4", "variety": "3", "hygiene": "2",
                "menu": "1", "csrf_token": token})
            rejected.append(r.status_code == 400)
        check("P3-4", "out-of-range and non-numeric ratings rejected",
              all(rejected) and len(BOOK.reviews().rows) == 0,
              f"results={rejected}")

        token = csrf_token(client, "/committee")
        no_review = client.post("/committee/submit", data={
            "taste": "4", "quality": "4", "variety": "4", "hygiene": "4",
            "menu": "4", "csrf_token": token})
        check("P3-5", "review is optional",
              no_review.status_code == 302 and len(BOOK.reviews().rows) == 1)

    # Truncation
    BOOK.reset()
    seed_member("long@sai.edu", "Long", "goodpassword")
    with app.test_client() as client:
        login_member(client, "long@sai.edu", "goodpassword")
        token = csrf_token(client, "/committee")
        client.post("/committee/submit", data={
            "taste": "3", "quality": "3", "variety": "3", "hygiene": "3",
            "menu": "3", "review": "x" * 900, "csrf_token": token})
        stored = BOOK.reviews().rows[0][9]
        check("P3-7", "review truncated to 500 characters",
              len(stored) == 500, f"length={len(stored)}")

    # Forced password change
    BOOK.reset()
    seed_member("new@sai.edu", "New Member", "temp-password", must_change=True)
    with app.test_client() as client:
        login = login_member(client, "new@sai.edu", "temp-password")
        rating_page = client.get("/committee")
        check("P3-10", "Must_Change_Password blocks the rating page",
              "/committee/password" in login.headers.get("Location", "") and
              rating_page.status_code == 302 and
              "/committee/password" in rating_page.headers.get("Location", ""),
              f"login={login.headers.get('Location')} page={rating_page.headers.get('Location')}")

        token = csrf_token(client, "/committee/password")
        changed = client.post("/committee/password", data={
            "password": "my-new-password", "confirm": "my-new-password",
            "csrf_token": token})
        member = sheets.get_committee_member("new@sai.edu")
        after = client.get("/committee")
        check("P3-11", "password change clears the flag and unblocks rating",
              not member["must_change_password"] and changed.status_code == 302
              and after.status_code == 200,
              f"must_change={member['must_change_password']} page={after.status_code}")

        # New password works, old one does not
        old = login_member(app.test_client(), "new@sai.edu", "temp-password")
        new = login_member(app.test_client(), "new@sai.edu", "my-new-password")
        check("P3-11b", "the new password replaces the temporary one",
              old.status_code == 401 and new.status_code == 302,
              f"old={old.status_code} new={new.status_code}")

    BOOK.reset()
    seed_member("pw@sai.edu", "PW", "goodpassword", must_change=True)
    with app.test_client() as client:
        login_member(client, "pw@sai.edu", "goodpassword")
        token = csrf_token(client, "/committee/password")
        short = client.post("/committee/password", data={
            "password": "abc", "confirm": "abc", "csrf_token": token})
        token = csrf_token(client, "/committee/password")
        mismatch = client.post("/committee/password", data={
            "password": "longenough123", "confirm": "different123",
            "csrf_token": token})
        check("P3-12", "short and mismatched passwords rejected",
              short.status_code == 400 and mismatch.status_code == 400,
              f"short={short.status_code} mismatch={mismatch.status_code}")

    # Shared-NAT: the per-IP student limiter must not touch committee submits
    BOOK.reset()
    seed_member("nat1@sai.edu", "NAT One", "goodpassword")
    seed_member("nat2@sai.edu", "NAT Two", "goodpassword")
    LIMITER.enabled = True
    try:
        with app.test_client() as client:
            client.post("/submit", data={"overall": "4"})
            student_second = client.post("/submit", data={"overall": "4"})

        submits = []
        for email in ["nat1@sai.edu", "nat2@sai.edu"]:
            with app.test_client() as client:
                login_member(client, email, "goodpassword")
                token = csrf_token(client, "/committee")
                r = client.post("/committee/submit", data={
                    "taste": "4", "quality": "4", "variety": "4",
                    "hygiene": "4", "menu": "4", "csrf_token": token})
                submits.append(r.status_code)

        check("P3-13", "committee submits are not blocked by the per-IP student cap",
              student_second.status_code == 429 and submits == [302, 302] and
              len(BOOK.reviews().rows) == 2,
              f"student_second={student_second.status_code} committee={submits}")
    finally:
        LIMITER.enabled = False


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Committee dashboard
# ══════════════════════════════════════════════════════════════════════════════

def phase_4():
    section("PHASE 4 — Committee dashboard")
    from datetime import datetime, timedelta

    BOOK.reset()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    seed_member("a@sai.edu", "Member A", "goodpassword")
    seed_member("b@sai.edu", "Member B", "goodpassword")
    seed_member("c@sai.edu", "Member C", "goodpassword")
    seed_member("d@sai.edu", "Former D", "goodpassword", active=False)

    # Today: Taste 4 and 2 -> 3.0 ; all dims average to 3.0 overall
    seed_review("a@sai.edu", "Member A", today, [4, 4, 4, 4, 4], "Good today")
    seed_review("b@sai.edu", "Member B", today, [2, 2, 2, 2, 2], "Cold rice")
    seed_review("c@sai.edu", "Member C", yesterday, [5, 5, 5, 5, 5], "Excellent")

    with app.test_client() as client:
        login_admin(client)
        response = client.get("/dashboard/committee")
        html = response.get_data(as_text=True)
        check("P4-1", "renders with an admin session", response.status_code == 200)

    with app.test_client() as client:
        response = client.get("/dashboard/committee?token=vc2026")
        check("P4-2", "renders with ?token= (read-only access retained)",
              response.status_code == 200)
        html = response.get_data(as_text=True)

    with app.test_client() as client:
        denied = client.get("/dashboard/committee?token=wrong")
        absent = client.get("/dashboard/committee")
        check("P4-3", "wrong or absent token gives 403",
              denied.status_code == 403 and absent.status_code == 403,
              f"wrong={denied.status_code} absent={absent.status_code}")

    # 2 of 3 active members submitted -> 67%
    flat = re.sub(r"\s+", "", html)
    check("P4-4", "stat cards show average, count, active members, participation",
          ">3.0<" in flat and ">2<" in flat and ">3<" in flat and ">67%<" in flat,
          "expected avg 3.0, 2 reviews, 3 active, 67% participation")

    with app.test_client() as client:
        html = client.get("/dashboard/committee?token=vc2026").get_data(as_text=True)
        payload = re.search(r"dimensionData: (\{.*?\}),\n", html, re.S)
        import json
        dimension_data = json.loads(payload.group(1)) if payload else {}
        correct = all(dimension_data.get(d, {}).get("avg") == 3.0
                      for d in sheets.DIMENSIONS)
        check("P4-5", "per-dimension averages computed correctly",
              correct, f"dimensionData={dimension_data}")

        trend_match = re.search(r"trendData: (\[.*?\]),\n", html, re.S)
        trend = json.loads(trend_match.group(1)) if trend_match else []
        check("P4-6", "trend data covers both days and serialises to JSON",
              len(trend) == 2 and trend[0]["Date"] == yesterday and
              trend[1]["Avg_Overall"] == 3.0,
              f"trend={trend}")

        check("P4-7", "reviews feed is newest-first with name and date",
              html.index("Cold rice") < html.index("Excellent") and
              "Member B" in html,
              "review ordering or attribution is wrong")

    BOOK.reset()
    with app.test_client() as client:
        response = client.get("/dashboard/committee?token=vc2026")
        check("P4-8", "zero data renders empty states rather than crashing",
              response.status_code == 200 and
              "No written reviews yet" in response.get_data(as_text=True))

    BOOK.mode = "raise"
    sheets.invalidate_roster_cache()
    with app.test_client() as client:
        response = client.get("/dashboard/committee?token=vc2026")
        check("P4-9", "a Sheets outage renders safe defaults, not a 500",
              response.status_code == 200, f"status={response.status_code}")
    BOOK.mode = "ok"

    BOOK.reset()
    with app.test_client() as client:
        response = client.get("/dashboard?token=vc2026")
        check("P4-10", "the existing student dashboard still renders",
              response.status_code == 200)


def report():
    section("SUMMARY")
    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    failed = [r for r in RESULTS if not r[2]]
    print(f"  {passed}/{len(RESULTS)} checks passed")
    if failed:
        print("\n  FAILED:")
        for item_id, description, _, detail in failed:
            print(f"    {item_id}  {description}")
            if detail:
                print(f"        {detail}")
    return 0 if not failed else 1


if __name__ == "__main__":
    print("MessMate — Food Committee verification harness")
    print("(in-memory sheets fake; no Google credentials required)")
    phase_0()
    phase_1()
    phase_2()
    phase_3()
    phase_4()
    sys.exit(report())
