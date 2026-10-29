<!-- converted from MessMate_Checklist.docx -->

MessMate
Build Checklist — Prototype Phase 1
Cross-referenced with PRD v1.0 & TSD v1.0  |  March 2026
| How to use this checklist Work through phases in order — each phase builds on the previous one. Replace ☐ with ☑ (or ✓) when a task is done. The Reference / Notes column maps each task back to the PRD or TSD section. Priority: Must = blocking (demo breaks without it), Should = important, Nice = bonus. All Phase 1 tasks should be complete before the VC demo. |
| --- |

| Must | Blocking — prototype is broken or undemonstrable without this task |
| --- | --- |
| Should | Important but demo can limp along without it; complete before launch |
| Nice | Polish / bonus — add if time allows, skip if under pressure |

| PHASE 0 · PROJECT SETUP Environment, credentials, and repository — do this before writing any app code |
| --- |

| 🗂️ Repository & Environment |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create a new project folder: messmate/ | TSD §3 — file structure | Must |
| ☐ | Initialise a git repository (git init) | Good practice | Must |
| ☐ | Create .gitignore — add credentials.json, __pycache__, .env | TSD §8.1 — never commit secrets | Must |
| ☐ | Create virtual environment: python -m venv venv | TSD §8.5 | Must |
| ☐ | Activate venv and install dependencies from requirements.txt | TSD §8.5 | Must |
| ☐ | Create requirements.txt with: flask, gspread, google-auth, flask-limiter, gunicorn | TSD §8.5 | Must |
| ☐ | Push initial commit to GitHub (private repo) | TSD §8.2 step 4 | Must |

| 🔑 Google Cloud & Sheets Setup |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create a new Google Cloud project named 'MessMate' | TSD §8.2 step 1 | Must |
| ☐ | Enable Google Sheets API on the Cloud project | TSD §8.2 step 1 | Must |
| ☐ | Create a Service Account; grant it Editor role | TSD §8.2 step 2 | Must |
| ☐ | Download credentials.json — save to project root (gitignored) | TSD §8.2 step 2 | Must |
| ☐ | Create a new Google Sheet named 'MessMate_Responses' | TSD §8.2 step 3 | Must |
| ☐ | Share the Sheet with the service account email (Editor access) | TSD §8.2 step 3 | Must |
| ☐ | Add Tab 1: rename to 'responses'; add all 14 column headers | TSD §4.1 — full column list | Must |
| ☐ | Add Tab 2: rename to 'daily_summary'; add AVERAGEIF formulas | TSD §4.2 — formula reference | Must |
| ☐ | Copy Sheet ID from URL; save as SPREADSHEET_ID env variable | TSD §8.1 | Must |

| PHASE 1 · FLASK BACKEND app.py, sheets.py, routes — the server that ties everything together |
| --- |

| 🐍 Core Flask App (app.py) |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create app.py with Flask app initialisation | TSD §5 — routes overview | Must |
| ☐ | Add GET / → renders form.html template | TSD §5 | Must |
| ☐ | Add POST /submit → receives form data, validates, writes to Sheets, returns success | TSD §5 | Must |
| ☐ | Add GET /dashboard → fetches Sheet data, passes to dashboard.html | TSD §5 | Must |
| ☐ | Add GET /health → returns 200 OK (for hosting uptime checks) | TSD §5 | Should |
| ☐ | Set FLASK_SECRET_KEY from environment variable | TSD §8.1 | Must |
| ☐ | Add server-side sanitisation of all POST inputs before Sheets write | TSD §9 — injection risk | Must |
| ☐ | Configure Flask-Limiter: 1 submission per IP per day on /submit | TSD §6.4 | Must |
| ☐ | Return user-friendly message on duplicate submission (rate limit hit) | TSD §6.4 | Must |
| ☐ | Add success page or redirect after valid form submission | Good UX | Must |

| 📊 Google Sheets Helper (sheets.py) |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create sheets.py — initialise gspread with service account credentials | TSD §2 — gspread lib | Must |
| ☐ | Write function: append_response(data_dict) → appends one row to 'responses' tab | TSD §4.1 | Must |
| ☐ | Write function: get_daily_summary() → reads all rows from 'daily_summary' tab | TSD §4.2 | Must |
| ☐ | Write function: get_today_responses() → filters today's rows from 'responses' | TSD §7.3 | Must |
| ☐ | Write function: get_all_suggestions() → returns non-null Suggestion column values | TSD §7.3 | Must |
| ☐ | Test each function independently — confirm data lands in Sheet correctly | TSD §10 step 1 | Must |

| PHASE 2 · STUDENT FEEDBACK FORM templates/form.html + static/style.css — mobile-first, QR-accessible |
| --- |

| 📐 Layout & Mobile Foundation |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create templates/form.html with responsive meta viewport tag | PRD §5, TSD §6 — mobile-first | Must |
| ☐ | Create static/style.css — base mobile styles, min tap target 44x44px | PRD §7 — accessibility | Must |
| ☐ | Add MessMate header/logo area with college name | VC demo polish | Should |
| ☐ | Ensure font sizes are readable on small screens (min 16px body) | PRD §7 — accessibility | Must |
| ☐ | Test layout on mobile viewport (375px width) in browser DevTools | PRD §7 — mobile compatibility | Must |

| 😄 Section 1 — Overall Rating (Required) |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Display 5 emoji buttons: 😡 😕 😐 🙂 😄 in a horizontal row | PRD §5.1 — emoji scale | Must |
| ☐ | JS: clicking an emoji selects it (highlight ring) and deselects others | PRD §5.1 — mutual exclusivity | Must |
| ☐ | Store selected value (1–5) in a hidden input field | TSD §4.1 — Overall column | Must |
| ☐ | Submit button disabled until an overall emoji is selected | PRD §5 — required field | Must |
| ☐ | Label each emoji clearly (Terrible / Bad / Okay / Good / Excellent) | PRD §5.1 | Should |

| 🍚 Section 2 — Per-Item Ratings (Optional) |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Render Rice card with dropdown: options Curry / Rasam / Both | PRD §5.1 — Rice dropdown spec | Must |
| ☐ | JS: selecting 'Curry' shows one emoji rating row (Rice_Curry) | TSD §6.1 | Must |
| ☐ | JS: selecting 'Rasam' shows one emoji rating row (Rice_Rasam) | TSD §6.1 | Must |
| ☐ | JS: selecting 'Both' shows two emoji rating rows (Curry + Rasam) | TSD §6.1 | Must |
| ☐ | JS: changing dropdown resets previously selected rice ratings | TSD §6.1 — clean state | Must |
| ☐ | Render Chapati card with emoji rating (1–5) | PRD §5.1 — menu item list | Must |
| ☐ | Render Chapati + Gravy/Sabzi card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Poriyal card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Sweet / Fruits card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Salad card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Curd card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Papad card with emoji rating | PRD §5.1 | Must |
| ☐ | Render Pickle / Thogayal card with emoji rating | PRD §5.1 — Tamil Nadu specific | Must |
| ☐ | Each item card: emoji rating uses same mutual-exclusivity JS as Section 1 | TSD §6.2 | Must |
| ☐ | All per-item fields submit as empty/null if user skips them | TSD §4.1 — nullable columns | Must |

| 💬 Section 3 & 4 — Review + Suggestion |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Add text review textarea — placeholder: 'Any comments about today's lunch?' | PRD §5.1 Section 3 | Must |
| ☐ | Enforce 150-character max on review field with live character counter | PRD §5.1 — 150 char limit | Must |
| ☐ | Add dish suggestion input field with placeholder text | PRD §5.1 Section 4 | Must |
| ☐ | Confirm no user identity / name field anywhere on the form | PRD §5.1 — anonymous | Must |
| ☐ | Add submit button with loading state (prevent double-submit) | Good UX | Should |

| PHASE 3 · DASHBOARD templates/dashboard.html + Python Matplotlib Rendering — read-only stakeholder view |
| --- |

| 📈 Stat Cards (Today's Summary) |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Display 'Today's Average Score' as a large number (1 decimal place) | PRD §6, TSD §7.3 | Must |
| ☐ | Colour-code average: red < 2.5, amber 2.5–3.5, green > 3.5 | TSD §7.3 — colour logic | Must |
| ☐ | Display response count alongside the average score | PRD §6 | Must |
| ☐ | Display today's date prominently on the dashboard | Context for stakeholders | Must |

| 📉 Charts |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Add Matplotlib via CDN in dashboard.html | TSD §2 — Matplotlib CDN | Must |
| ☐ | Create Python Matplotlib Rendering for chart initialisation code | TSD §3 — file structure | Must |
| ☐ | Build 7-day trend line chart (x = date, y = avg overall score) | PRD §6, TSD §7.2 | Must |
| ☐ | Build per-item horizontal bar chart (one bar per menu item) | PRD §6, TSD §7.2 | Must |
| ☐ | Pass aggregated data from Flask to charts as JSON in template | TSD §7.1 | Must |
| ☐ | Handle empty data gracefully (show 'No data yet' placeholder) | Edge case for fresh deploy | Should |

| 💡 Suggestions List |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Display all dish suggestions as a scrollable list | PRD §6 | Must |
| ☐ | Show suggestions newest-first (reverse chronological) | TSD §7.3 | Must |
| ☐ | Show timestamp alongside each suggestion | PRD §6 | Should |
| ☐ | Show 'No suggestions yet' message when list is empty | Edge case | Should |

| PHASE 4 · TESTING & QUALITY End-to-end checks before deployment |
| --- |

| 🧪 Functional Testing |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Submit form with only Overall rating — confirm row appears in Sheet | TSD §5 POST /submit | Must |
| ☐ | Submit form with all fields filled — confirm all columns populate | TSD §4.1 | Must |
| ☐ | Select Rice dropdown 'Both' — confirm two separate scores saved | TSD §6.1 | Must |
| ☐ | Submit twice from same IP — confirm second attempt is blocked | TSD §6.4 | Must |
| ☐ | Submit 150-char review — confirm it saves; try 151-char — confirm it's blocked | PRD §5.1 | Must |
| ☐ | Check dashboard loads and shows correct averages after test submissions | PRD §6 | Must |
| ☐ | Confirm no name or identity data is stored anywhere in the Sheet | PRD §5.1 — anonymous | Must |
| ☐ | Test GET /health — confirm 200 OK response | TSD §5 | Should |

| 📱 Mobile & Browser Testing |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Test form on real Android phone (Chrome) — layout, tap targets | PRD §7 — mobile compatibility | Must |
| ☐ | Test form on iPhone/Safari if available | PRD §7 | Should |
| ☐ | Confirm form completes in under 60 seconds (time yourself) | PRD §7 — < 60s target | Must |
| ☐ | Test dashboard on a laptop/desktop browser for VC demo | PRD §7 | Must |
| ☐ | Verify all emoji render correctly across Android and iOS | Cross-platform | Must |

| PHASE 5 · DEPLOYMENT & DEMO PREP Go live, seed data, generate QR — the final stretch before the VC pitch |
| --- |

| 🚀 Hosting & Deployment |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Create account on Render.com or Railway.app | TSD §8.2 step 5 | Must |
| ☐ | Connect GitHub repository to the hosting platform | TSD §8.2 step 5 | Must |
| ☐ | Set all 3 environment variables: GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID, FLASK_SECRET_KEY | TSD §8.1 | Must |
| ☐ | Trigger first deploy — confirm build succeeds (requirements.txt auto-install) | TSD §8.2 step 7 | Must |
| ☐ | Visit the live HTTPS URL — confirm form loads on mobile | TSD §8.2 step 7 | Must |
| ☐ | Submit a test entry from the live URL — confirm it lands in Sheet | End-to-end production test | Must |
| ☐ | Visit /dashboard on live URL — confirm charts render | End-to-end production test | Must |
| ☐ | Note the dashboard URL — share with caterer/deans separately from the form QR | PRD §4 | Should |

| 🌱 Demo Data Seeding |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Seed 50–80 realistic response rows directly into the 'responses' Sheet tab | PRD §8 — demo target | Must |
| ☐ | Spread seed data across the last 7 days (for the trend line to show) | TSD §7.2 — 7-day chart | Must |
| ☐ | Include varied scores (not all 5s) — make it look authentic | VC credibility | Must |
| ☐ | Add 10+ dish suggestions to the Suggestion column | PRD §8 — suggestions target | Must |
| ☐ | Verify daily_summary tab formulas update correctly after seeding | TSD §4.2 | Must |
| ☐ | Confirm dashboard shows non-zero averages and the trend line is populated | Demo readiness | Must |

| 📲 QR Code & Demo Materials |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | Generate QR code pointing to the live form URL (qrcode lib or qr.io) | TSD §8.2 step 8 | Must |
| ☐ | Test QR scan on a phone — confirm it opens the form correctly | Physical demo test | Must |
| ☐ | Print QR code — A5 or A4 size — for mess notice board display | VC demo prop | Must |
| ☐ | Prepare the 3-sentence pitch: problem, solution, data | PRD §1 — problem statement | Must |
| ☐ | Open dashboard on a laptop ready to show the VC during the pitch | Demo flow | Must |
| ☐ | Test the full demo flow end-to-end: scan QR → fill form → show dashboard update | Final dry run | Must |

| PHASE 6 · POST-DEMO — PHASE 2 BACKLOG Items deliberately out of scope for prototype — revisit after VC approval |
| --- |

| 🔭 Phase 2 Backlog Items |
| --- |

| ✓ | Task | Reference / Notes | Priority |
| --- | --- | --- | --- |
| ☐ | College email / roll number authentication (replace IP limiting) | PRD §3 — scope table Phase 2 | Nice |
| ☐ | Time-locked submission window (12pm–3pm lunch window only) | PRD §3 | Nice |
| ☐ | Admin panel: update/manage menu items without touching the Sheet | PRD §3 | Nice |
| ☐ | Breakfast and Dinner modules (hostelers only) | PRD §4.1 — future meals | Nice |
| ☐ | Dashboard HTTP Basic Auth or token login for stakeholder access | TSD §9 Phase 2 security | Nice |
| ☐ | Weekly summary shareable card (WhatsApp-friendly PNG) | PRD §3 | Nice |
| ☐ | Suggestion acknowledgement workflow ('Noted by mess committee') | PRD discussion — retention fix | Nice |
| ☐ | Participation streak / daily nudge feature | PRD discussion | Nice |
| ☐ | 'Better than yesterday?' delta indicator on dashboard | PRD discussion | Nice |
| ☐ | Data export (CSV) from dashboard for administration | PRD §10 — out of scope P1 | Nice |

| PROGRESS TRACKER Phase 0–1 Setup & Backend __ / __ tasks done Phase 2 Student Form __ / __ tasks done Phase 3 Dashboard __ / __ tasks done Phase 4–5 Test & Deploy __ / __ tasks done |
| --- |