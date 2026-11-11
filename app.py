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
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sheets
import auth
import csrf
import ui_config
import device
import pilot
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

# The one UI configuration: design tokens (/ui/tokens.css) and score bands
ui_config.init_app(app)

# Anonymous per-device cookies: the rate-limiter key and "what I rated today"
device.init_app(app)

# A quick tap is refused for a meal whose serving window has not started.
# Tests switch this off so they are not hostage to the wall clock.
app.config.setdefault("ENFORCE_MEAL_WINDOWS", True)

# Flask-Limiter. Student routes key on the anonymous device cookie
# (device.device_id) rather than the IP: a hostel sits behind one NAT address,
# so a per-IP cap is a per-building cap. Login routes keep the IP key.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


# Sheets reads are cached (see sheets.py, "Read cache"). The refresh thread is
# started by the first request rather than at import, so the debug reloader's
# watcher process — which never serves a request — does not run one too.
@app.before_request
def _start_sheets_cache_refresh():
    sheets.start_refresh_scheduler()


# Who is signed in, for the sign-in / sign-out control in every header.
# Read from the session, not from per-route template variables, so a header
# never offers "Sign in" to someone who is already signed in.
@app.context_processor
def _inject_auth_role():
    if auth.is_admin_session():
        role = "admin"
    elif auth.is_viewer_session():
        role = "viewer"
    elif auth.current_member():
        role = "member"
    else:
        role = None
    return {"auth_role": role}


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
    if request.path.startswith("/home"):
        # Stay on the home page: a capped quick tap is answered where it was
        # made, with its own message, not with the per-dish form.
        return _render_home(rated="limit"), 429
    return render_template(
        "form.html",
        error="You've already submitted a review in the last 4 hours. "
              "Come back after your next meal! 😊"
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
    if val and val.isdigit() and 1 <= int(val) <= 5:
        return int(val)
    return ""


@app.route("/submit", methods=["POST"])
@limiter.limit("1 per 4 hours", key_func=device.device_id)  # one review per device per 4 hours
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
        "is_viewer": auth.is_viewer_session(),
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
    return redirect(url_for("signin"))


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

def _parse_meal(val):
    """'lunch' / 'Lunch' -> 'Lunch'; anything not in sheets.MEALS -> None."""
    meal = str(val or "").strip().title()
    return meal if meal in sheets.MEALS else None


def _default_committee_meal(reviewed, now=None):
    """
    The meal the rating page opens on when none is asked for: the latest meal
    that has started serving and is not yet reviewed — at 1 pm, Lunch. Before
    breakfast, or once every served meal is done, the first unreviewed meal.
    """
    now = now or datetime.now()
    served = [m for m in sheets.MEALS if sheets.meal_is_open(m, now)]
    for meal in reversed(served):
        if meal not in reviewed:
            return meal
    for meal in sheets.MEALS:
        if meal not in reviewed:
            return meal
    return sheets.MEALS[0]


def _render_committee_form(member, meal, reviewed, error=None, status=200):
    """
    The rating page for one meal: today's dishes for it from the menu tab, the
    five areas, and the meal toggle with each meal's reviewed state.
    """
    dishes = sheets.get_menu_for_date().get(meal, [])
    meal_tabs = [{"name": m, "reviewed": m in reviewed,
                  "timing": sheets.MEAL_TIMINGS.get(m, "")}
                 for m in sheets.MEALS]
    return render_template(
        "committee_form.html", member=member, meal=meal, dishes=dishes,
        meal_tabs=meal_tabs, meal_done=meal in reviewed, error=error,
    ), status


@app.route("/committee", methods=["GET"])
@auth.login_required
@auth.password_change_required
def committee():
    """
    The committee rating page for one meal (?meal=Lunch): a 1-5 rating per
    dish on today's menu for that meal, the five areas, and an optional review.
    """
    member = auth.current_member()
    reviewed = sheets.reviewed_meals(member["Email"])

    # One review per member per meal per day. With all three done, the member
    # gets the already-reviewed page rather than a toggle of finished meals.
    if all(m in reviewed for m in sheets.MEALS):
        return render_template("committee_thanks.html",
                               member=member, already_submitted=True)

    meal = _parse_meal(request.args.get("meal")) or _default_committee_meal(reviewed)
    return _render_committee_form(member, meal, reviewed)


@app.route("/committee/submit", methods=["POST"])
@auth.login_required
@auth.password_change_required
@csrf.protect
def committee_submit():
    """
    Validates and stores one committee review.

    Deliberately NOT rate limited by IP: campus Wi-Fi puts the whole committee
    behind one NAT address, so a per-IP cap would lock out everyone after the
    first submission. Duplicate control is per member per meal per day instead.

    Dishes are posted as dish_<i> (rating) with dish_name_<i> (the name the
    page showed). The server checks those names against the menu as it stands
    NOW: if staff edited the menu while the member was rating, the indexes no
    longer line up, and saving would file ratings under the wrong dishes.
    """
    member = auth.current_member()
    reviewed = sheets.reviewed_meals(member["Email"])

    meal = _parse_meal(request.form.get("meal"))
    if not meal:
        return _render_committee_form(
            member, _default_committee_meal(reviewed), reviewed,
            error="Choose Breakfast, Lunch or Dinner to review.", status=400)

    # Every dish on today's menu for this meal is required
    dishes = sheets.get_menu_for_date().get(meal, [])
    posted_names = [str(request.form.get(f"dish_name_{i}", "")).strip()
                    for i in range(len(dishes))]
    extra_dish = request.form.get(f"dish_name_{len(dishes)}") is not None
    if posted_names != dishes or extra_dish:
        return _render_committee_form(
            member, meal, reviewed, status=409,
            error=f"Today's {meal.lower()} menu changed while you were rating. "
                  "Check the dishes below and rate them again.")

    dish_ratings = []
    for i, dish in enumerate(dishes):
        value = parse_dimension(request.form.get(f"dish_{i}"))
        if value is None:
            return _render_committee_form(
                member, meal, reviewed, status=400,
                error=f"Please rate {dish} (1-5).")
        dish_ratings.append((dish, value))

    # All five dimensions are required
    ratings = {}
    for dimension in sheets.DIMENSIONS:
        value = parse_dimension(request.form.get(dimension.lower()))
        if value is None:
            return _render_committee_form(
                member, meal, reviewed, status=400,
                error=f"Please rate {dimension} (1-5).")
        ratings[dimension] = value

    if meal in reviewed:
        return render_template("committee_thanks.html", member=member,
                               already_submitted=True, meal=meal,
                               remaining=[m for m in sheets.MEALS if m not in reviewed])

    # CRITICAL: stored raw, not html.escape()d. Jinja2 auto-escapes it on the
    # dashboard; escaping here too would render literal "&amp;" to admins.
    review_text = request.form.get("review", "")[:500]

    data = {
        "Member_Email": member["Email"],
        "Member_Name": member.get("Name", ""),
        "Review": review_text,
        "Meal": meal,
    }
    data.update(ratings)

    try:
        if sheets.append_committee_review(data, dish_ratings):
            return redirect(url_for("committee_thanks", meal=meal))
        return _render_committee_form(
            member, meal, reviewed, status=500,
            error="Failed to save your review. Please try again.")
    except Exception as e:
        print(f"Error writing committee review: {e}")
        return _render_committee_form(
            member, meal, reviewed, status=500,
            error="An error occurred saving your review.")


@app.route("/committee/thanks", methods=["GET"])
@auth.login_required
def committee_thanks():
    """Post-submission confirmation, with a link on to any meal still unreviewed."""
    member = auth.current_member()
    reviewed = sheets.reviewed_meals(member["Email"])
    return render_template(
        "committee_thanks.html", member=member,
        meal=_parse_meal(request.args.get("meal")),
        remaining=[m for m in sheets.MEALS if m not in reviewed])


@app.route("/committee/dashboard", methods=["GET"])
@auth.login_required
@auth.password_change_required
def committee_member_dashboard():
    """
    The committee's own dashboard, for signed-in members.

    The same committee analytics the admin sees, plus the member's own
    record (reviews this month, last review) and — as context, in its own
    card and never averaged in — what students said today. A member who
    can see the trend they are contributing to files better reviews than one
    rating into a void.
    """
    member = auth.current_member()
    email = str(member.get("Email", "")).strip().lower()
    today = datetime.now().strftime("%Y-%m-%d")
    this_month = today[:7]

    context = {
        "member": member,
        "dimensions": sheets.DIMENSIONS,
        "today_date": datetime.now().strftime("%A, %d %B %Y"),
        "is_admin": False,
        "mine_this_month": 0,
        "my_last": None,
        "reviewed_today": False,
        "student": _empty_student_analytics(),
        "taps": _empty_meal_taps(),
    }
    try:
        context.update(_committee_analytics())
        mine = [r for r in sheets.get_committee_reviews()
                if str(r.get("Member_Email", "")).strip().lower() == email]
        mine.sort(key=lambda r: (str(r.get("Date", "")), str(r.get("Timestamp", ""))))
        context["mine_this_month"] = sum(
            1 for r in mine if str(r.get("Date", "")).startswith(this_month))
        context["reviewed_today"] = any(str(r.get("Date", "")).strip() == today for r in mine)
        if mine:
            last = mine[-1]
            scores = [_num(last.get(d)) for d in sheets.DIMENSIONS if str(last.get(d, "")).strip()]
            context["my_last"] = {
                "date": str(last.get("Date", "")),
                "avg": _average(scores),
                "scores": {d: last.get(d, "") for d in sheets.DIMENSIONS},
                "text": str(last.get("Review", "")).strip(),
            }
    except Exception as e:
        print(f"Error loading member dashboard: {e}")
        context.update(_empty_committee_analytics())

    # Student context, kept to its own card
    try:
        context["student"] = _student_analytics()
        context["taps"] = _meal_tap_summary(today)
    except Exception as e:
        print(f"Member dashboard: student context unavailable: {e}")

    return render_template("committee_member_dashboard.html", **context)


# ── Sign in: one door for every role ──────────────────────────────────────────

def _safe_next(path, default):
    """Only ever redirect to a local path — an absolute URL would be an open redirect."""
    path = str(path or "")
    if path.startswith("/") and not path.startswith("//"):
        return path
    return default


def _render_signin(**extra):
    return render_template(
        "signin.html",
        next=_safe_next(request.values.get("next", ""), ""),
        pilot_accounts=pilot.accounts(),
        pilot_mode=pilot.enabled(),
        **extra
    )


@app.route("/signin", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
@csrf.protect
def signin():
    """
    Unified sign-in: the email decides the role.

      admin@messmate.demo   -> the admin password (ADMIN_PASSWORD_HASH)
      dean@messmate.demo    -> the read-only viewer (VIEWER_PASSWORD / token)
      anyone else           -> a committee member, checked against the roster

    The per-role pages (/admin/login, /committee/login) still work; this is
    the front door, and the only page that lists the demo's pilot accounts.
    One failure message for every wrong combination, so the page never says
    which emails exist.
    """
    if request.method == "GET":
        return _render_signin()

    email = str(request.form.get("email", "")).strip().lower()
    password = request.form.get("password", "")
    next_path = request.values.get("next", "")
    role = pilot.SPECIAL_EMAILS.get(email)

    if role == "admin":
        if not auth.verify_admin(password):
            return _render_signin(error="Incorrect email or password."), 401
        auth.login_admin()
        return redirect(_safe_next(next_path, url_for("admin_overview")))

    if role == "viewer":
        if not auth.verify_viewer(password):
            return _render_signin(error="Incorrect email or password."), 401
        auth.login_viewer()
        return redirect(_safe_next(next_path, url_for("dashboard")))

    member = auth.verify_member(email, password)
    if not member:
        return _render_signin(error="Incorrect email or password."), 401
    auth.login_member(member)
    if member.get("must_change_password"):
        return redirect(url_for("committee_password"))
    return redirect(_safe_next(next_path, url_for("committee_member_dashboard")))


@app.route("/signout", methods=["POST"])
@csrf.protect
def signout():
    """Clears whichever role is signed in and returns to the front door."""
    auth.logout_all()
    return redirect(url_for("signin"))


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
    return redirect(url_for("signin"))


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

    # Reviews are per meal now, so one member can file up to three a day.
    # today_count is MEMBERS who reviewed (every template shows it as "X of
    # N members"), which keeps participation a true percentage of the roster.
    filed = {str(r.get("Member_Email", "")).strip().lower() for r in today_reviews}
    today_count = len(filed)
    today_review_count = len(today_reviews)
    today_meal_counts = {
        meal: sum(1 for r in today_reviews
                  if str(r.get("Meal", "")).strip().title() == meal)
        for meal in sheets.MEALS
    }
    today_avg = _average(today_all_scores)
    participation = (round(today_count / active_members * 100)
                     if active_members else 0)

    rated_dims = [(d, v["avg"]) for d, v in dimension_data.items() if v["count"]]
    lowest_dimension = min(rated_dims, key=lambda x: x[1]) if rated_dims else None
    highest_dimension = max(rated_dims, key=lambda x: x[1]) if rated_dims else None

    # Who has filed today, so a dean can see at a glance who is missing
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
                "meal": str(review.get("Meal", "")).strip().title(),
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
        "today_review_count": today_review_count,
        "today_meal_counts": today_meal_counts,
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
        "today_count": 0, "today_review_count": 0,
        "today_meal_counts": {m: 0 for m in sheets.MEALS},
        "active_members": 0, "participation": 0,
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
        "is_viewer": auth.is_viewer_session(),
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
    if ui_config.score_band(student["today_avg"]) == "red":
        alerts.append({
            "level": "danger",
            "text": f"Students rate today's lunch {student['today_avg']:.1f}/5.",
            "href": url_for("dashboard"), "action": "See dishes",
        })
    if student["worst_item"] and ui_config.score_band(student["worst_item"][1]) == "red":
        alerts.append({
            "level": "warn",
            "text": f"{student['worst_item'][0]} is today's lowest dish at "
                    f"{student['worst_item'][1]:.1f}/5.",
            "href": url_for("dashboard"), "action": "See dishes",
        })
    for meal, tally in taps["tallies"].items():
        if tally["good"] + tally["bad"] >= 5 and ui_config.tap_band(tally["score"]) == "poor":
            alerts.append({
                "level": "danger",
                "text": f"Only {tally['score']}% liked {meal.lower()} today "
                        f"({tally['total']} taps).",
                "href": url_for("dashboard"), "action": "See taps",
            })
    if committee["lowest_dimension"] and ui_config.score_band(committee["lowest_dimension"][1]) == "red":
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


def _meal_open_state(now=None):
    """Per meal: whether today's serving window has started, and when it does."""
    now = now or datetime.now()
    enforce = app.config.get("ENFORCE_MEAL_WINDOWS", True)
    return {
        meal: {
            "open": (not enforce) or sheets.meal_is_open(meal, now),
            "opens": sheets.MEAL_OPENS_LABEL.get(meal, ""),
        }
        for meal in sheets.MEALS
    }


def _render_home(selected_date=None, rated="", rated_as="", rated_meal=""):
    """
    Builds the student home. Shared by GET /home and the 429 handler, so a
    student who hits the daily cap sees this page with its own banner rather
    than the per-dish form with the wrong message.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    selected_date = str(selected_date or today).strip()

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

    is_admin = auth.can_view_dashboards()

    # What this device already said today, and whether each tap can still be
    # taken back. Lives in a signed cookie; the sheet never sees it.
    now = datetime.now()
    taps = device.rated_today()
    undoable = {meal: device.can_undo(entry, now) for meal, entry in taps.items()}

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
        rated=rated,
        rated_as=rated_as,
        rated_meal=rated_meal,
        taps=taps,
        undoable=undoable,
        open_state=_meal_open_state(now),
        enforce_windows=bool(app.config.get("ENFORCE_MEAL_WINDOWS", True)),
        is_admin=is_admin,
    )


@app.route("/home", methods=["GET"])
def home():
    """Today's menu with a quick reaction per meal and day-wise navigation."""
    return _render_home(
        selected_date=request.args.get("date", ""),
        rated=request.args.get("rated", ""),
        rated_as=request.args.get("as", ""),
        rated_meal=request.args.get("meal", ""),
    )


def _tap_was_stored(response):
    """Only a stored tap spends one of the day's three. Refusals are free."""
    return response.status_code == 302 and "&as=" in (response.headers.get("Location") or "")


@app.route("/home/rate", methods=["POST"])
@limiter.limit("3 per day", key_func=device.device_id, deduct_when=_tap_was_stored)
def home_rate():
    """
    Records one quick reaction. Anonymous — nothing identifying is stored.

    Three a day per device, matching the three meals, and never two for the
    same meal: the device remembers what it said today and can take it back
    for a few minutes (POST /home/undo). A meal cannot be rated before its
    serving window opens, nor for any day but today — the day switcher shows
    the week's menus, but an opinion needs a plate.
    """
    meal = str(request.form.get("meal", "")).strip().title()
    rating = str(request.form.get("rating", "")).strip().lower()
    suggestion = request.form.get("suggestion", "")[:200]

    if meal not in sheets.MEALS or rating not in sheets.RATINGS:
        return redirect(url_for("home", rated="invalid"))

    today = datetime.now().strftime("%Y-%m-%d")
    date_str = str(request.form.get("date", "") or today).strip()
    if date_str != today:
        return redirect(url_for("home", rated="notyet", date=date_str))

    if not _meal_open_state()[meal]["open"]:
        return redirect(url_for("home", rated="notopen", meal=meal.lower()))

    if meal in device.rated_today():
        return redirect(url_for("home", rated="already", meal=meal.lower()))

    try:
        stamp = sheets.append_meal_rating(meal, rating, suggestion)
        if stamp:
            device.remember(meal, rating, stamp)
            return redirect(url_for("home", rated=meal.lower(), **{"as": rating}))
        return redirect(url_for("home", rated="failed"))
    except Exception as e:
        print(f"Error recording meal rating: {e}")
        return redirect(url_for("home", rated="failed"))


@app.route("/home/undo", methods=["POST"])
def home_undo():
    """
    Takes back this device's tap on one meal, within device.UNDO_WINDOW of
    making it. The row the device remembered is deleted from the sheet; the
    cookie forgets it; the buttons come back.
    """
    meal = str(request.form.get("meal", "")).strip().title()
    entry = device.rated_today().get(meal)
    if meal not in sheets.MEALS or not entry:
        return redirect(url_for("home"))

    if not device.can_undo(entry):
        return redirect(url_for("home", rated="undo_late", meal=meal.lower()))

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        removed = sheets.delete_meal_rating(entry["ts"], today, meal)
    except Exception as e:
        print(f"Error undoing meal rating: {e}")
        removed = False

    if removed:
        device.forget(meal)
        return redirect(url_for("home", rated="undone", meal=meal.lower()))
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


# ── Admin: menu CSV import / template ─────────────────────────────────────────

MENU_IMPORT_MAX_BYTES = 1_000_000   # 1 MB — a year of menus is a few KB


@app.route("/admin/menu/template.csv", methods=["GET"])
@auth.admin_required
def admin_menu_template_csv():
    """
    A blank CSV for one week, matching the importer's columns. Defaults to the
    week being viewed (?start=YYYY-MM-DD), so "download, fill, upload" round-trips
    the same seven days.
    """
    start = sheets.week_start(request.args.get("start") or None)
    start_dt = datetime.strptime(start, "%Y-%m-%d")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Breakfast", "Lunch", "Dinner"])
    for offset in range(7):
        date_str = (start_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
        writer.writerow([date_str, "", "", ""])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="menu_template_{start}.csv"'},
    )


@app.route("/admin/menu/import", methods=["POST"])
@auth.admin_required
@csrf.protect
def admin_menu_import():
    """
    Bulk-imports menus from an uploaded CSV. Columns (header row,
    case-insensitive, any order): Date, Breakfast, Lunch, Dinner. Date is
    YYYY-MM-DD; each meal cell is a comma-separated dish list (quote the cell so
    its own commas do not split the row). Rows write through save_menu_week(),
    which upserts by date, so re-importing a date updates it rather than
    duplicating. A blank meal cell publishes nothing for that meal, exactly like
    the editor.
    """
    start = str(request.form.get("start", "")).strip()
    start = start if DATE_RE.match(start) else sheets.week_start()

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return _render_menu(start, error="Choose a CSV file to import."), 400

    raw = upload.read(MENU_IMPORT_MAX_BYTES + 1)
    if len(raw) > MENU_IMPORT_MAX_BYTES:
        return _render_menu(start, error="That file is too large (max 1 MB)."), 400

    try:
        text = raw.decode("utf-8-sig")   # tolerate a BOM from Excel
    except UnicodeDecodeError:
        return _render_menu(start, error="Could not read that file — save it as UTF-8 CSV."), 400

    reader = csv.DictReader(io.StringIO(text))
    columns = {(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
    missing = [c for c in ("date", "breakfast", "lunch", "dinner") if c not in columns]
    if missing:
        return _render_menu(
            start,
            error="CSV needs a header row with columns: Date, Breakfast, Lunch, Dinner.",
        ), 400

    def cell(row, key):
        return str(row.get(columns[key], "") or "").strip()

    by_date = {}      # last row for a date wins
    bad_lines = []
    for line_no, row in enumerate(reader, start=2):   # line 1 is the header
        date_str = cell(row, "date")
        if not date_str:
            continue                                  # skip blank lines
        if not DATE_RE.match(date_str):
            bad_lines.append(str(line_no))
            continue
        by_date[date_str] = (date_str, cell(row, "breakfast"),
                             cell(row, "lunch"), cell(row, "dinner"))

    days = list(by_date.values())
    if not days:
        msg = "No valid rows found in that CSV."
        if bad_lines:
            s_ = "s" if len(bad_lines) > 1 else ""
            msg = f"No valid rows — bad date on line{s_} {', '.join(bad_lines)}."
        return _render_menu(start, error=msg), 400

    if not sheets.save_menu_week(days):
        return _render_menu(start, error="Could not save the imported menu."), 500

    note = f"Imported {len(days)} day{'s' if len(days) != 1 else ''}."
    if bad_lines:
        s_ = "s" if len(bad_lines) > 1 else ""
        note += f" Skipped line{s_} {', '.join(bad_lines)} (bad date)."

    imported_start = sheets.week_start(sorted(by_date)[0])
    return _render_menu(imported_start, success=note, saved_dates=list(by_date))


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for hosting platform uptime monitoring."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
