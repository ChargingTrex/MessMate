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
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sheets
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
    """Custom 429 page — friendly message for daily rate limit."""
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
def dashboard():
    """
    Serves the stakeholder dashboard with aggregated data from Sheets.
    Protected by a secret token in the URL query string.
    """
    # Dashboard access protection — must provide correct token
    token = request.args.get("token", "")
    if token != os.environ.get("DASHBOARD_TOKEN", ""):
        return "Access denied. Add ?token=YOUR_TOKEN to the URL.", 403

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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for hosting platform uptime monitoring."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
