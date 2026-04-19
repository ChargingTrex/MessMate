# MessMate — AI Agent Build Prompt
**One-session prototype build · Python + Flask + Google Sheets + Chart.js**
Cross-referenced: PRD v1.0 · TSD v1.0 · Checklist v1.0

---

## How to use this file

- Work through prompt blocks **in order** — each builds on the previous.
- Open your AI coding agent (Claude, Cursor, Copilot Chat, or similar).
- **Paste Block 0 first.** Wait for it to finish. Then paste Block 1, and so on.
- Each block is self-contained — it reminds the agent of context, gives the full spec, and defines "done."
- The agent should produce **actual runnable files**, not just explanations.
- If the agent gets confused mid-session, paste the block again with: *"Continue from where you stopped."*

---

## Priority Legend

| Label | Meaning |
|---|---|
| 🔴 Must | Blocking — demo breaks without this |
| 🟠 Should | Important but demo can limp along without it |
| 🔵 Nice | Polish — add if time allows |

---

---

# PROMPT BLOCK 0 — Project Context & Setup

> Paste this at the very start of your first session. It gives the agent the full project picture before any code is written.

---

```
You are a senior full-stack developer helping me build "MessMate" — a college
mess food review web app for a solo student developer (me). This is a
one-day prototype build to demo to my college's Vice Chancellor.

=== PROJECT OVERVIEW ===
App name      : MessMate
Purpose       : Students scan a QR code at the mess, rate today's lunch,
                and admin/deans/VC see a live dashboard with scores & trends.
Tech stack    : Python (Flask), HTML/CSS/Vanilla JS, Google Sheets (backend),
                Chart.js (CDN), Flask-Limiter, gspread, Render.com (hosting)
Developer     : Solo student — keep code simple, well-commented, beginner-friendly
Meal scope    : Lunch only (prototype). Breakfast/dinner are Phase 2.
Authentication: None for prototype. IP-rate limiting only (1 submit/IP/day).
Anonymity     : No student name or identity is stored anywhere. Fully anonymous.

=== FILE STRUCTURE TO CREATE ===
messmate/
├── app.py                 # Flask app — routes + logic
├── sheets.py              # Google Sheets read/write helpers
├── requirements.txt       # Python dependencies
├── .gitignore             # Must include: credentials.json, .env, __pycache__
├── credentials.json       # Google Service Account key (gitignored — user provides)
├── templates/
│   ├── form.html          # Student feedback form
│   └── dashboard.html     # Stakeholder dashboard
└── static/
    ├── style.css          # Shared mobile-first styles
    └── dashboard.js       # Chart.js chart setup

=== GOOGLE SHEETS SCHEMA ===
Tab 1 — "responses" (one row per submission):
Timestamp | Overall | Rice_Curry | Rice_Rasam | Chapati | Chapati_Gravy |
Poriyal | Sweet | Salad | Curd | Papad | Pickle | Review | Suggestion

All item columns (Rice_Curry through Pickle) are nullable — blank if student skipped.
Overall is always 1–5 (required). Review max 150 chars. Suggestion is free text.

Tab 2 — "daily_summary" (formulas, not written by Flask):
Date | Avg_Overall | Response_Count | Avg_Rice_Curry | Avg_Rice_Rasam |
Avg_Chapati | Avg_Chapati_Gravy | Avg_Poriyal | Avg_Sweet | Avg_Salad |
Avg_Curd | Avg_Papad | Avg_Pickle

=== ENVIRONMENT VARIABLES (never hardcode these) ===
GOOGLE_CREDENTIALS_JSON   Full JSON string of the service account key
SPREADSHEET_ID            Google Sheet ID from the URL
FLASK_SECRET_KEY          Random secret string

=== YOUR TASK FOR THIS SESSION ===
1. Create the full messmate/ project folder with the file structure above.
2. Create requirements.txt with: flask, gspread, google-auth, flask-limiter, gunicorn
3. Create .gitignore
4. Create sheets.py with gspread initialisation and these 4 functions:
   - append_response(data_dict)   → appends one row to "responses" tab
   - get_daily_summary()          → reads all rows from "daily_summary" tab
   - get_today_responses()        → filters today's rows from "responses"
   - get_all_suggestions()        → returns all non-blank Suggestion values
5. Create a stub app.py with Flask initialised, secret key loaded from env,
   Flask-Limiter configured, and placeholder routes for: GET /, POST /submit,
   GET /dashboard, GET /health
6. Add a README.md with setup steps for the Google Cloud service account.

Do NOT build the HTML templates yet — that is the next session.
Produce all files with full content, well-commented in plain English.
Tell me when done and list every file you created.
```

---

---

# PROMPT BLOCK 1 — Student Feedback Form

> Paste this block after Block 0 is fully complete and all backend files are created.

---

```
We are building MessMate — a college mess food review app. The backend
(app.py, sheets.py) is already done. Now build the student feedback form.

=== FILE TO CREATE: templates/form.html ===

DESIGN REQUIREMENTS:
- Mobile-first. Students open this by scanning a QR code on their phone.
- Clean, friendly UI. Use soft whites, a blue accent (#2E75B6), and emojis.
- No login, no name field. Completely anonymous.
- Single scrollable page — no multi-step wizard needed.
- Tappable targets minimum 44x44px. Body font minimum 16px.
- Page title: "MessMate — Rate Today's Lunch 🍱"

SECTION 1 — OVERALL RATING (required, blocks submit if not selected):
- Heading: "How was today's lunch overall?"
- Display 5 emoji buttons in a single row:
  😡 Terrible (value=1)  😕 Bad (value=2)  😐 Okay (value=3)
  🙂 Good (value=4)  😄 Excellent (value=5)
- JS: clicking one selects it (add a blue ring/highlight), deselects all others.
- Store selected value in hidden input: <input type="hidden" name="overall" id="overall_val">
- Submit button stays DISABLED until an overall emoji is tapped.

SECTION 2 — PER-ITEM RATINGS (all optional):
- Heading: "Rate individual items (optional)"
- Subtext: "Only rate what was served today"

RICE CARD (special — dropdown + conditional ratings):
  - Label: "🍚 Rice"
  - Dropdown (name="rice_served"): options → [ Select... | Curry | Rasam | Both ]
  - JS behaviour:
      "Curry" selected  → show one emoji row (name="rice_curry",  label="Rice + Curry")
      "Rasam" selected  → show one emoji row (name="rice_rasam",  label="Rice + Rasam")
      "Both" selected   → show TWO emoji rows (rice_curry AND rice_rasam)
      Dropdown reset    → hide all rice rating rows, clear selections

STANDARD ITEM CARDS (each has a 5-emoji rating row, all optional):
  name="chapati"        label="🫓 Chapati"
  name="chapati_gravy"  label="🫓 Chapati + Gravy / Sabzi"
  name="poriyal"        label="🥬 Poriyal"
  name="sweet"          label="🍮 Sweet / Fruits"
  name="salad"          label="🥗 Salad"
  name="curd"           label="🥛 Curd"
  name="papad"          label="🫓 Papad"
  name="pickle"         label="🫙 Pickle / Thogayal"

Each emoji rating row: same 5-emoji mutual-exclusivity JS as Section 1.
Store value in a hidden input. Unselected = empty string submitted.

SECTION 3 — TEXT REVIEW (optional):
  <textarea name="review" maxlength="150"
    placeholder="Any comments about today's lunch?"></textarea>
  Show live character counter: "X / 150"

SECTION 4 — SUGGEST A DISH (optional):
  <input type="text" name="suggestion"
    placeholder="Suggest a dish for the mess menu...">

SUBMIT BUTTON:
  - Text: "Submit Feedback 🚀"
  - Disabled until Section 1 emoji is selected.
  - On click: show loading state "Submitting..." to prevent double-tap.
  - Posts to: POST /submit

=== FILE TO CREATE: static/style.css ===
Write all CSS here (no inline styles in HTML).
Include: base reset, mobile layout, emoji button styles (selected state),
card styles, dropdown, textarea, submit button, character counter.

=== FILE TO UPDATE: app.py — POST /submit route ===
- Read all form fields from request.form
- Convert emoji ratings to integers (1–5); leave blank fields as None
- Build a data_dict matching the Google Sheets column order
- Call sheets.append_response(data_dict)
- On success: render a thank-you message ("Thanks! Your feedback was recorded.")
- On rate-limit hit: return friendly message ("Already submitted today — come back tomorrow!")
- Wrap Sheet write in try/except — show error page if Sheet is unreachable

Produce all files with full content. Tell me when done.
```

---

---

# PROMPT BLOCK 2 — Admin Dashboard

> Paste this block after Block 1 is complete and the form is working end-to-end.

---

```
We are building MessMate — a college mess food review app.
The form (form.html) and backend are complete. Now build the dashboard.

=== FILE TO CREATE: templates/dashboard.html ===

AUDIENCE: Mess caterer, Deans, Chancellor, Vice Chancellor.
DEVICE: Laptop / desktop browser (not mobile-first).
DESIGN: Clean, professional, data-forward. Use Chart.js loaded from CDN.
        Colour scheme: white background, blue (#1F4E79 / #2E75B6) accents.

SECTION 1 — TOP STAT CARDS (today's summary):
Three cards in a row:
  Card A: "Today's Average"
          Large number (1 decimal). Colour-coded background:
          score < 2.5   → red   (bg #FFEBEE  text #B71C1C)
          score 2.5–3.5 → amber (bg #FFF3E0  text #BF5700)
          score > 3.5   → green (bg #E8F5E9  text #1E6B3C)
  Card B: "Responses Today"
          Count of today's submissions (integer).
  Card C: "Today's Date"
          Formatted as: Sunday, 15 March 2026

SECTION 2 — 7-DAY TREND CHART:
- Chart.js Line chart
- X axis: last 7 dates (from daily_summary tab)
- Y axis: average overall score, range 1–5
- Dataset label: "Overall Avg Score"
- Smooth curve (tension: 0.4), blue line, filled area below
- Title: "7-Day Overall Trend"

SECTION 3 — PER-ITEM SCORES CHART:
- Chart.js Horizontal Bar chart
- Y axis labels (items, top to bottom):
  Rice + Curry, Rice + Rasam, Chapati, Chapati + Gravy,
  Poriyal, Sweet/Fruits, Salad, Curd, Papad, Pickle/Thogayal
- X axis: score 0–5
- Colour bars by score (same red/amber/green logic as stat cards)
- Show score value at end of each bar
- Skip items with no data (show as 0 or "No data")
- Title: "Today's Item Scores"

SECTION 4 — SUGGESTED DISHES LIST:
- Heading: "💡 Student Suggestions"
- Scrollable list, newest first
- Each row: suggestion text + timestamp
- If no suggestions: show "No suggestions yet."

=== FILE TO CREATE: static/dashboard.js ===
All Chart.js initialisation code goes here.
Data is injected by Flask as JSON in the template using Jinja2:
  {{ trend_data | tojson }}  and  {{ item_data | tojson }}
Parse these and feed them into Chart.js datasets.

=== FILE TO UPDATE: app.py — GET /dashboard route ===
Fetch and pass to the template:
  - trend_data   : list of {date, avg_overall} dicts (last 7 rows of daily_summary)
  - item_data    : dict of {item_name: avg_score} for today from responses tab
  - today_avg    : float (today's average overall score)
  - today_count  : int (number of responses today)
  - suggestions  : list of {text, timestamp} dicts (newest first)
  - today_date   : formatted date string
If Sheet is empty or unreachable, pass safe defaults (empty lists, zeros).

Produce all files with full content. Tell me when done.
```

---

---

# PROMPT BLOCK 3 — Testing & Hardening

> Paste this block after the dashboard is complete and visible in the browser.

---

```
We are building MessMate. The form and dashboard are complete.
Now harden the app, fix edge cases, and confirm everything works end-to-end.

=== TESTING CHECKLIST — work through each item: ===

1. FORM — OVERALL RATING GATE
   Submit the form without selecting an overall emoji.
   Expected: submit button stays disabled / form does not POST.
   Fix if broken.

2. FORM — MINIMAL SUBMISSION
   Select only the Overall emoji (value=3). Submit.
   Expected: one row appears in Google Sheet with only Overall=3 filled,
   all other item columns blank, Review blank, Suggestion blank.
   Fix if broken.

3. FORM — RICE DROPDOWN "BOTH"
   Select "Both" in the Rice dropdown. Rate Rice+Curry = 4, Rice+Rasam = 2. Submit.
   Expected: Rice_Curry=4 AND Rice_Rasam=2 both saved in the Sheet row.
   Fix if broken.

4. FORM — REVIEW CHARACTER LIMIT
   Type exactly 150 characters in the review box. Confirm counter shows "150 / 150".
   Try typing a 151st character. Confirm it is blocked.
   Fix if broken.

5. SPAM PROTECTION
   Submit the form twice from the same browser/IP within the same day.
   Expected: second attempt returns the friendly message:
   "You've already submitted feedback for today. Come back tomorrow! 😊"
   Fix if broken.

6. DASHBOARD — EMPTY STATE
   Temporarily point daily_summary to an empty range.
   Expected: dashboard loads without crashing; shows "No data yet" or zeros.
   Fix if broken. Restore after.

7. DASHBOARD — DATA ACCURACY
   After submissions in step 2 and 3, reload dashboard.
   Expected: today_avg and today_count reflect the test submissions.
   Item chart shows scores for items that were rated.
   Fix if broken.

8. MOBILE LAYOUT
   Open form in browser DevTools → mobile viewport 375px wide.
   Check: emoji buttons fit in one row, no horizontal scroll, text readable.
   Fix any layout issues.

9. SECURITY — INPUT SANITISATION
   Submit a review containing: <script>alert('xss')</script>
   Expected: saved as plain text in Sheet, NOT executed anywhere.
   If not sanitised, add html.escape() on all text inputs in POST /submit.

10. HEALTH ENDPOINT
    GET /health should return HTTP 200 and body: {"status": "ok"}
    Fix if broken.

After all 10 checks pass, output a summary of what was fixed and what passed.
```

---

---

# PROMPT BLOCK 4 — Demo Data Seeding

> Paste this block after all tests pass. Creates realistic data for the VC demo.

---

```
We are building MessMate. The app is working and tested.
Now create a data seeding script to populate the Google Sheet with realistic
demo data for the VC presentation.

=== FILE TO CREATE: seed_data.py ===

PURPOSE: Populate the "responses" tab in Google Sheets with 70 realistic rows
         spread across the last 7 days (10 rows per day).
         This makes the dashboard trend chart and per-item charts look live and real.

REQUIREMENTS:
- Use the same gspread connection from sheets.py
- Spread rows evenly: 10 per day, days = today minus 0 through 6
- Timestamps: random times between 12:00 and 14:30 for each day (lunch window)
- Overall scores: realistic bell curve — mostly 3s and 4s, some 2s and 5s, rare 1s
  Suggested distribution per 10 rows: [1×1, 2×2, 3×3, 3×4, 1×5]
- Item ratings: not every item rated in every row (50–70% fill rate per item)
  Vary scores per item — Poriyal and Pickle tend to score lower (2–3),
  Sweet scores higher (3–5), Rice scores vary 2–4.
- Review texts: include 15 varied short reviews across the 70 rows, rest blank.
  Example reviews (use these + invent similar ones):
    "Rice was a bit soggy today", "Chapati was really good!",
    "Poriyal could use more seasoning", "Sweet was excellent",
    "Overall decent meal", "Curd was fresh", "Pickle was too salty",
    "Chapati gravy was tasty", "Rice quality has improved",
    "Salad was fresh and crunchy"
- Suggestions: include these 12 suggestions distributed across different rows:
    "Puliyodarai", "Chole Bhature on Sundays", "More variety in sweet",
    "Lemon rice option", "Sambar rice", "Raita with chapati",
    "Sprouts salad", "Fruit bowl option", "Kesari on Fridays",
    "Gobi manchurian", "Tomato soup", "Papad every day"

AFTER SEEDING:
- Print a summary: "Seeded X rows across Y days"
- Remind me to manually refresh the daily_summary tab formulas in Sheets

Then instruct me to:
1. Open the Sheet and verify rows look correct
2. Check the daily_summary tab auto-populated via formulas
3. Reload /dashboard and confirm charts show populated data
```

---

---

# PROMPT BLOCK 5 — Deploy & QR Code

> Paste this block last. Gets the app live and produces the QR code for the mess board.

---

```
We are building MessMate. The app is complete, tested, and seeded with demo data.
Now deploy it to Render.com (or Railway.app) and generate the QR code.

=== STEP 1: PREPARE FOR DEPLOYMENT ===

Create / verify these files exist and are correct:

requirements.txt — must include:
  flask
  gspread
  google-auth
  flask-limiter
  gunicorn

Procfile (create if missing):
  web: gunicorn app:app

.gitignore — must include:
  credentials.json
  .env
  __pycache__/
  *.pyc
  venv/

app.py — confirm it reads credentials from environment variable, NOT from file:
  import os, json
  creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
  creds_dict = json.loads(creds_json)
  # Pass creds_dict to gspread ServiceAccountCredentials

=== STEP 2: DEPLOYMENT INSTRUCTIONS ===

Give me step-by-step instructions to:
1. Push the project to a new private GitHub repository
2. Sign up / log in to Render.com
3. Create a new Web Service connected to the GitHub repo
4. Set the build command and start command
5. Add the 3 environment variables:
     GOOGLE_CREDENTIALS_JSON  (paste full JSON string)
     SPREADSHEET_ID           (from Sheet URL)
     FLASK_SECRET_KEY         (generate a random one — provide a Python snippet)
6. Deploy and get the live HTTPS URL

=== STEP 3: QR CODE GENERATOR ===

Create a file: generate_qr.py

Requirements:
- Use the qrcode Python library (add to requirements if missing)
- Accept the live URL as a variable at the top of the file (easy to edit)
- Generate a QR code image: messmate_qr.png
- Size: large enough to scan from 30cm away
- Add a border / quiet zone of 4 modules
- Print: "QR code saved as messmate_qr.png — point it to: [URL]"

=== STEP 4: DEMO READINESS CHECKLIST ===

After deployment, walk me through these final checks:
[ ] Scan the QR code on a real phone — form opens correctly
[ ] Submit a test rating from the phone — appears in Sheet
[ ] Open /dashboard on a laptop — trend chart and item chart render
[ ] Dashboard shows today's average and response count
[ ] Suggestions list shows the seeded suggestions
[ ] All emoji render correctly on both Android and the laptop
[ ] Page title shows "MessMate" in the browser tab

When all checks pass, output:
"MessMate is live at: [URL]"
"Dashboard at: [URL]/dashboard"
"QR code saved as messmate_qr.png — print and stick on the mess notice board."
"You are ready for the VC demo. 🎉"
```

---

---

## Quick Reference — Key Specs for the Agent

| Spec | Value |
|---|---|
| App name | MessMate |
| Form route | `GET /` → form.html |
| Submit route | `POST /submit` → writes to Sheet |
| Dashboard route | `GET /dashboard` → dashboard.html |
| Health route | `GET /health` → `{"status": "ok"}` |
| Rating scale | 1 (😡 Terrible) → 5 (😄 Excellent) |
| Rice dropdown options | Curry / Rasam / Both |
| Menu items (10 total) | Rice, Chapati, Chapati+Gravy, Poriyal, Sweet, Salad, Curd, Papad, Pickle/Thogayal |
| Required field | Overall rating only — all others optional |
| Review limit | 150 characters max |
| Spam rule | 1 submission per IP per day (Flask-Limiter) |
| Data store | Google Sheets — gspread library |
| Charts library | Chart.js via CDN (no install) |
| Hosting | Render.com or Railway.app (free tier) |
| Score colour: 🔴 red | `< 2.5` → bg `#FFEBEE` text `#B71C1C` |
| Score colour: 🟠 amber | `2.5–3.5` → bg `#FFF3E0` text `#BF5700` |
| Score colour: 🟢 green | `> 3.5` → bg `#E8F5E9` text `#1E6B3C` |

---

## Troubleshooting — Tell the agent exactly this

| Problem | What to paste |
|---|---|
| gspread auth error | *"Fix the gspread auth to use GOOGLE_CREDENTIALS_JSON env variable as a JSON string, not a file path."* |
| Sheet write fails | *"The service account email must be added as Editor on the Google Sheet. Show me the email to add."* |
| Charts not rendering | *"Chart.js is not loading. Check the CDN URL is correct and JSON data is passed to the template."* |
| Emoji rating not submitting | *"The hidden input for [item] is not being set by the JS. Debug the emoji selection handler."* |
| Rate limit not working | *"Flask-Limiter is not blocking the second submission. Check the limiter is initialised with app and the decorator is on POST /submit."* |
| Deploy fails | *"The Render build is failing. Check requirements.txt includes gunicorn and Procfile says: web: gunicorn app:app"* |

---

*MessMate Build Prompt · PRD v1.0 + TSD v1.0 · March 2026*