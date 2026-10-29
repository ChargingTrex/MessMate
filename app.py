"""
MessMate Core Application Server (app.py)
------------------------------------------
This is the main Flask web server for the MessMate application.
It handles routing for the student feedback form and the admin dashboard,
processes incoming form submissions, performs input validation and rate-limiting,
and communicates with the Google Sheets backend (sheets.py) to read and write data.

Routes (see README.md for the full table):
  Student     GET /  POST /submit  GET /thanks  GET /home  POST /home/rate
  Committee   /committee/login  /committee  /committee/submit  /committee/password
  Admin       /admin (overview)  /admin/menu (+ /save, /save-week)  /admin/members
  Dashboards  GET /dashboard  GET /dashboard/committee  (admin session or ?token=)
  GET /health — Health check endpoint
"""

# CRITICAL: ALL imports at the TOP of the file — never inside route functions
import os
import html
import re
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sheets
import auth
import csrf
from dotenv import load_dotenv

# Load .env for local development
load_dotenv()

# ── Flask App Initialization ──────────────────────────────────────────────────
app = Flask(__name__)

# CRITICAL: FLASK_SECRET_KEY must be set — raise RuntimeError if missing
secret = os.environ.get("FLASK_SECRET_KEY")
if not secret:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set!")
app.secret_key = secret

# ── Session Hardening ─────────────────────────────────────────────────────────
# Committee and admin logins ride on signed session cookies, so these matter.
# SESSION_COOKIE_SECURE is env-driven: forcing it on would break local HTTP
# development, where the cookie would simply never be sent.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# Registers csrf_field() as a Jinja global for use in every protected form
csrf.init_app(app)

# Initialize Flask-Limiter for IP-based rate limiting (1 submit/IP/day)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


# ── Error Handlers ────────────────────────────────────────────────────────────

@app.errorhandler(429)
def ratelimit_handler(e):
    """
    Custom 429 page. Path-aware: a rate-limited login must not be answered
    with the student feedback form.
    """
    if request.path.startswith("/committee/login"):
        return render_template(
            "committee_login.html",
            error="Too many login attempts. Please try again later."
        ), 429
    if request.path.startswith("/admin/login"):
        return render_template(
            "admin_login.html",
            error="Too many login attempts. Please try again later."
        ), 429
    return render_template(
        "form.html",
        error="You've already submitted feedback for today. Come back tomorrow! 😊"
    ), 429


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Serves the student feedback form."""
    return render_template("form.html")


def parse_rating(val):
    """
    Convert a form rating value to int or empty string.
    Returns int if val is a digit string 1-5, else "" (empty string).
    NEVER returns None or 0 — blank columns must be empty strings.
    """
    if val and val.isdigit():
        return int(val)
    return ""


@app.route("/submit", methods=["POST"])
@limiter.limit("1 per day")  # 1 submission per IP per day
def submit():
    """
    Receives form data, validates, sanitizes, writes row to Sheets.
    On success: redirects to GET /thanks (not inline HTML).
    On failure: re-renders form with error message.
    """
    form = request.form

    # Required: overall rating must be digit 1-5
    overall = parse_rating(form.get("overall"))
    if not overall:
        return render_template("form.html", error="Overall rating is required.")

    # Build data dict — ratings as int or "" (empty string for blank)
    # CRITICAL: html.escape() on Review ONLY (for XSS protection).
    # Do NOT escape Suggestion — Jinja2 auto-escapes on render.
    # Double-escaping Suggestion causes "&amp;" display bug.
    data_dict = {
        "Overall": overall,
        "Rice_Curry": parse_rating(form.get("rice_curry")),
        "Rice_Rasam": parse_rating(form.get("rice_rasam")),
        "Chapati": parse_rating(form.get("chapati")),
        "Chapati_Gravy": parse_rating(form.get("chapati_gravy")),
        "Poriyal": parse_rating(form.get("poriyal")),
        "Sweet": parse_rating(form.get("sweet")),
        "Salad": parse_rating(form.get("salad")),
        "Curd": parse_rating(form.get("curd")),
        "Papad": parse_rating(form.get("papad")),
        "Pickle": parse_rating(form.get("pickle")),
        "Review": html.escape(form.get("review", "")[:150]),
        "Suggestion": form.get("suggestion", "")
    }

    try:
        success = sheets.append_response(data_dict)
        if success:
            # Trigger background auto-update of the daily summary sheet
            # Failure here should NOT break the student's submission
            try:
                result = sheets.update_daily_summary_for_today()
                print(f"Daily summary update result: {result}", flush=True)
            except Exception as e:
                print(f"Warning: Failed to update daily summary: {e}")

            # Redirect to proper thank-you page (not inline HTML)
            return redirect(url_for("thanks"))
        else:
            return render_template(
                "form.html",
                error="Failed to connect to Google Sheets. Please try again later."
            ), 500
    except Exception as e:
        print(f"Error writing to sheet: {e}")
        return render_template(
            "form.html",
            error="An error occurred saving your feedback."
        ), 500


def _average(values):
    """Mean to one decimal place, 0 for an empty list."""
    return round(sum(values) / len(values), 1) if values else 0


@app.route("/thanks", methods=["GET"])
def thanks():
    """Serves the post-submission thank-you page."""
    return render_template("thanks.html")




STUDENT_ITEMS = [
    "Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy",
    "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle"
]

ITEM_LABELS = {
    "Rice_Curry": "Rice + Curry", "Rice_Rasam": "Rice + Rasam",
    "Chapati": "Chapati", "Chapati_Gravy": "Chapati + Gravy",
    "Poriyal": "Poriyal", "Sweet": "Sweet / Fruits", "Salad": "Salad",
    "Curd": "Curd", "Papad": "Papad", "Pickle": "Pickle / Thogayal",
}


def _num(val, cast=float, default=0):
    """float/int of a sheet cell, or `default` for blanks and junk."""
    try:
        return cast(val) if str(val).strip() != "" else default
    except (ValueError, TypeError):
        return default


def _parse_date(value):
    """
    A sheet date cell as a date, or None. Accepts the ISO form the app
    writes plus the forms Google Sheets reformats it into when a column is
    not set to plain text.
    """
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _student_analytics():
    """
    Everything the student dashboard shows, computed once so the admin
    overview can show the same numbers without a second set of arithmetic.
    Raises on a Sheets failure — callers decide the fallback posture.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 1. 30-day trend from daily_summary ────────────────────────────────
    # Sorted by date rather than trusting row order: the tab is append-only
    # in normal use, but one person sorting it in the browser would otherwise
    # scramble the chart. Unparseable dates keep their row position (stable
    # sort) rather than being dropped.
    valid_records = []
    for r in sheets.get_daily_summary():
        date_str = str(r.get("Date", "")).strip()
        if date_str and _num(r.get("Avg_Overall")) > 0:
            valid_records.append(r)
    valid_records.sort(key=lambda r: (_parse_date(r.get("Date")) or datetime.min.date()))

    trend_data = []
    for row in valid_records[-30:]:
        trend_data.append({
            "Date": str(row.get("Date", "")),
            "Avg_Overall": _num(row.get("Avg_Overall")),
            "Response_Count": _num(row.get("Response_Count"), int),
        })

    # ── 2. Today, live from the responses tab ─────────────────────────────
    today_responses = sheets.get_today_responses()
    today_count = len(today_responses)
    overall_scores = [_num(r.get("Overall")) for r in today_responses
                      if str(r.get("Overall", "")).strip()]
    today_avg = _average(overall_scores)

    # ── 3. Per-item averages for today ────────────────────────────────────
    item_data = {}
    for item in STUDENT_ITEMS:
        scores = [_num(r.get(item)) for r in today_responses
                  if str(r.get(item, "")).strip()]
        item_data[item] = {"avg": _average(scores), "count": len(scores)}

    # ── 4. Keep today's trend point in step with the live stat card ───────
    # Only today's point: if the summary row for today has not been written
    # yet, overwriting the last point would relabel yesterday with today's
    # numbers, so a missing point is appended instead.
    if today_count > 0:
        if trend_data and _parse_date(trend_data[-1]["Date"]) == datetime.now().date():
            trend_data[-1]["Avg_Overall"] = today_avg
            trend_data[-1]["Response_Count"] = today_count
        else:
            trend_data.append({"Date": today, "Avg_Overall": today_avg,
                               "Response_Count": today_count})

    # ── 5. Seven-day roll-up: one number for "how has the week gone" ──────
    last_week = trend_data[-7:]
    week_avg = _average([p["Avg_Overall"] for p in last_week if p["Avg_Overall"] > 0])
    week_responses = sum(p["Response_Count"] for p in last_week)

    # Best and worst dish today, for the people who only read the headline
    rated = [(ITEM_LABELS[k], v["avg"]) for k, v in item_data.items() if v["count"]]
    best_item = max(rated, key=lambda x: x[1]) if rated else None
    worst_item = min(rated, key=lambda x: x[1]) if rated else None

    return {
        "trend_data": trend_data,
        "item_data": item_data,
        "today_avg": today_avg,
        "today_count": today_count,
        "week_avg": week_avg,
        "week_responses": week_responses,
        "best_item": best_item,
        "worst_item": worst_item,
        "suggestions": list(reversed(sheets.get_all_suggestions())),
    }


def _empty_student_analytics():
    return {
        "trend_data": [], "item_data": {}, "today_avg": 0, "today_count": 0,
        "week_avg": 0, "week_responses": 0, "best_item": None,
        "worst_item": None, "suggestions": [],
    }


def _meal_tap_summary(today):
    """
    Today's quick-tap tallies plus a seven-day roll-up, from meal_ratings.
    Kept apart from the per-dish numbers above: a tally of taps is not a mean
    of 1-5 scores, and the two are never averaged together.
    """
    tallies = sheets.summarise_meal_ratings(today)
    cutoff = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    good = ate = total = 0
    quick_suggestions = []
    for row in sheets.get_meal_ratings():
        date_str = str(row.get("Date", "")).strip()
        if date_str < cutoff:
            continue
        rating = str(row.get("Rating", "")).strip().lower()
        total += 1
        if rating == "good":
            good += 1
            ate += 1
        elif rating == "bad":
            ate += 1
        text = str(row.get("Suggestion", "")).strip()
        if text:
            quick_suggestions.append({
                "text": text,
                "meal": str(row.get("Meal", "")).strip().title(),
                "timestamp": str(row.get("Timestamp", "")),
            })
    quick_suggestions.sort(key=lambda s: s["timestamp"], reverse=True)
    return {
        "tallies": tallies,
        "today_total": sum(t["total"] for t in tallies.values()),
        "week_score": round(good / ate * 100) if ate else 0,
        "week_total": total,
        "quick_suggestions": quick_suggestions,
    }


def _empty_meal_taps():
    return {
        "tallies": {m: {"good": 0, "bad": 0, "skip": 0, "total": 0, "score": 0}
                    for m in sheets.MEALS},
        "today_total": 0, "week_score": 0, "week_total": 0,
        "quick_suggestions": [],
    }


@app.route("/dashboard", methods=["GET"])
@auth.admin_view_required
def dashboard():
    """
    Serves the student dashboard with aggregated data from Sheets.
    Protected by an admin session or the legacy ?token= query string.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    context = {
        "today_date": datetime.now().strftime("%A, %d %B %Y"),
        "is_admin": auth.is_admin_session(),
        "meals": sheets.MEALS,
        "menu_today": {meal: [] for meal in sheets.MEALS},
    }
    try:
        context.update(_student_analytics())
        context["taps"] = _meal_tap_summary(today)
        context["menu_today"] = sheets.get_menu_for_date(today)
    except Exception as e:
        # Safe fallback defaults if the sheet fails — the page renders empty,
        # it never 500s
        print(f"Error loading dashboard: {e}")
        context.update(_empty_student_analytics())
        context["taps"] = _empty_meal_taps()

    return render_template("dashboard.html", **context)


# ══════════════════════════════════════════════════════════════════════════════
# FOOD COMMITTEE MODULE
# ══════════════════════════════════════════════════════════════════════════════
# Unlike the student form, these routes are authenticated and the data is
# attributed to a named member. The student flow above stays anonymous.


def parse_dimension(val):
    """
    Validates one committee rating.
    Returns an int 1-5, or None if missing/out of range/non-numeric.

    Stricter than parse_rating() above: the student form accepts blank
    per-item ratings, but all five committee dimensions are required.
    """
    raw = str(val or "").strip()
    if not raw.isdigit():
        return None
    num = int(raw)
    if num < 1 or num > 5:
        return None
    return num


# ── Committee: authentication ─────────────────────────────────────────────────

@app.route("/committee/login", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
@csrf.protect
def committee_login():
    """Committee member login. Sets a session on success."""
    if request.method == "GET":
        if auth.current_member():
            return redirect(url_for("committee"))
        return render_template("committee_login.html")

    email = request.form.get("email", "")
    password = request.form.get("password", "")

    member = auth.verify_member(email, password)
    if not member:
        # One message for unknown email, wrong password, and deactivated
        # member alike — the login page must not reveal who is on the committee
        return render_template(
            "committee_login.html",
            error="Incorrect email or password."
        ), 401

    auth.login_member(member)

    if member.get("must_change_password"):
        return redirect(url_for("committee_password"))
    return redirect(url_for("committee"))


@app.route("/committee/logout", methods=["POST"])
@csrf.protect
def committee_logout():
    """Clears the member session."""
    auth.logout_member()
    return redirect(url_for("committee_login"))


@app.route("/committee/password", methods=["GET", "POST"])
@auth.login_required
@csrf.protect
def committee_password():
    """
    First-login password change. The password an admin hands out is generated
    server-side, displayed once, and typically relayed over chat — so it is
    marked single-use and must be replaced before the member can rate anything.
    """
    member = auth.current_member()

    if request.method == "GET":
        return render_template("committee_password.html", member=member)

    new_password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    if len(new_password) < auth.MIN_PASSWORD_LENGTH:
        return render_template(
            "committee_password.html", member=member,
            error=f"Password must be at least {auth.MIN_PASSWORD_LENGTH} characters."
        ), 400

    if new_password != confirm:
        return render_template(
            "committee_password.html", member=member,
            error="The two passwords do not match."
        ), 400

    ok = sheets.update_committee_member(
        member["Email"],
        Password_Hash=auth.hash_password(new_password),
        Must_Change_Password="FALSE"
    )
    if not ok:
        return render_template(
            "committee_password.html", member=member,
            error="Could not save your new password. Please try again."
        ), 500

    return redirect(url_for("committee"))


# ── Committee: rating ─────────────────────────────────────────────────────────

@app.route("/committee", methods=["GET"])
@auth.login_required
@auth.password_change_required
def committee():
    """The committee rating page — five dimensions plus an optional review."""
    member = auth.current_member()

    # One review per member per day. Checked on GET so the member sees the
    # already-submitted page instead of filling in a form that will be refused.
    if sheets.has_submitted_today(member["Email"]):
        return render_template("committee_thanks.html",
                               member=member, already_submitted=True)

    return render_template("committee_form.html", member=member)


@app.route("/committee/submit", methods=["POST"])
@auth.login_required
@auth.password_change_required
@csrf.protect
def committee_submit():
    """
    Validates and stores one committee review.

    Deliberately NOT rate limited by IP: campus Wi-Fi puts the whole committee
    behind one NAT address, so a per-IP cap would lock out everyone after the
    first submission. Duplicate control is per member per day instead.
    """
    member = auth.current_member()

    # All five dimensions are required
    ratings = {}
    for dimension in sheets.DIMENSIONS:
        value = parse_dimension(request.form.get(dimension.lower()))
        if value is None:
            return render_template(
                "committee_form.html", member=member,
                error=f"Please rate {dimension} (1-5)."
            ), 400
        ratings[dimension] = value

    if sheets.has_submitted_today(member["Email"]):
        return render_template("committee_thanks.html",
                               member=member, already_submitted=True)

    # CRITICAL: stored raw, not html.escape()d. Jinja2 auto-escapes it on the
    # dashboard; escaping here too would render literal "&amp;" to admins.
    review_text = request.form.get("review", "")[:500]

    data = {
        "Member_Email": member["Email"],
        "Member_Name": member.get("Name", ""),
        "Review": review_text,
    }
    data.update(ratings)

    try:
        if sheets.append_committee_review(data):
            return redirect(url_for("committee_thanks"))
        return render_template(
            "committee_form.html", member=member,
            error="Failed to save your review. Please try again."
        ), 500
    except Exception as e:
        print(f"Error writing committee review: {e}")
        return render_template(
            "committee_form.html", member=member,
            error="An error occurred saving your review."
        ), 500


@app.route("/committee/thanks", methods=["GET"])
@auth.login_required
def committee_thanks():
    """Post-submission confirmation."""
    return render_template("committee_thanks.html", member=auth.current_member())


# ── Admin: authentication ─────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
@csrf.protect
def admin_login():
    """
    Admin login. Required for anything that changes the roster — the legacy
    ?token= credential is read-only by design (see auth.py).
    """
    if request.method == "GET":
        if auth.is_admin_session():
            return redirect(url_for("admin_overview"))
        return render_template("admin_login.html")

    if not auth.verify_admin(request.form.get("password", "")):
        return render_template("admin_login.html",
                               error="Incorrect password."), 401

    auth.login_admin()

    # Only ever redirect to a local path — an absolute URL here would be an
    # open redirect
    next_path = request.form.get("next", "")
    if next_path.startswith("/") and not next_path.startswith("//"):
        return redirect(next_path)
    return redirect(url_for("admin_overview"))


@app.route("/admin/logout", methods=["POST"])
@csrf.protect
def admin_logout():
    auth.logout_admin()
    return redirect(url_for("admin_login"))


# ── Admin: member management ──────────────────────────────────────────────────

def _render_members(**extra):
    """
    Renders the roster page. Shared by the GET view and by every mutation,
    which re-render in place so one-time passwords can be revealed exactly once.
    """
    roster = sheets.get_committee_roster()
    this_month = datetime.now().strftime("%Y-%m")
    today = datetime.now().strftime("%Y-%m-%d")

    # Review counts this month, for spotting members who have stopped rating,
    # and who has already filed today
    counts, reviewed_today = {}, set()
    for review in sheets.get_committee_reviews():
        key = str(review.get("Member_Email", "")).strip().lower()
        date_str = str(review.get("Date", ""))
        if date_str.startswith(this_month):
            counts[key] = counts.get(key, 0) + 1
        if date_str == today:
            reviewed_today.add(key)

    members = []
    for record in roster:
        email = str(record.get("Email", "")).strip().lower()
        if not email:
            continue
        members.append({
            "email": email,
            "name": record.get("Name", ""),
            "active": sheets._is_true(record.get("Active")),
            "must_change": sheets._is_true(record.get("Must_Change_Password")),
            "term_start": record.get("Term_Start", ""),
            "term_end": record.get("Term_End", ""),
            "reviews_this_month": counts.get(email, 0),
            "reviewed_today": email in reviewed_today,
        })

    # Active members first, then alphabetically
    members.sort(key=lambda m: (not m["active"], m["name"].lower()))

    active = [m for m in members if m["active"]]
    return render_template(
        "admin_members.html",
        members=members,
        active_count=len(active),
        reviewed_today_count=sum(1 for m in active if m["reviewed_today"]),
        pending_count=sum(1 for m in active if m["must_change"]),
        is_admin=True,
        **extra
    )


@app.route("/admin/members", methods=["GET"])
@auth.admin_required
def admin_members():
    """Roster table plus the add / bulk-add forms."""
    return _render_members()


def _create_member(raw_email, raw_name):
    """
    Validates and creates one member.
    Returns (credentials_dict, None) or (None, error_message).

    Does not write — returns the row so bulk add can batch them into a single
    API call. The caller performs the write.
    """
    name = str(raw_name or "").strip()
    if not name:
        return None, "Name is required."

    email, error = auth.normalize_email(raw_email)
    if error:
        return None, error

    # Checked against the whole roster, including inactive members: a returning
    # member should be reactivated, not duplicated, so their history stays intact
    if sheets.get_committee_member(email):
        return None, f"{email} is already on the roster (reactivate them instead)."

    password = auth.generate_password()
    return {
        "email": email,
        "name": name,
        "password": password,
        "hash": auth.hash_password(password),
    }, None


@app.route("/admin/members/add", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_members_add():
    """Creates one member and reveals the generated password once."""
    created, error = _create_member(request.form.get("email"),
                                    request.form.get("name"))
    if error:
        return _render_members(error=error), 400

    if not sheets.add_committee_member(created["email"], created["name"],
                                       created["hash"]):
        return _render_members(error="Could not save the new member."), 500

    return _render_members(
        credentials=[created],
        success=f"Added {created['name']}."
    )


@app.route("/admin/members/bulk", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_members_bulk():
    """
    Bulk add from a pasted list, one 'Name, email' per line — for the start of
    a rotation, when the whole committee changes at once.

    Valid rows are written in a single append_rows call; invalid lines are
    reported individually so nothing fails silently.
    """
    raw = request.form.get("members", "")
    created, errors = [], []
    seen = set()

    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        if "," not in line:
            errors.append(f"Line {line_no}: expected 'Name, email'.")
            continue

        name_part, email_part = line.split(",", 1)
        record, error = _create_member(email_part, name_part)
        if error:
            errors.append(f"Line {line_no}: {error}")
            continue

        # Duplicates within the pasted block itself
        if record["email"] in seen:
            errors.append(f"Line {line_no}: {record['email']} is duplicated in this list.")
            continue

        seen.add(record["email"])
        created.append(record)

    if created:
        rows = [(c["email"], c["name"], c["hash"]) for c in created]
        if not sheets.add_committee_members_bulk(rows):
            return _render_members(error="Could not save the new members."), 500

    return _render_members(
        credentials=created,
        success=f"Added {len(created)} member(s)." if created else None,
        error=" ".join(errors) if errors else None
    )


@app.route("/admin/members/update", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_members_update():
    """
    Activate, deactivate, or reset one member's password.

    There is no delete: deactivation preserves the review history and the
    record of who served on which rotation.
    """
    email = str(request.form.get("email", "")).strip().lower()
    action = request.form.get("action", "")

    member = sheets.get_committee_member(email)
    if not member:
        return _render_members(error="Unknown member."), 404

    today = datetime.now().strftime("%Y-%m-%d")

    if action == "deactivate":
        ok = sheets.update_committee_member(email, Active="FALSE", Term_End=today)
        return (_render_members(success=f"Deactivated {email}.") if ok
                else (_render_members(error="Could not update member."), 500))

    if action == "activate":
        ok = sheets.update_committee_member(email, Active="TRUE", Term_End="")
        return (_render_members(success=f"Reactivated {email}.") if ok
                else (_render_members(error="Could not update member."), 500))

    if action == "reset":
        password = auth.generate_password()
        ok = sheets.update_committee_member(
            email,
            Password_Hash=auth.hash_password(password),
            Must_Change_Password="TRUE"
        )
        if not ok:
            return _render_members(error="Could not reset password."), 500
        return _render_members(
            credentials=[{"email": email, "name": member.get("Name", ""),
                          "password": password}],
            success=f"Password reset for {email}."
        )

    return _render_members(error="Unknown action."), 400


# ── Admin: committee dashboard ────────────────────────────────────────────────

def _committee_analytics():
    """
    Everything the committee dashboard shows. Raises on a Sheets failure.

    A five-member committee average and a 200-student average measure
    different things and are never mixed.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    reviews = sheets.get_committee_reviews()
    roster = sheets.get_committee_roster()

    active = [r for r in roster if sheets._is_true(r.get("Active"))]
    active_members = len(active)

    def dimension_values(rows, dimension):
        """Numeric values for one dimension, skipping blanks and junk."""
        values = []
        for row in rows:
            raw = str(row.get(dimension, "")).strip()
            try:
                if raw:
                    values.append(float(raw))
            except ValueError:
                pass
        return values

    # ── Today ──────────────────────────────────────────────────────────────
    today_reviews = [r for r in reviews
                     if str(r.get("Date", "")).strip() == today]

    dimension_data = {}
    today_all_scores = []
    for dimension in sheets.DIMENSIONS:
        values = dimension_values(today_reviews, dimension)
        today_all_scores.extend(values)
        dimension_data[dimension] = {"avg": _average(values),
                                     "count": len(values)}

    today_count = len(today_reviews)
    today_avg = _average(today_all_scores)
    participation = (round(today_count / active_members * 100)
                     if active_members else 0)

    rated_dims = [(d, v["avg"]) for d, v in dimension_data.items() if v["count"]]
    lowest_dimension = min(rated_dims, key=lambda x: x[1]) if rated_dims else None
    highest_dimension = max(rated_dims, key=lambda x: x[1]) if rated_dims else None

    # Who has filed today, so a dean can see at a glance who is missing
    filed = {str(r.get("Member_Email", "")).strip().lower() for r in today_reviews}
    attendance = sorted(
        ({"name": m.get("Name", "") or m.get("Email", ""),
          "email": str(m.get("Email", "")).strip().lower(),
          "reviewed": str(m.get("Email", "")).strip().lower() in filed}
         for m in active),
        key=lambda m: (m["reviewed"], m["name"].lower())
    )

    # ── Trend (last 30 days with data) ─────────────────────────────────────
    by_date = {}
    for review in reviews:
        date_str = str(review.get("Date", "")).strip()
        if date_str:
            by_date.setdefault(date_str, []).append(review)

    trend_data = []
    for date_str in sorted(by_date.keys()):
        rows = by_date[date_str]
        point = {"Date": date_str, "Response_Count": len(rows)}
        all_scores = []
        for dimension in sheets.DIMENSIONS:
            values = dimension_values(rows, dimension)
            all_scores.extend(values)
            point[dimension] = _average(values)
        point["Avg_Overall"] = _average(all_scores)
        trend_data.append(point)
    trend_data = trend_data[-30:]

    last_week = trend_data[-7:]
    week_avg = _average([p["Avg_Overall"] for p in last_week if p["Avg_Overall"] > 0])
    week_reviews = sum(p["Response_Count"] for p in last_week)

    # ── Reviews feed (newest first, text only) ─────────────────────────────
    # Sorted by Date/Timestamp rather than reversed row order: row order
    # only happens to be chronological, and stops being so the moment
    # anyone sorts the sheet or backfills a day.
    review_feed = []
    for review in reviews:
        text = str(review.get("Review", "")).strip()
        if text:
            review_feed.append({
                "name": review.get("Member_Name", "") or "Committee member",
                "date": review.get("Date", ""),
                "text": text,
                "_sort": (str(review.get("Date", "")),
                          str(review.get("Timestamp", ""))),
            })
    review_feed.sort(key=lambda r: r["_sort"], reverse=True)

    return {
        "trend_data": trend_data,
        "dimension_data": dimension_data,
        "today_avg": today_avg,
        "today_count": today_count,
        "active_members": active_members,
        "participation": participation,
        "lowest_dimension": lowest_dimension,
        "highest_dimension": highest_dimension,
        "attendance": attendance,
        "week_avg": week_avg,
        "week_reviews": week_reviews,
        "reviews": review_feed,
    }


def _empty_committee_analytics():
    return {
        "trend_data": [], "dimension_data": {}, "today_avg": 0,
        "today_count": 0, "active_members": 0, "participation": 0,
        "lowest_dimension": None, "highest_dimension": None,
        "attendance": [], "week_avg": 0, "week_reviews": 0, "reviews": [],
    }


@app.route("/dashboard/committee", methods=["GET"])
@auth.admin_view_required
def committee_dashboard():
    """Committee analytics — deliberately separate from the student dashboard."""
    context = {
        "dimensions": sheets.DIMENSIONS,
        "today_date": datetime.now().strftime("%A, %d %B %Y"),
        "is_admin": auth.is_admin_session(),
    }
    try:
        context.update(_committee_analytics())
    except Exception as e:
        # Same failure posture as /dashboard: render empty, never 500
        print(f"Error loading committee dashboard: {e}")
        context.update(_empty_committee_analytics())

    return render_template("committee_dashboard.html", **context)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN OVERVIEW — every important number on one screen
# ══════════════════════════════════════════════════════════════════════════════
# The landing page after admin sign-in. It shows nothing the three detail
# pages do not; its job is to answer "is anything wrong today?" without
# opening any of them. Each block degrades independently, so a Sheets
# hiccup on one tab blanks one card rather than the whole page.


def _menu_week_status(week):
    """
    Publication state per day for the next week, plus what needs attention.
    Returns (days, gaps) where `gaps` lists days with any meal unpublished.
    """
    days, gaps = [], []
    for day in week:
        published = sum(1 for meal in sheets.MEALS if day["published"][meal])
        entry = {
            "date": day["date"], "label": day["label"],
            "weekday": day["weekday"], "is_today": day["is_today"],
            "published": published,
            "missing": [m for m in sheets.MEALS if not day["published"][m]],
        }
        days.append(entry)
        if published < len(sheets.MEALS):
            gaps.append(entry)
    return days, gaps


@app.route("/admin", methods=["GET"])
@auth.admin_required
def admin_overview():
    """One screen with today's numbers, this week's menu state, and alerts."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    try:
        student = _student_analytics()
    except Exception as e:
        print(f"Overview: student analytics unavailable: {e}")
        student = _empty_student_analytics()

    try:
        taps = _meal_tap_summary(today)
    except Exception as e:
        print(f"Overview: meal taps unavailable: {e}")
        taps = _empty_meal_taps()

    try:
        committee = _committee_analytics()
    except Exception as e:
        print(f"Overview: committee analytics unavailable: {e}")
        committee = _empty_committee_analytics()

    try:
        week = sheets.get_menu_week(today, days=7)
        pending_passwords = sum(
            1 for m in sheets.get_committee_roster()
            if sheets._is_true(m.get("Active"))
            and sheets._is_true(m.get("Must_Change_Password")))
    except Exception as e:
        print(f"Overview: menu unavailable: {e}")
        week, pending_passwords = [], 0

    menu_days, menu_gaps = _menu_week_status(week)
    menu_today = next((d for d in menu_days if d["is_today"]), None)
    today_menu = week[0] if week and week[0]["is_today"] else None

    # ── Attention list: the reasons to open a detail page today ───────────
    alerts = []
    if menu_today and menu_today["missing"]:
        alerts.append({
            "level": "danger",
            "text": f"Today's {' and '.join(m.lower() for m in menu_today['missing'])} "
                    "menu is not published.",
            "href": url_for("admin_menu"), "action": "Publish",
        })
    upcoming_gaps = [d for d in menu_gaps if not d["is_today"]]
    if upcoming_gaps:
        alerts.append({
            "level": "warn",
            "text": f"{len(upcoming_gaps)} of the next 6 days have an unpublished meal "
                    f"(first: {upcoming_gaps[0]['label']}).",
            "href": url_for("admin_menu"), "action": "Open editor",
        })
    if 0 < student["today_avg"] < 2.5:
        alerts.append({
            "level": "danger",
            "text": f"Students rate today's lunch {student['today_avg']:.1f}/5.",
            "href": url_for("dashboard"), "action": "See dishes",
        })
    if student["worst_item"] and student["worst_item"][1] < 2.5:
        alerts.append({
            "level": "warn",
            "text": f"{student['worst_item'][0]} is today's lowest dish at "
                    f"{student['worst_item'][1]:.1f}/5.",
            "href": url_for("dashboard"), "action": "See dishes",
        })
    for meal, tally in taps["tallies"].items():
        if tally["good"] + tally["bad"] >= 5 and tally["score"] < 40:
            alerts.append({
                "level": "danger",
                "text": f"Only {tally['score']}% liked {meal.lower()} today "
                        f"({tally['total']} taps).",
                "href": url_for("dashboard"), "action": "See taps",
            })
    if committee["lowest_dimension"] and committee["lowest_dimension"][1] < 2.5:
        name, score = committee["lowest_dimension"]
        alerts.append({
            "level": "danger",
            "text": f"Committee scored {name.lower()} {score:.1f}/5 today.",
            "href": url_for("committee_dashboard"), "action": "See review",
        })
    missing = [m["name"] for m in committee["attendance"] if not m["reviewed"]]
    if committee["active_members"] and missing and now.hour >= 15:
        alerts.append({
            "level": "warn",
            "text": f"{len(missing)} of {committee['active_members']} committee members "
                    f"have not reviewed today ({', '.join(missing[:3])}"
                    f"{', …' if len(missing) > 3 else ''}).",
            "href": url_for("committee_dashboard"), "action": "See who",
        })
    if pending_passwords:
        alerts.append({
            "level": "info",
            "text": f"{pending_passwords} member{'s' if pending_passwords != 1 else ''} "
                    "never signed in to set a password.",
            "href": url_for("admin_members"), "action": "Roster",
        })

    # ── Latest feedback across all three layers, newest first ─────────────
    feed = []
    for s in student["suggestions"][:10]:
        feed.append({"source": "Dish form", "text": s["text"],
                     "when": str(s["timestamp"]), "tone": "student"})
    for s in taps["quick_suggestions"][:10]:
        feed.append({"source": f"Quick tap · {s['meal']}", "text": s["text"],
                     "when": s["timestamp"], "tone": "tap"})
    for r in committee["reviews"][:10]:
        feed.append({"source": f"Committee · {r['name']}", "text": r["text"],
                     "when": str(r["date"]), "tone": "committee"})
    feed.sort(key=lambda f: f["when"], reverse=True)

    return render_template(
        "admin_overview.html",
        today_date=now.strftime("%A, %d %B %Y"),
        today_iso=today,
        student=student,
        taps=taps,
        committee=committee,
        meals=sheets.MEALS,
        timings=sheets.MEAL_TIMINGS,
        today_menu=today_menu,
        menu_days=menu_days,
        menu_gaps=menu_gaps,
        alerts=alerts,
        feed=feed[:8],
        pending_passwords=pending_passwords,
        is_admin=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT HOME — today's menu and a one-tap reaction per meal
# ══════════════════════════════════════════════════════════════════════════════
# Three layers of feedback now exist, deliberately kept apart:
#
#   /home      one tap per meal — good / bad / skip, plus a suggestion.
#              The thing a student will actually stop to do.
#   /          the per-dish 1-5 form, for students with more to say.
#   /committee the five-dimension review, attributed, committee only.
#
# They are never mixed into one average: a tally of taps and a mean of 1-5
# scores are different measurements of different populations.


@app.route("/home", methods=["GET"])
def home():
    """Today's menu with a quick reaction per meal and day-wise navigation."""
    today = datetime.now().strftime("%Y-%m-%d")
    selected_date = request.args.get("date", today).strip()

    try:
        datetime.strptime(selected_date, "%Y-%m-%d")
    except ValueError:
        selected_date = today

    try:
        menu = sheets.get_menu_for_date(selected_date)
        tallies = sheets.summarise_meal_ratings(today)
        week = sheets.get_menu_week()
    except Exception as e:
        # Same posture as the dashboards: a Sheets problem must not take the
        # student-facing page down with it
        print(f"Error loading home page: {e}")
        menu = {meal: [] for meal in sheets.MEALS}
        tallies = {meal: {"good": 0, "bad": 0, "skip": 0, "total": 0, "score": 0}
                   for meal in sheets.MEALS}
        week = []

    # Build lookup for client-side instant day switching. Only what is
    # published goes to the page: the week entries also carry the editor's
    # template suggestions, which must never reach a student as if they were
    # the menu (the day switcher would otherwise show them on an unpublished
    # day, and every dish in the template would appear in the page source).
    week_menu_lookup = {}
    for day_info in week:
        d_str = day_info.get("date")
        if d_str:
            week_menu_lookup[d_str] = {
                meal: sheets._split_items(day_info.get(meal, ""))
                for meal in sheets.MEALS
            }
    week_meta = [{"date": d["date"], "label": d["label"], "is_today": d["is_today"]}
                 for d in week]

    try:
        display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%A, %d %B %Y")
    except Exception:
        display_date = datetime.now().strftime("%A, %d %B %Y")

    is_admin = auth.is_admin_session() or auth.has_valid_token()

    return render_template(
        "home.html",
        meals=sheets.MEALS,
        menu=menu,
        timings=sheets.MEAL_TIMINGS,
        tallies=tallies,
        today_date=display_date,
        is_today=(selected_date == today),
        today_iso=today,
        selected_date=selected_date,
        week=week_meta,
        week_json=json.dumps(week_menu_lookup),
        rated=request.args.get("rated", ""),
        is_admin=is_admin,
    )


@app.route("/home/rate", methods=["POST"])
@limiter.limit("3 per day")  # one per meal per IP per day
def home_rate():
    """
    Records one quick reaction. Anonymous — nothing identifying is stored.

    Limited to three a day per IP, matching the three meals. The per-dish form
    allows one a day; this allows one per meal, because a student who eats
    breakfast and dinner has two separate things to say.
    """
    meal = str(request.form.get("meal", "")).strip().title()
    rating = str(request.form.get("rating", "")).strip().lower()
    suggestion = request.form.get("suggestion", "")[:200]

    if meal not in sheets.MEALS or rating not in sheets.RATINGS:
        return redirect(url_for("home", rated="invalid"))

    try:
        if sheets.append_meal_rating(meal, rating, suggestion):
            return redirect(url_for("home", rated=meal.lower()))
        return redirect(url_for("home", rated="failed"))
    except Exception as e:
        print(f"Error recording meal rating: {e}")
        return redirect(url_for("home", rated="failed"))


# ── Admin: menu editor ────────────────────────────────────────────────────────

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _render_menu(start=None, **extra):
    """
    Renders the editor for the calendar week (Monday to Sunday) containing
    `start`, defaulting to the current week. Shared by the GET view and both
    save routes so a save re-renders the same week it was made in.
    """
    start = sheets.week_start(start if start and DATE_RE.match(start) else None)
    week = sheets.get_menu_week(start, days=7)
    first, last = week[0], week[-1]
    start_dt = datetime.strptime(start, "%Y-%m-%d")

    # The previous week's rows, offered as a "copy last week" starting point
    prev_start = (start_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_week = {d["date"]: {m: d[m] for m in sheets.MEALS}
                 for d in sheets.get_menu_week(prev_start, days=7)}

    published_meals = sum(1 for d in week for m in sheets.MEALS if d["published"][m])
    full_days = sum(1 for d in week if all(d["published"].values()))

    return render_template(
        "admin_menu.html",
        week=week,
        meals=sheets.MEALS,
        timings=sheets.MEAL_TIMINGS,
        start=start,
        week_label=f"{first['label']} – {last['label']}",
        is_current_week=(start == sheets.week_start()),
        prev_start=prev_start,
        next_start=(start_dt + timedelta(days=7)).strftime("%Y-%m-%d"),
        this_start=sheets.week_start(),
        prev_week_json=json.dumps(prev_week),
        published_meals=published_meals,
        total_meals=len(week) * len(sheets.MEALS),
        full_days=full_days,
        is_admin=True,
        **extra
    )


@app.route("/admin/menu", methods=["GET"])
@auth.admin_required
def admin_menu():
    """
    Week-at-a-glance menu editor, paged by calendar week (?start=YYYY-MM-DD).

    The menu tab can also be edited directly in the spreadsheet — this page is
    for whoever does not want to open it. Both routes write the same rows.
    """
    return _render_menu(request.args.get("start", ""))


@app.route("/admin/menu/save", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_menu_save():
    """Upserts one day's menu from the editor."""
    date_str = str(request.form.get("date", "")).strip()
    start = str(request.form.get("start", "")).strip() or date_str

    if not DATE_RE.match(date_str):
        return _render_menu(start, error="That date is not valid."), 400

    ok = sheets.save_menu_for_date(
        date_str,
        request.form.get("Breakfast", "").strip(),
        request.form.get("Lunch", "").strip(),
        request.form.get("Dinner", "").strip(),
    )
    if not ok:
        return _render_menu(start, error="Could not save the menu."), 500

    return _render_menu(start, success=f"Menu saved for {date_str}.",
                        saved_dates=[date_str])


@app.route("/admin/menu/save-week", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_menu_save_week():
    """
    Upserts every day of the week in one go. Fields are named
    <Meal>__<YYYY-MM-DD>; a date is written only if at least one of its meal
    fields was submitted, so a partial form never blanks days it did not carry.
    """
    start = str(request.form.get("start", "")).strip()
    if not DATE_RE.match(start):
        return _render_menu(None, error="That week is not valid."), 400

    days = []
    for offset in range(7):
        date_str = (datetime.strptime(start, "%Y-%m-%d")
                    + timedelta(days=offset)).strftime("%Y-%m-%d")
        keys = [f"{meal}__{date_str}" for meal in sheets.MEALS]
        if not any(key in request.form for key in keys):
            continue
        days.append(tuple([date_str] + [request.form.get(key, "").strip()
                                        for key in keys]))

    if not days:
        return _render_menu(start, error="Nothing to save."), 400

    if not sheets.save_menu_week(days):
        return _render_menu(start, error="Could not save the week."), 500

    return _render_menu(
        start,
        success=f"Saved {len(days)} day{'s' if len(days) != 1 else ''} "
                f"({days[0][0]} to {days[-1][0]}).",
        saved_dates=[d[0] for d in days],
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for hosting platform uptime monitoring."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
