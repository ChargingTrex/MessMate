# MessMate — College Mess Food Review App 🍱

A web app for students to anonymously rate their daily mess lunch. Admins, deans, and the VC get a live dashboard with scores, trends, and suggestions.

## Tech Stack

- **Backend**: Python (Flask), gspread, Google Sheets
- **Frontend**: HTML/CSS/Vanilla JS, Chart.js (CDN)
- **Rate Limiting**: Flask-Limiter (1 submission/IP/day)
- **Hosting**: Render.com (free tier)

## Features

- 📱 Mobile-first student feedback form (QR code scannable)
- 😡😕😐🙂😄 Emoji-based overall + per-item ratings
- 📊 Admin dashboard with trend charts and item-level analytics
- 💡 Student dish suggestion board
- 🔒 Dashboard protected by secret token
- 🛡️ Rate limiting prevents spam (1 submit per IP per day)
- 🔐 Fully anonymous — no student identity stored
- 🍽️ **Student home page** (`/home`) — today's breakfast, lunch and dinner menu
  with a one-tap reaction per meal: good, bad or skipped, plus a suggestion
- 📝 **Menu editor** — publish the week from `/admin/menu`, or type straight into
  the `menu` tab; both write the same rows
- 🍽️ **Food Committee module** — member login, a five-dimension review page
  (taste, quality, variety, hygiene, menu), and a separate committee dashboard
- 👥 **Admin member management UI** — add, bulk-add, rotate, and reset passwords
  from the browser, with server-generated one-time credentials

## Quick Start (Local Development)

### 1. Prerequisites

- Python 3.8+
- A Google Cloud service account with Sheets API access
- A Google Sheet with the correct schema (see below)

### 2. Google Cloud Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts**
5. Click **Create Service Account**
   - Name: `messmate-backend`
   - Role: **Editor** (or custom role with Sheets + Drive access)
6. Click on the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**
7. Download the JSON file and save it as `credentials.json` in the project root
8. Open your Google Sheet → Click **Share** → Add the service account email (from the JSON file's `client_email` field) with **Editor** access

### 3. Google Sheet Schema

Create a Google Sheet with two tabs:

**Tab 1: `responses`** (headers in row 1):
```
Timestamp | Overall | Rice_Curry | Rice_Rasam | Chapati | Chapati_Gravy | Poriyal | Sweet | Salad | Curd | Papad | Pickle | Review | Suggestion
```

**Tab 2: `daily_summary`** (headers in row 1):
```
Date | Avg_Overall | Response_Count | Avg_Rice_Curry | Avg_Rice_Rasam | Avg_Chapati | Avg_Chapati_Gravy | Avg_Poriyal | Avg_Sweet | Avg_Salad | Avg_Curd | Avg_Papad | Avg_Pickle
```

**Tab 3: `committee_members`** (headers in row 1):
```
Email | Name | Password_Hash | Active | Must_Change_Password | Term_Start | Term_End | Created_At
```

**Tab 4: `committee_reviews`** (headers in row 1):
```
Timestamp | Date | Member_Email | Member_Name | Taste | Quality | Variety | Hygiene | Menu | Review
```

**Tab 5: `menu`** (headers in row 1):
```
Date | Breakfast | Lunch | Dinner
```

**Tab 6: `meal_ratings`** (headers in row 1):
```
Timestamp | Date | Meal | Rating | Suggestion
```

> Headers must match **exactly** — `get_all_records()` maps row 1 to dict keys,
> so a rename silently breaks every lookup. Run `python manage_committee.py list`
> to validate them.
>
> Set the `Date` column of `committee_reviews` to **Plain Text** formatting.
> Google Sheets reformats date-looking cells, and all committee filtering reads
> that column as a literal `YYYY-MM-DD` string.
>
> `Email` must stay in column A of `committee_members`, and `Date` in column A
> of `menu` — roster and menu edits find the row by scanning that column.

### 4. Environment Variables

Create a `.env` file in the project root:

```env
FLASK_SECRET_KEY=your-random-secret-key-here
SPREADSHEET_ID=your-google-sheet-id-from-url
DASHBOARD_TOKEN=vc2026

# Food Committee module
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$...      # see below
COMMITTEE_EMAIL_DOMAIN=saiuniversity.edu.in   # optional allowlist; any domain if unset
SESSION_COOKIE_SECURE=true                    # set in production (HTTPS only)
```

Generate the admin password hash:
```bash
python manage_committee.py hash-admin-password
```

The password itself is never stored — keep it in a password manager. Without
`ADMIN_PASSWORD_HASH` set, admin login fails closed and the roster UI is
unreachable.

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Get the Spreadsheet ID from the Google Sheet URL:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_IS_HERE/edit
```

### 5. Install & Run

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the dev server
python app.py
```

Open http://localhost:5000 in your browser.

### 6. Access the Dashboard

```
http://localhost:5000/dashboard?token=vc2026
```

### 7. Seed Demo Data

```bash
python seed_data.py
```

This populates 70 rows across 7 days for a realistic demo.

## Deployment (Render.com)

See [MessMate Hosting Guide](MessMate_Hosting_Guide.md) for detailed deployment instructions.

Quick steps:
1. Push to a private GitHub repo
2. Create a Render.com Web Service → connect the repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables:
   - `GOOGLE_CREDENTIALS_JSON` — full JSON string of the service account key
   - `SPREADSHEET_ID` — from the Google Sheet URL
   - `FLASK_SECRET_KEY` — generated secret
   - `DASHBOARD_TOKEN` — e.g. `vc2026`

## File Structure

```
messmate/
├── app.py                 # Flask app — routes + logic
├── sheets.py              # Google Sheets read/write helpers
├── requirements.txt       # Python dependencies
├── Procfile               # For Render.com deployment
├── .gitignore             # Ignores: credentials.json, .env, __pycache__
├── auth.py                # Session auth, password hashing, access decorators
├── csrf.py                # CSRF tokens for authenticated POSTs
├── seed_data.py           # Demo data seeding script
├── manage_committee.py    # Break-glass roster CLI (admin hash, add, list)
├── generate_qr.py         # QR code generator for the mess poster
├── CONTRIBUTING.md        # Architecture, conventions, how to run the tests
├── templates/
│   ├── home.html              # Student home — menu + quick reactions
│   ├── admin_menu.html        # Menu editor
│   ├── form.html              # Student feedback form
│   ├── thanks.html            # Post-submission thank-you page
│   ├── dashboard.html         # Stakeholder dashboard
│   ├── committee_login.html   # Committee member login
│   ├── committee_password.html# Forced first-login password change
│   ├── committee_form.html    # Five-dimension rating page
│   ├── committee_thanks.html  # Confirmation / already-submitted
│   ├── committee_dashboard.html # Committee analytics
│   ├── admin_login.html       # Admin login
│   └── admin_members.html     # Member management UI
├── test/
│   └── test_committee.py  # Credential-free verification harness
└── static/
    ├── style.css                # Shared mobile-first styles
    ├── dashboard.js             # Student dashboard charts
    ├── committee.js             # Committee rating widget
    └── committee_dashboard.js   # Committee dashboard charts
```

## Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Student feedback form |
| `/submit` | POST | Process submission (1/IP/day rate limit) |
| `/thanks` | GET | Thank-you page |
| `/dashboard?token=TOKEN` | GET | Admin dashboard (403 without token) |
| `/health` | GET | Health check → `{"status": "ok"}` |
| `/home` | GET | Today's menu with a one-tap reaction per meal |
| `/home/rate` | POST | Record good / bad / skip (3 per IP per day) |
| `/admin/menu` | GET | Week-at-a-glance menu editor |
| `/admin/menu/save` | POST | Publish one day's menu |
| `/committee/login` | GET, POST | Committee member login |
| `/committee/logout` | POST | Clear member session |
| `/committee/password` | GET, POST | Forced password change at first sign-in |
| `/committee` | GET | Rating page (5 dimensions + review) |
| `/committee/submit` | POST | Store one review (1 per member per day) |
| `/committee/thanks` | GET | Confirmation |
| `/admin/login` | GET, POST | Admin login (required for roster changes) |
| `/admin/logout` | POST | Clear admin session |
| `/admin/members` | GET | Roster table, add + bulk-add forms |
| `/admin/members/add` | POST | Create one member |
| `/admin/members/bulk` | POST | Create many from a pasted list |
| `/admin/members/update` | POST | Activate / deactivate / reset password |
| `/dashboard/committee` | GET | Committee dashboard (admin session or token) |

### Access levels

| Credential | Can do | Cannot do |
|---|---|---|
| `?token=` in the URL | Open both read-only dashboards | Touch the roster |
| Admin session (`/admin/login`) | Everything, including member management | — |
| Member session | Submit one review per day | See any dashboard |

The split is deliberate: a query-string token leaks into browser history,
`Referer` headers, and hosting access logs. That is tolerable for a read-only
page but not for one that can create accounts, so **every roster mutation
requires a real admin session**.

## Notes

- **Rate limiting**: Uses in-memory storage. Resets on server restart (acceptable for prototype on Render's free tier).
- **Anonymity**: No student name, email, or identity is ever collected or stored.
- **Timestamp format**: `YYYY-MM-DD HH:MM:SS` everywhere. Never change this — date filtering depends on it.

## The three feedback layers

MessMate asks for feedback three ways, and **never mixes their numbers** — a
tally of taps, a mean of 1–5 dish scores and a committee review measure
different things from different populations.

| Surface | Who | What it asks |
|---|---|---|
| `/home` | any student, no login | One tap per meal: good / bad / skip, plus a suggestion |
| `/` | any student, no login | Per-dish 1–5 ratings, a review and a suggestion |
| `/committee` | committee members | Taste, quality, variety, hygiene, menu — attributed |

The home page is the low-effort one, and the one most students will actually
use; it links through to the per-dish form for anyone with more to say.

## Publishing the menu

Two equally valid editors, both writing the same rows to the `menu` tab:

1. **The spreadsheet** — type straight into the `menu` tab.
2. **The admin UI** at `/admin/menu` — a week at a glance, one row per day,
   each saved independently. Needs an admin session.

Items are comma-separated (`Idli, Sambar, Coconut Chutney`); newlines work too.
A blank meal shows as "Menu not published yet" rather than an empty card.

Skips are counted but kept out of a meal's score, which is `good` as a share of
those who actually ate — a student who never turned up is telling you about
attendance, not about the food.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the conventions behind all of this.

## Food Committee

### Setting up the first members

1. Generate and set `ADMIN_PASSWORD_HASH` (above), then restart the app.
2. Sign in at `/admin/login` and open `/admin/members`.
3. Add members individually, or paste a whole rotation into the bulk box as
   `Name, email` per line.
4. Copy the generated one-time passwords **immediately** — only the hash is
   stored, so they cannot be shown again. A reset is the only way back.
5. Each member is forced to choose their own password at first sign-in.

### Rotating the committee

Deactivate the outgoing members and bulk-add the incoming ones. There is no
delete: deactivation preserves review history and records who served when.
`Term_Start` / `Term_End` track each rotation.

### Anonymity

Student feedback stays fully anonymous. **Committee reviews are attributed** —
the member's name and email are stored with each review, and the login page
says so explicitly.

### Running the checks

```bash
python test/test_smoke.py          # 34 checks, 18 features, ~1 second
python test/test_committee.py      # no credentials required
python test/test_e2e_committee.py
python test/test_e2e_student.py
python test/test_e2e_home.py
```

This drives the real routes against an in-memory fake of the sheets layer and
verifies every item in `docs/FoodCommittee_Checklist.md` marked AUTO.
