"""
MessMate Core Application Server (app.py)
----------------------------------------
This is the main Flask web server for the MessMate application.
It handles routing for the student feedback form and the admin dashboard,
processes incoming form submissions, performs input validation and rate-limiting,
and communicates with the Google Sheets backend (sheets.py) to read and write data.
"""

import os
import html
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sheets
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-dev-secret")

# Initialize Flask-Limiter for IP-based rate limiting (1 submit/IP/day as requested)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("form.html", error="You've already submitted feedback for today. Come back tomorrow! 😊"), 429

@app.route("/", methods=["GET"])
def index():
    """Serves the student feedback form."""
    return render_template("form.html")

def parse_rating(val):
    """Convert emoji rating value to integer or None if blank."""
    if val and val.isdigit():
        return int(val)
    return ""

@app.route("/submit", methods=["POST"])
@limiter.limit("1 per day")  # 1 submission per IP per day
def submit():
    """Receives form data, validates, writes row to Sheets, returns success page."""
    # Sanitize and get form fields
    form = request.form

    # Required overall
    overall = parse_rating(form.get("overall"))
    if not overall:
        return render_template("form.html", error="Overall rating is required.")

    # Optional fields
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
        "Suggestion": html.escape(form.get("suggestion", ""))
    }

    try:
        success = sheets.append_response(data_dict)
        if success:
            # Trigger background auto-update of the daily summary sheet
            try:
                sheets.update_daily_summary_for_today()
            except Exception as e:
                print(f"Failed to update daily summary: {e}")
                
            return "<html><body><div style='text-align:center; padding: 50px; font-family: sans-serif;'><h2>Thanks! Your feedback was recorded. 🚀</h2><p><a href='/'>Go back</a></p></div></body></html>"
        else:
            return render_template("form.html", error="Failed to connect to Google Sheets. Please try again later."), 500
    except Exception as e:
        print(f"Error writing to sheet: {e}")
        return render_template("form.html", error="An error occurred saving your feedback."), 500

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Serves the stakeholder dashboard; fetches aggregated data from Sheets."""
    try:
        # 1. Get 30-Day Trend Data (For the toggle)
        summary_records = sheets.get_daily_summary()
        # Filter out rows with empty dates AND rows where Avg_Overall is 0
        # (Google Sheets formulas return 0 for dates with no responses)
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
        
        # Take the last 30 records if there are many
        trend_data = []
        if valid_records:
            # Slicing from the end to get last 30
            last_30 = valid_records[-30:] if len(valid_records) > 30 else valid_records
            for row in last_30:
                date_val = str(row.get("Date", ""))
                avg_val = row.get("Avg_Overall", 0)
                try:
                    # Handle cases where the spreadsheet cell might be empty string instead of 0
                    avg_val = float(avg_val) if avg_val != "" else 0
                except ValueError:
                    avg_val = 0
                
                # Also get response count
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
        
        # 2. Get Today's Responses for Item Averages and Counts
        today_responses = sheets.get_today_responses()
        today_count = len(today_responses)
        today_avg = 0.0
        
        # Calculate today's average
        today_avg = 0
        if today_count > 0:
            if len(today_responses) > 0:
                # Calculate from live responses if we have them
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
            else:
                # Fallback to the daily summary average if live responses failed to fetch
                today_avg = today_summary.get("Avg_Overall", 0)
                try:
                    today_avg = round(float(today_avg), 1)
                except ValueError:
                    today_avg = 0
            
        # Calculate per-item averages for today
        item_data = {}
        items = ["Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy", 
                 "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle"]
                 
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
                item_data[item] = sum(item_scores) / len(item_scores)
            else:
                item_data[item] = 0
                
        # 3. Synchronize Graph with Live Data
        # Google Sheets formulas can lag or fail to parse text-formatted integers.
        # To ensure the stat card strictly matches the graph, overwrite the last graph point.
        if trend_data and today_count > 0:
            trend_data[-1]["Avg_Overall"] = today_avg
            trend_data[-1]["Response_Count"] = today_count
                
        # 4. Get Suggestions
        # The prompt says get ALL suggestions newest first, so we reverse the list
        all_suggestions = sheets.get_all_suggestions()
        suggestions_reversed = list(reversed(all_suggestions))
        
        # Format today's date
        from datetime import datetime
        today_date = datetime.now().strftime("%A, %d %B %Y")
        
        return render_template(
            "dashboard.html",
            trend_data=trend_data,
            item_data=item_data,
            today_avg=today_avg,
            today_count=today_count,
            suggestions=suggestions_reversed,
            today_date=today_date
        )
        
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        # Safe fallback defaults if sheet fails
        from datetime import datetime
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
