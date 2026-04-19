# MessMate — Flask App Build Prompt
**One-session prototype · Python + Flask + Google Sheets + Chart.js**
*Refined from real code review — addresses known bugs before they happen.*

---

## How to use this file
- Work through prompt blocks **in order** — each builds on the previous.
- Open your AI coding agent (Claude, Cursor, Copilot Chat, or similar).
- Paste Block 0 first. Wait for it to finish. Then paste Block 1, and so on.
- Each block is self-contained — it reminds the agent of context and defines "done."
- The agent should produce **actual runnable files**, not just explanations.

---

## Priority Legend
| Label | Meaning |
|-------|---------|
| 🔴 Must | Blocking — demo breaks without this |
| 🟠 Should | Important but demo can limp along |
| 🔵 Nice | Polish — add if time allows |

---

# PROMPT BLOCK 0 — Project Context & Setup

```
You are a senior full-stack developer helping me build "MessMate" — a college
mess food review web app. This is a prototype to demo to my college's management.

=== PROJECT OVERVIEW ===
App name      : MessMate
Purpose       : Students scan a QR code at the mess, rate today's lunch,
                and admin/deans/VC see a live dashboard with scores & trends.
Tech stack    : Python (Flask), HTML/CSS/Vanilla JS, Google Sheets (backend),
                Chart.js (CDN), Flask-Limiter, gspread, Render.com (hosting)
Developer     : Solo student — keep code simple, well-commented, beginner-friendly
Meal scope    : Lunch only (prototype).
Authentication: None for the form. Dashboard protected by a secret token in the URL.
Anonymity     : No student name or identity is stored anywhere. Fully anonymous.

=== FILE STRUCTURE TO CREATE ===
messmate/
├── app.py                 # Flask app — routes + logic
├── sheets.py              # Google Sheets read/write helpers
├── requirements.txt       # Python dependencies
├── Procfile               # For Render.com deployment
├── .gitignore             # Must include: credentials.json, .env, __pycache__
├── templates/
│   ├── form.html          # Student feedback form
│   ├── thanks.html        # Post-submission thank-you page
│   └── dashboard.html     # Stakeholder dashboard
└── static/
    ├── style.css          # Shared mobile-first styles
    └── dashboard.js       # Chart.js chart setup

=== GOOGLE SHEETS SCHEMA ===
Tab 1 — "responses" (one row per submission):
Timestamp | Overall | Rice_Curry | Rice_Rasam | Chapati | Chapati_Gravy |
Poriyal | Sweet | Salad | Curd | Papad | Pickle | Review | Suggestion

- Timestamp format: YYYY-MM-DD HH:MM:SS  (e.g. 2026-04-19 13:45:00)
  CRITICAL: Use this exact format everywhere. Date filtering uses startswith("YYYY-MM-DD").
  Never use DD/MM/YYYY or any other format.
- All item columns (Rice_Curry through Pickle) are nullable — blank if student skipped.
- Overall is always 1–5 (required).
- Review max 150 chars. Suggestion is free text.

Tab 2 — "daily_summary" (written by Flask, NOT Google Sheets formulas):
Date | Avg_Overall | Response_Count | Avg_Rice_Curry | Avg_Rice_Rasam |
Avg_Chapati | Avg_Chapati_Gravy | Avg_Poriyal | Avg_Sweet | Avg_Salad |
Avg_Curd | Avg_Papad | Avg_Pickle

- Date format: YYYY-MM-DD — same as Timestamp prefix. Must match exactly.
  Flask will look for today's date in column A to update vs. append.

=== ENVIRONMENT VARIABLES (never hardcode these) ===
GOOGLE_CREDENTIALS_JSON   Full JSON string of the service account key
SPREADSHEET_ID            Google Sheet ID from the URL
FLASK_SECRET_KEY          Random secret string (REQUIRED — raise error if missing)
DASHBOARD_TOKEN           Secret token to access /dashboard (e.g. "vc2026")

=== YOUR TASK FOR THIS SESSION ===
1. Create the full messmate/ project folder with the file structure above.
2. Create requirements.txt with:
   flask, gspread, google-auth, flask-limiter, gunicorn, python-dotenv, qrcode[pil]
3. Create Procfile: web: gunicorn app:app
4. Create .gitignore
5. Create sheets.py — see Block 1 spec.
6. Create stub app.py with Flask initialised, all imports at the top of the file
   (NOT inside functions), FLASK_SECRET_KEY loaded with a RuntimeError if missing,
   Flask-Limiter configured, and placeholder routes for:
   GET /, POST /submit, GET /thanks, GET /dashboard, GET /health
7. Add a README.md with Google Cloud service account setup steps.

CRITICAL RULES FOR app.py:
- ALL imports (including `from datetime import datetime`) go at the TOP of the file.
  Never put imports inside route functions.
- FLASK_SECRET_KEY must raise RuntimeError if not set:
    secret = os.environ.get("FLASK_SECRET_KEY")
    if not secret:
        raise RuntimeError("FLASK_SECRET_KEY environment variable is not set!")
    app.secret_key = secret
- Do NOT produce inline HTML strings in route functions.
  Always use render_template() and a proper template file.

Do NOT build the HTML templates yet — that is Block 2.
Produce all files with full content, well-commented in plain English.
Tell me when done and list every file you created.
```

---

# PROMPT BLOCK 1 — Google Sheets Layer (sheets.py)

```
We are building MessMate. Block 0 setup is complete.
Now build the complete sheets.py Google Sheets integration layer.

=== FILE TO CREATE: sheets.py ===

AUTHENTICATION:
- Use google.oauth2.service_account.Credentials
- SCOPES: spreadsheets + drive
- Locally: read from credentials.json file
- On Render: read from GOOGLE_CREDENTIALS_JSON environment variable (JSON string)
- CRITICAL: Cache the gspread client at module level to avoid re-authenticating
  on every request (each auth round-trip adds ~2 seconds of latency).
  Use a module-level _client = None variable and only create it once:

    _client = None

    def get_client():
        global _client
        if _client is None:
            creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            _client = gspread.authorize(creds)
        return _client

IMPLEMENT THESE 5 FUNCTIONS:

1. get_sheet(tab_name) → worksheet | None
   - Gets the spreadsheet by SPREADSHEET_ID env var
   - Returns the named worksheet or None on error
   - Logs errors with print()

2. append_response(data_dict) → bool
   - Appends one row to "responses" tab
   - Timestamp format: YYYY-MM-DD HH:MM:SS using datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   - Column order: Timestamp, Overall, Rice_Curry, Rice_Rasam, Chapati,
     Chapati_Gravy, Poriyal, Sweet, Salad, Curd, Papad, Pickle, Review, Suggestion
   - Returns True on success, False on failure

3. get_today_responses() → list[dict]
   - Reads all rows from "responses" tab
   - Filters to rows where Timestamp starts with today's date (YYYY-MM-DD)
   - Returns list of record dicts

4. get_daily_summary() → list[dict]
   - Reads all rows from "daily_summary" tab
   - Returns list of record dicts

5. update_daily_summary_for_today() → bool
   - Calls get_today_responses() to get today's data
   - If no responses: returns True immediately (nothing to update)
   - Calculates averages for all 11 item columns (skip blank/non-numeric values)
   - Builds a row: [today_str, avg_overall, count, avg_rice_curry, ...]
   - Reads column A of daily_summary to check if today's date already exists
   - If exists: UPDATE that row using worksheet.update(f"A{row_index}:M{row_index}", [row_data])
   - If not: APPEND using worksheet.append_row(row_data)
   - CRITICAL: today_str must use the same format as Timestamp prefix: "%Y-%m-%d"
     The date.index() lookup only works if the formats match exactly.
   - Returns True on success, False on failure

6. get_all_suggestions() → list[dict]
   - Reads all rows from "responses" tab
   - Returns list of {text, timestamp} dicts for rows where Suggestion is non-blank
   - Does NOT reverse order — let app.py handle that

Produce the complete sheets.py with all functions, well-commented.
Tell me when done.
```

---

# PROMPT BLOCK 2 — Student Feedback Form

```
We are building MessMate. Backend files are complete. Now build the student form.

=== FILE TO CREATE: templates/form.html ===

DESIGN:
- Mobile-first. Students open this by scanning a QR code on their phone.
- Clean, friendly UI. Soft whites, blue accent (#2E75B6), emojis.
- No login, no name field. Completely anonymous.
- Single scrollable page. Tappable targets minimum 44×44px. Body font minimum 16px.
- Page title: "MessMate — Rate Today's Lunch 🍱"
- Show error message (passed from Flask as `error` variable) at top if present.

SECTION 1 — OVERALL RATING (required):
- Heading: "How was today's lunch overall?"
- 5 emoji buttons in a row: 😡=1  😕=2  😐=3  🙂=4  😄=5
- Clicking one: adds blue ring highlight, deselects others
- Store value in: <input type="hidden" name="overall" id="overall_val">
- Submit button stays DISABLED until an emoji is selected

SECTION 2 — PER-ITEM RATINGS (all optional):
- Heading: "Rate individual items (optional)"
- Subtext: "Only rate what was served today"

RICE CARD — dropdown + conditional rating rows:
- Dropdown name="rice_served": [ Select... | Curry | Rasam | Both ]
- JS: "Curry" → show rice_curry row; "Rasam" → show rice_rasam row;
      "Both" → show both rows; reset → hide all, clear selections

STANDARD ITEM CARDS (5-emoji row each, all optional):
  name="chapati"        label="🫓 Chapati"
  name="chapati_gravy"  label="🫓 Chapati + Gravy / Sabzi"
  name="poriyal"        label="🥬 Poriyal"
  name="sweet"          label="🍮 Sweet / Fruits"
  name="salad"          label="🥗 Salad"
  name="curd"           label="🥛 Curd"
  name="papad"          label="🫓 Papad"
  name="pickle"         label="🫙 Pickle / Thogayal"

Each emoji row: same 5-emoji mutual-exclusivity JS. Value in hidden input.
Unselected = empty string submitted.

SECTION 3 — TEXT REVIEW (optional):
- <textarea name="review" maxlength="150" placeholder="Any comments?"></textarea>
- Live character counter: "X / 150"

SECTION 4 — SUGGEST A DISH (optional):
- <input type="text" name="suggestion" placeholder="Suggest a dish...">

SUBMIT BUTTON:
- Text: "Submit Feedback 🚀" — disabled until Section 1 selected
- On click: show "Submitting..." to prevent double-tap
- Posts to: POST /submit

=== FILE TO CREATE: templates/thanks.html ===
A proper thank-you page (NOT an inline HTML string in app.py).
- Heading: "Thanks! Your feedback was recorded. 🚀"
- Friendly message about anonymous, helping improve food quality
- Link back to the form: "Submit another response"
- Same CSS/style as form.html

=== FILE TO CREATE/UPDATE: static/style.css ===
All CSS here (no inline styles in HTML).
Include: base reset, mobile layout, emoji button styles (selected = blue ring),
card styles, dropdown, textarea, submit button, character counter,
error message styling (red background banner at top).

=== FILE TO UPDATE: app.py — complete routes ===

GET / → render form.html
  
POST /submit:
  🔴 Rate limited: @limiter.limit("1 per day")
  - Read all fields from request.form
  - Validate overall: must be digit 1-5. If not, re-render form with error.
  - Sanitize text fields: call html.escape() on Review and Suggestion ONLY.
    Do NOT escape numeric rating fields.
  - Convert ratings to int or "" (empty string for blank — NOT None, NOT 0)
  - Build data_dict and call sheets.append_response(data_dict)
  - On success: also call sheets.update_daily_summary_for_today() in a try/except
    (failure here should NOT break the student's submission)
  - On success: redirect to GET /thanks (use redirect + url_for)
  - On sheet failure: re-render form.html with error message
  - On rate limit (429): render form.html with message:
    "You've already submitted feedback for today. Come back tomorrow! 😊"

GET /thanks → render thanks.html

GET /health → return jsonify({"status": "ok"})

Tell me when done.
```

---

# PROMPT BLOCK 3 — Admin Dashboard

```
We are building MessMate. Form and backend are complete. Now build the dashboard.

=== FILE TO CREATE: templates/dashboard.html ===

AUDIENCE: Mess caterer, Deans, Chancellor, Vice Chancellor. Desktop browser.
DESIGN: Clean, professional. Chart.js via CDN. White bg, blue (#1F4E79/#2E75B6) accents.

SECTION 1 — STAT CARDS (3 in a row):
  Card A: "Today's Average" — colour-coded:
    score == 0 / no data → neutral white, show "--"
    score < 2.5          → red   (bg #FFEBEE, text #B71C1C)
    score 2.5–3.5        → amber (bg #FFF3E0, text #BF5700)
    score > 3.5          → green (bg #E8F5E9, text #1E6B3C)
  Card B: "Responses Today" — integer count
  Card C: "Today's Date" — formatted string from Flask

SECTION 2 — TREND CHART (line):
- Toggle buttons: "7 Days" | "1 Month"
- Chart.js Line chart — x: dates, y: avg score (0–5), smooth curve
- Tooltip shows: Avg Score + Response Count for that day
- Title updates based on toggle: "7-Day Overall Trend" / "30-Day Overall Trend"
- CRITICAL: The tooltip callback must index into the SLICED data array,
  not the full trendData array. Store the currently-rendered slice in a
  variable and reference that in the callback. Otherwise tooltip data
  will be misaligned in 7-day mode.

SECTION 3 — PER-ITEM SCORES (horizontal bar):
- Chart.js horizontal bar chart (indexAxis: 'y')
- Only show items with avg > 0 (skip unrated items)
- Colour bars by score: <2.5=red #EF5350, 2.5-3.5=amber #FFB300, >3.5=green #66BB6A
- Tooltip: "Avg Score: X.X" + "Rated by: N students"
- Empty state: show "No item ratings yet" text

SECTION 4 — SUGGESTIONS:
- Heading: "💡 Student Suggestions"
- Scrollable list (max-height 400px), newest first
- Each row: suggestion text + timestamp
- Empty state: "No suggestions yet."

DASHBOARD ACCESS PROTECTION:
The /dashboard route in app.py must check for a secret token:
  token = request.args.get("token", "")
  if token != os.environ.get("DASHBOARD_TOKEN", ""):
      return "Access denied. Add ?token=YOUR_TOKEN to the URL.", 403
This prevents the public from viewing feedback data.

=== FILE TO CREATE: static/dashboard.js ===
All Chart.js code goes here.
Data injected via window.MESSMATE_DATA from the template.

CRITICAL — Tooltip Bug Fix:
When rendering a sliced subset of trendData (e.g., last 7 days), the tooltip
callback must reference the sliced array, not the full array:

  function renderTrendChart(days) {
    const slicedData = trendData.slice(-days);  // keep this reference
    // ...
    tooltip callback: {
      label: function(context) {
        // Use slicedData[context.dataIndex], NOT trendData[context.dataIndex]
        const point = slicedData[context.dataIndex];
        ...
      }
    }
  }

=== FILE TO UPDATE: app.py — GET /dashboard route ===

Fetch and prepare:
  1. summary_records = sheets.get_daily_summary()
     Filter: keep rows where Date is non-empty AND Avg_Overall > 0
     Take last 30 valid records → trend_data list of {Date, Avg_Overall, Response_Count}

  2. today_responses = sheets.get_today_responses()
     today_count = len(today_responses)
     today_avg: calculate from today_responses overall scores, rounded to 1 decimal
     Do NOT reference any undefined variable like `today_summary`.
     
  3. Per-item averages: loop over today_responses, calculate avg per item key.
     item_data = { "Rice_Curry": {"avg": 3.5, "count": 12}, ... }
     Items with no ratings get {"avg": 0, "count": 0}

  4. Sync last graph point:
     If trend_data is non-empty AND today_count > 0:
       trend_data[-1]["Avg_Overall"] = today_avg
       trend_data[-1]["Response_Count"] = today_count

  5. suggestions = list(reversed(sheets.get_all_suggestions()))

  6. today_date = datetime.now().strftime("%A, %d %B %Y")

  Wrap everything in try/except with safe defaults (empty lists, 0s) on failure.

Tell me when done.
```

---

# PROMPT BLOCK 4 — Testing & Hardening

```
MessMate form and dashboard are complete. Now harden and verify everything.

=== TESTING CHECKLIST ===

1. OVERALL RATING GATE
   Submit form without selecting emoji. Expected: button stays disabled, no POST.

2. MINIMAL SUBMISSION
   Select only Overall = 3. Submit.
   Expected: one Sheet row with Overall=3, all item columns blank.

3. RICE "BOTH" MODE
   Select Both → rate Rice+Curry=4, Rice+Rasam=2. Submit.
   Expected: Rice_Curry=4 AND Rice_Rasam=2 in the Sheet row.

4. REVIEW CHARACTER LIMIT
   Type exactly 150 chars. Counter shows "150 / 150". 151st char is blocked.

5. SPAM PROTECTION
   Submit twice from same IP. 2nd attempt shows:
   "You've already submitted feedback for today. Come back tomorrow! 😊"

6. DASHBOARD TOKEN PROTECTION
   GET /dashboard → 403 Access Denied.
   GET /dashboard?token=wrong → 403.
   GET /dashboard?token=YOUR_TOKEN → dashboard loads.

7. DASHBOARD EMPTY STATE
   With no data: dashboard loads, shows "--" for avg, 0 for count, "No suggestions yet."
   No crashes or unhandled exceptions.

8. DASHBOARD TOOLTIP ACCURACY
   Switch between 7 Days and 1 Month. Hover chart points.
   Expected: tooltip shows the correct date's avg and response count.
   If tooltip shows wrong data on 7-day view, the slicedData bug is present — fix it.

9. DOUBLE-ESCAPE CHECK
   Submit suggestion: "Puliyodarai & Rice"
   Expected: dashboard shows "Puliyodarai & Rice" — NOT "Puliyodarai &amp; Rice"
   If you see &amp; the text is being double-escaped. Fix by removing html.escape()
   from the Suggestion field in app.py (Jinja2 auto-escapes on render).

10. XSS CHECK
    Submit review: <script>alert('xss')</script>
    Expected: saved as plain text, NOT executed on dashboard.
    html.escape() on Review in POST /submit handles this.

11. MOBILE LAYOUT
    Open form at 375px width in DevTools. Check: emoji row fits, no horizontal scroll.

12. HEALTH ENDPOINT
    GET /health → HTTP 200, body: {"status": "ok"}

After all 12 pass, output a summary of what was fixed and what passed clean.
```

---

# PROMPT BLOCK 5 — Demo Data Seeding

```
MessMate is tested and working. Seed realistic data for the VC demo.

=== FILE TO CREATE: seed_data.py ===

PURPOSE: Populate the "responses" tab with 70 rows across 7 days (10/day).
Also writes the "daily_summary" tab directly via update_daily_summary_for_today().

REQUIREMENTS:
- Import and use sheets.py functions (append_response, update_daily_summary_for_today)
- Days: today minus 0 through 6 (7 days total)
- Timestamps: random times between 12:00 and 14:30 for each day
- Temporarily patch datetime.now() or pass an override date to allow seeding past days.
  Best approach: add an optional date_override parameter to get_today_responses()
  and update_daily_summary_for_today() in sheets.py, so seed_data.py can seed
  and summarize one day at a time.

SCORE DISTRIBUTION per 10 rows:
  1×1, 2×2, 3×3, 3×4, 1×5 (realistic bell curve)

ITEM RATINGS:
  50–70% fill rate per item (not every student rates every item)
  Poriyal, Pickle: skew lower (2–3)
  Sweet: skew higher (3–5)
  Rice, Chapati: vary 2–4

REVIEW TEXTS (use these, rest blank):
  "Rice was a bit soggy today", "Chapati was really good!",
  "Poriyal could use more seasoning", "Sweet was excellent",
  "Overall decent meal", "Curd was fresh", "Pickle was too salty",
  "Chapati gravy was tasty", "Rice quality has improved",
  "Salad was fresh and crunchy"

SUGGESTIONS (distribute across rows):
  "Puliyodarai", "Chole Bhature on Sundays", "More variety in sweet",
  "Lemon rice option", "Sambar rice", "Raita with chapati",
  "Sprouts salad", "Fruit bowl option", "Kesari on Fridays",
  "Gobi manchurian", "Tomato soup", "Papad every day"

AFTER SEEDING:
- For each of the 7 days, call update_daily_summary_for_today(date_override=day)
- Print: "Seeded 70 rows across 7 days. Daily summaries written."
- Remind: "Open /dashboard?token=YOUR_TOKEN to verify charts."
```

---

# PROMPT BLOCK 6 — Deploy & QR Code

```
MessMate is complete and seeded. Deploy it and generate the QR code.

=== STEP 1: VERIFY DEPLOYMENT FILES ===

requirements.txt must include:
  flask, gspread, google-auth, flask-limiter, gunicorn, python-dotenv, qrcode[pil]

Procfile: web: gunicorn app:app

.gitignore must include:
  credentials.json, .env, __pycache__/, *.pyc, venv/, messmate_qr.png

app.py credentials loading — must use env var, NOT file path in production:
  creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
  if creds_json:
      creds_dict = json.loads(creds_json)
      creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
  else:
      creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

=== STEP 2: DEPLOYMENT INSTRUCTIONS (Render.com) ===
Give me step-by-step instructions to:
1. Push to a new private GitHub repository
2. Create a Render.com Web Service connected to the repo
3. Set build command and start command
4. Add environment variables:
     GOOGLE_CREDENTIALS_JSON  (full JSON string)
     SPREADSHEET_ID           (from Sheet URL)
     FLASK_SECRET_KEY         (generate with: python -c "import secrets; print(secrets.token_hex(32))")
     DASHBOARD_TOKEN          (e.g. "vc2026")
5. Deploy and get the live HTTPS URL

=== STEP 3: QR CODE (generate_qr.py) ===

Create generate_qr.py:
- Import qrcode (in requirements.txt as qrcode[pil])
- LIVE_URL variable at top — easy to edit
- CRITICAL: Add a guard before generating:
    if "your-messmate-app" in LIVE_URL or not LIVE_URL.startswith("https://"):
        print("⚠️  ERROR: Update LIVE_URL before generating the QR code!")
        sys.exit(1)
- Use ERROR_CORRECT_H (30% correction — more robust for printed posters)
- box_size=10, border=4
- Save as messmate_qr.png
- Print: "✅ QR code saved. Point it to: [URL]"
- Command-line override: python generate_qr.py https://your-url.onrender.com

=== STEP 4: FINAL DEMO CHECKLIST ===
[ ] Scan QR code on real phone — form opens
[ ] Submit test rating from phone — appears in Sheet
[ ] Open /dashboard?token=YOUR_TOKEN on laptop — charts render
[ ] Tooltip shows correct data on 7-day view
[ ] Suggestions list shows seeded suggestions
[ ] Today's average stat card updates after submission
[ ] All emojis render correctly on Android + laptop
[ ] /health returns {"status": "ok"}

When all pass:
"MessMate is live at: [URL]"
"Dashboard: [URL]/dashboard?token=YOUR_TOKEN"
"QR code: messmate_qr.png — print and post on the mess notice board."
"You are ready for the VC demo. 🎉"
```

---

# Quick Reference

| Spec | Value |
|------|-------|
| Form route | `GET /` |
| Submit route | `POST /submit` (rate limited: 1/IP/day) |
| Thanks route | `GET /thanks` (proper template, no inline HTML) |
| Dashboard route | `GET /dashboard?token=TOKEN` (403 without token) |
| Health route | `GET /health` → `{"status": "ok"}` |
| Rating scale | 1 (😡) → 5 (😄) |
| Timestamp format | `YYYY-MM-DD HH:MM:SS` — used everywhere, never change |
| Date format | `YYYY-MM-DD` — prefix of timestamp, used for filtering |
| Review limit | 150 chars max |
| Spam rule | 1 submission / IP / day (Flask-Limiter) |
| Data store | Google Sheets via gspread |
| Charts | Chart.js via CDN |
| Hosting | Render.com free tier |
| Score: 🔴 red | `< 2.5` |
| Score: 🟠 amber | `2.5 – 3.5` |
| Score: 🟢 green | `> 3.5` |

---

# Known Pitfalls — Tell the agent these if things break

| Problem | What to paste |
|---------|--------------|
| Tooltip shows wrong date's data | "The tooltip callback must index into `slicedData`, not `trendData`. Fix the renderTrendChart function to store the sliced array and use it in the tooltip." |
| Suggestions show `&amp;` on dashboard | "Remove html.escape() from the Suggestion field in POST /submit. Jinja2 auto-escapes on render — double-escaping corrupts the text." |
| Dashboard crashes with NameError | "Check app.py for any reference to `today_summary` — it doesn't exist. Remove it." |
| Slow form submissions (~5s) | "The gspread client is being recreated on every request. Add a module-level `_client` cache in sheets.py and only create it once." |
| Daily summary gets duplicate rows | "The date format in update_daily_summary_for_today() must exactly match the Timestamp prefix format: YYYY-MM-DD. Check both use `strftime('%Y-%m-%d')`." |
| gspread auth error | "Fix gspread auth to read GOOGLE_CREDENTIALS_JSON as a JSON string env var, not a file path." |
| Dashboard accessible without token | "Add token check in GET /dashboard: if request.args.get('token') != os.environ.get('DASHBOARD_TOKEN'): return 403" |
| Rate limit resets after deploy | "Render's free tier restarts the dyno on inactivity. In-memory rate limiting resets on restart. This is acceptable for the prototype — note it in the README." |
| Deploy fails on Render | "Check requirements.txt includes gunicorn and Procfile says: web: gunicorn app:app" |

---

*MessMate Build Prompt v2.0 — refined from real code review · April 2026*
