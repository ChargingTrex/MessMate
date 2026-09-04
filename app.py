"""
MessMate Core Application Server (app.py)
------------------------------------------
This is the main Flask web server for the MessMate application.
It handles routing for the student feedback form and the admin dashboard,
processes incoming form submissions, performs input validation and rate-limiting,
and communicates with the Google Sheets backend (sheets.py) to read and write data.

Routes:
  GET  /           — Student feedback form
  POST /submit     — Process form submission (rate limited: 1/IP/day)
  GET  /thanks     — Thank-you page (proper template)
  GET  /dashboard  — Stakeholder dashboard (token-protected)
  GET  /health     — Health check endpoint
"""

# CRITICAL: ALL imports at the TOP of the file — never inside route functions
import os
import html
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


@app.route("/thanks", methods=["GET"])
def thanks():
    """Serves the post-submission thank-you page."""
    return render_template("thanks.html")




@app.route("/dashboard", methods=["GET"])
@auth.admin_view_required
def dashboard():
    """
    Serves the stakeholder dashboard with aggregated data from Sheets.
    Protected by an admin session or the legacy ?token= query string.
    """
    try:
        # ── 1. Get 30-Day Trend Data ──────────────────────────────────────
        summary_records = sheets.get_daily_summary()

        # Filter: keep rows where Date is non-empty AND Avg_Overall > 0
        valid_records = []
        for r in summary_records:
            date_str = str(r.get("Date", "")).strip()
            avg_val = r.get("Avg_Overall", 0)
            try:
                avg_num = float(avg_val) if avg_val != "" else 0
            except (ValueError, TypeError):
                avg_num = 0
            if date_str and avg_num > 0:
                valid_records.append(r)

        # Take last 30 valid records for the trend chart
        trend_data = []
        last_30 = valid_records[-30:] if len(valid_records) > 30 else valid_records
        for row in last_30:
            date_val = str(row.get("Date", ""))
            avg_val = row.get("Avg_Overall", 0)
            try:
                avg_val = float(avg_val) if avg_val != "" else 0
            except (ValueError, TypeError):
                avg_val = 0

            resp_val = row.get("Response_Count", 0)
            try:
                resp_num = int(resp_val) if resp_val != "" else 0
            except (ValueError, TypeError):
                resp_num = 0

            trend_data.append({
                "Date": date_val,
                "Avg_Overall": avg_val,
                "Response_Count": resp_num
            })

        # ── 2. Get Today's Live Data ──────────────────────────────────────
        today_responses = sheets.get_today_responses()
        today_count = len(today_responses)
        today_avg = 0

        if today_count > 0:
            overall_scores = []
            for r in today_responses:
                val = r.get("Overall", "")
                try:
                    if str(val).strip():
                        overall_scores.append(float(val))
                except ValueError:
                    pass
            if overall_scores:
                today_avg = round(sum(overall_scores) / len(overall_scores), 1)

        # ── 3. Per-Item Averages ──────────────────────────────────────────
        item_data = {}
        items = [
            "Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy",
            "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle"
        ]

        for item in items:
            item_scores = []
            for r in today_responses:
                val = r.get(item, "")
                try:
                    if str(val).strip():
                        item_scores.append(float(val))
                except ValueError:
                    pass
            if item_scores:
                item_data[item] = {
                    "avg": round(sum(item_scores) / len(item_scores), 1),
                    "count": len(item_scores)
                }
            else:
                item_data[item] = {"avg": 0, "count": 0}

        # ── 4. Sync Last Graph Point with Live Data ───────────────────────
        # Ensures stat card matches the last trend chart point
        if trend_data and today_count > 0:
            trend_data[-1]["Avg_Overall"] = today_avg
            trend_data[-1]["Response_Count"] = today_count

        # ── 5. Get Suggestions (newest first) ─────────────────────────────
        suggestions = list(reversed(sheets.get_all_suggestions()))

        # ── 6. Today's Date (formatted for display) ───────────────────────
        today_date = datetime.now().strftime("%A, %d %B %Y")

        return render_template(
            "dashboard.html",
            trend_data=trend_data,
            item_data=item_data,
            today_avg=today_avg,
            today_count=today_count,
            suggestions=suggestions,
            today_date=today_date
        )

    except Exception as e:
        print(f"Error loading dashboard: {e}")
        # Safe fallback defaults if sheet fails — no crashes
        return render_template(
            "dashboard.html",
            trend_data=[],
            item_data={},
            today_avg=0,
            today_count=0,
            suggestions=[],
            today_date=datetime.now().strftime("%A, %d %B %Y")
        )



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
            return redirect(url_for("admin_members"))
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
    return redirect(url_for("admin_members"))


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

    # Review counts this month, for spotting members who have stopped rating
    counts = {}
    for review in sheets.get_committee_reviews():
        if str(review.get("Date", "")).startswith(this_month):
            key = str(review.get("Member_Email", "")).strip().lower()
            counts[key] = counts.get(key, 0) + 1

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
        })

    # Active members first, then alphabetically
    members.sort(key=lambda m: (not m["active"], m["name"].lower()))

    return render_template(
        "admin_members.html",
        members=members,
        active_count=sum(1 for m in members if m["active"]),
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

def _average(values):
    """Mean to one decimal place, 0 for an empty list."""
    return round(sum(values) / len(values), 1) if values else 0


@app.route("/dashboard/committee", methods=["GET"])
@auth.admin_view_required
def committee_dashboard():
    """
    Committee analytics — deliberately separate from the student dashboard.

    A five-member committee average and a 200-student average measure
    different things and are never mixed.
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        reviews = sheets.get_committee_reviews()
        roster = sheets.get_committee_roster()

        active_members = sum(1 for r in roster if sheets._is_true(r.get("Active")))

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

        # ── Today ──────────────────────────────────────────────────────────
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

        # ── Trend (last 30 days with data) ─────────────────────────────────
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

        # ── Reviews feed (newest first, text only) ─────────────────────────
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

        return render_template(
            "committee_dashboard.html",
            trend_data=trend_data,
            dimension_data=dimension_data,
            dimensions=sheets.DIMENSIONS,
            today_avg=today_avg,
            today_count=today_count,
            active_members=active_members,
            participation=participation,
            reviews=review_feed,
            today_date=datetime.now().strftime("%A, %d %B %Y"),
            is_admin=auth.is_admin_session(),
        )

    except Exception as e:
        # Same failure posture as /dashboard: render empty, never 500
        print(f"Error loading committee dashboard: {e}")
        return render_template(
            "committee_dashboard.html",
            trend_data=[], dimension_data={}, dimensions=sheets.DIMENSIONS,
            today_avg=0, today_count=0, active_members=0, participation=0,
            reviews=[], today_date=datetime.now().strftime("%A, %d %B %Y"),
            is_admin=auth.is_admin_session(),
        )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for hosting platform uptime monitoring."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
