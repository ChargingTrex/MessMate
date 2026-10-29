<!-- converted from MessMate_TSD.docx -->

MessMate
College Food Review & Feedback Platform
Technical Specification Document (TSD)
Version 1.0  |  Prototype Release  |  March 2026
| Field | Details |
| --- | --- |
| Document Title | MessMate — TSD v1.0 |
| Author | Solo Developer (Student) |
| Tech Stack | Python (Flask), HTML/CSS/JS, Google Sheets API |
| Hosting | Render.com or Railway.app (free tier) |
| Database | Google Sheets (prototype backend) |
| Phase | Phase 1 — Prototype |

# 1.  System Architecture
MessMate follows a lightweight 3-tier architecture optimised for a solo developer prototype. There is no traditional database — Google Sheets acts as both the datastore and a live, shareable audit trail that can be demonstrated directly to stakeholders.

| ARCHITECTURE OVERVIEW Student Phone (QR Code → Browser URL) ↓ Python + Flask (Web Server — Render / Railway) ↓ POST (form submit) ↑ GET (dashboard read) Google Sheets API (Data Store) ↓ Dashboard Page (HTML + Chart.js — read-only) |
| --- |

# 2.  Technology Stack
| Layer | Technology | Justification |
| --- | --- | --- |
| Web Framework | Python — Flask | Lightweight, well-documented, easy solo deployment |
| Frontend | HTML5 + CSS3 + Vanilla JS | No build tooling needed; fast mobile load |
| Charts (Dashboard) | Chart.js (CDN) | No install; excellent bar/line chart support |
| Data Store | Google Sheets (gspread library) | Visual backend for demos; shareable; free |
| Auth (Google API) | Google Service Account (JSON key) | Secure server-side writes to Sheets |
| Hosting | Render.com or Railway.app | Free tier; supports Python; HTTPS out of the box |
| QR Code | qrcode Python library or qr.io | Generate QR pointing to hosted URL |
| Spam Protection | Flask-Limiter (IP-based) | 1 submission per IP per day; no login needed |

# 3.  Project File Structure
messmate/
├── app.py                    # Flask app — routes, logic
├── sheets.py                 # Google Sheets read/write helpers
├── requirements.txt          # Python dependencies
├── credentials.json          # Google Service Account key (gitignored)
├── templates/
│   ├── form.html             # Student feedback form
│   └── dashboard.html        # Admin/stakeholder dashboard
└── static/
├── style.css             # Shared styles (mobile-first)
└── dashboard.js          # Chart.js initialisation

# 4.  Google Sheets Data Schema
One Google Sheet with two tabs:

## 4.1  Tab 1 — responses
Every form submission writes one row. All item rating columns are nullable (blank if student skipped).

| Column | Type | Source | Notes |
| --- | --- | --- | --- |
| Timestamp | DateTime | Server auto | Python datetime.now() — not user-supplied |
| Overall | Integer 1–5 | Section 1 | Required field |
| Rice_Curry | Integer 1–5 | Section 2 dropdown | Null if Rasam-only or skipped |
| Rice_Rasam | Integer 1–5 | Section 2 dropdown | Null if Curry-only or skipped |
| Chapati | Integer 1–5 | Section 2 | Null if skipped |
| Chapati_Gravy | Integer 1–5 | Section 2 | Null if skipped |
| Poriyal | Integer 1–5 | Section 2 | Null if skipped |
| Sweet | Integer 1–5 | Section 2 | Null if skipped |
| Salad | Integer 1–5 | Section 2 | Null if skipped |
| Curd | Integer 1–5 | Section 2 | Null if skipped |
| Papad | Integer 1–5 | Section 2 | Null if skipped |
| Pickle | Integer 1–5 | Section 2 | Null if skipped |
| Review | String ≤150 | Section 3 | Null if skipped |
| Suggestion | String | Section 4 | Null if skipped; anonymous |

## 4.2  Tab 2 — daily_summary (auto-computed via Sheets formulas)
This tab holds AVERAGEIF/COUNTIF formulas aggregating Tab 1 by date. The dashboard reads from this tab for performance.

| Column | Formula (example) |
| --- | --- |
| Date | Unique date values extracted from Timestamp |
| Avg_Overall | =AVERAGEIF(responses!A:A, A2, responses!B:B) |
| Response_Count | =COUNTIF(responses!A:A, A2) |
| Avg_Rice_Curry | =AVERAGEIF(responses!A:A, A2, responses!C:C) |
| Avg_Rice_Rasam | =AVERAGEIF(responses!A:A, A2, responses!D:D) |
| [... per item ...] | Same pattern for all 10 items |

# 5.  Flask API Routes
| Method | Route | Description | Template |
| --- | --- | --- | --- |
| GET | / | Serves the student feedback form | form.html |
| POST | /submit | Receives form data, validates, writes row to Sheets, returns success page | — |
| GET | /dashboard | Serves the stakeholder dashboard; fetches aggregated data from Sheets | dashboard.html |
| GET | /health | Health check endpoint for hosting platform uptime monitoring | — |

# 6.  Frontend Form Logic
## 6.1  Rice Dropdown Behaviour
The Rice card uses dynamic JavaScript to render rating inputs based on dropdown selection:

User selects 'Curry'   → One emoji rating row appears (Rice_Curry)
User selects 'Rasam'   → One emoji rating row appears (Rice_Rasam)
User selects 'Both'    → Two emoji rating rows appear (Rice_Curry + Rice_Rasam)
Default (no selection) → No rating rows shown; both fields submit as empty

## 6.2  Emoji Rating Widget
Each item rating renders as 5 emoji buttons in a horizontal row. JS handles mutual exclusivity (selecting one deselects others). Selected emoji gets a highlighted background ring. Value is stored in a hidden input field per item.

## 6.3  Form Validation (client-side)
- Overall rating is required — submit button disabled until one emoji is selected
- Text review enforces 150-character max with live counter
- All other fields are optional — no blocking validation

## 6.4  Spam Protection (server-side)
- Flask-Limiter applied to POST /submit
- Rule: 1 request per IP per day (resets at midnight IST)
- On duplicate: returns friendly message — 'You have already submitted feedback for today. Come back tomorrow!'
- Note: IP-based limiting is prototype-grade. Phase 2 will use college email auth.

# 7.  Dashboard Technical Spec
## 7.1  Data Fetching
On each GET /dashboard request, the Flask server fetches fresh data from Google Sheets using gspread. Data is passed to the Jinja2 template as JSON and injected into Chart.js datasets on page load.

## 7.2  Charts
| Chart | Library | Type | Data |
| --- | --- | --- | --- |
| 7-Day Overall Trend | Chart.js | Line chart | daily_summary — last 7 rows |
| Per-Item Avg Scores | Chart.js | Horizontal bar chart | Today's column averages from responses tab |

## 7.3  Stat Cards
- Today's Average: Calculated server-side; colour logic: < 2.5 = red, 2.5–3.5 = amber, > 3.5 = green
- Response Count: COUNT of today's rows in responses tab
- Suggested Dishes: All non-null values from Suggestion column, displayed newest-first

# 8.  Deployment Plan
## 8.1  Environment Variables
The following must be set as environment secrets in the hosting platform (never committed to git):

GOOGLE_CREDENTIALS_JSON   — Full contents of credentials.json (service account)
SPREADSHEET_ID            — Google Sheet ID from the URL
FLASK_SECRET_KEY          — Random string for session security

## 8.2  Step-by-Step Deployment
- Create a Google Cloud project and enable Google Sheets API
- Create a Service Account, download credentials.json
- Create the Google Sheet, share it with the service account email
- Push code to a GitHub repository (credentials.json in .gitignore)
- Connect GitHub repo to Render.com or Railway.app
- Set environment variables in the hosting dashboard
- Deploy — platform auto-builds from requirements.txt
- Generate QR code pointing to the live HTTPS URL
- Seed 50–80 realistic demo responses directly into the Sheet

## 8.3  requirements.txt
flask
gspread
google-auth
flask-limiter
gunicorn

# 9.  Security Considerations
| Risk | Mitigation | Phase |
| --- | --- | --- |
| Spam / duplicate submissions | IP-rate limiting via Flask-Limiter (1/day) | Phase 1 |
| Credentials exposure | Service account key stored as env variable, never in git | Phase 1 |
| Dashboard unauthorised access | Obscurity via non-guessable URL path for prototype | Phase 1 |
| Dashboard unauthorised access | HTTP Basic Auth or token-based login | Phase 2 |
| Student identity | No PII collected; anonymous submission design | Phase 1 |
| Data manipulation | Sheets write-only via service account; direct Sheet access limited | Phase 1 |
| Injection attacks | All form inputs sanitised server-side before Sheets write | Phase 1 |

# 10.  Recommended Build Order
| Step | Task | Estimated Time |
| --- | --- | --- |
| 1 | Set up Flask app skeleton + Google Sheets API connection; test one row write | 2–3 hrs |
| 2 | Build form.html — overall emoji rating + basic mobile layout | 2–3 hrs |
| 3 | Add per-item cards + Rice dropdown JS logic | 2–3 hrs |
| 4 | Add text review + suggestion box; wire full POST /submit | 1–2 hrs |
| 5 | Build dashboard.html — stat cards + Chart.js charts | 3–4 hrs |
| 6 | Add IP rate limiting + error/success pages | 1 hr |
| 7 | Deploy to Render/Railway; test end-to-end on mobile | 1–2 hrs |
| 8 | Seed demo data into Sheet; generate QR code; print | 1 hr |

Total estimated build time: 13–19 hours for a clean, demo-ready prototype.