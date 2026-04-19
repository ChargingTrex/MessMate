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

### 4. Environment Variables

Create a `.env` file in the project root:

```env
FLASK_SECRET_KEY=your-random-secret-key-here
SPREADSHEET_ID=your-google-sheet-id-from-url
DASHBOARD_TOKEN=vc2026
```

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
├── seed_data.py           # Demo data seeding script
├── generate_qr.py         # QR code generator for the mess poster
├── templates/
│   ├── form.html          # Student feedback form
│   ├── thanks.html        # Post-submission thank-you page
│   └── dashboard.html     # Stakeholder dashboard
└── static/
    ├── style.css          # Shared mobile-first styles
    └── dashboard.js       # Chart.js chart setup
```

## Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Student feedback form |
| `/submit` | POST | Process submission (1/IP/day rate limit) |
| `/thanks` | GET | Thank-you page |
| `/dashboard?token=TOKEN` | GET | Admin dashboard (403 without token) |
| `/health` | GET | Health check → `{"status": "ok"}` |

## Notes

- **Rate limiting**: Uses in-memory storage. Resets on server restart (acceptable for prototype on Render's free tier).
- **Anonymity**: No student name, email, or identity is ever collected or stored.
- **Timestamp format**: `YYYY-MM-DD HH:MM:SS` everywhere. Never change this — date filtering depends on it.
