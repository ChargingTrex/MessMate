# MessMate — Google Sheets → SQL Migration Guide
**Replacing gspread with SQLite (local) or PostgreSQL (production)**

> This guide converts MessMate's backend from Google Sheets to a proper SQL database.
> The migration touches exactly 2 files: `sheets.py` (replaced entirely) and `app.py` (minor updates).
> Templates, static files, and routes stay unchanged.

---

## Why Migrate?

| Issue with Google Sheets | SQL Fix |
|---|---|
| `daily_summary` formulas need manual refresh | Queries compute aggregates live, always accurate |
| Every request creates a new API auth handshake | DB connection is persistent and fast |
| Google API rate limits (100 reads/100s per user) | No rate limits |
| Sheet goes down if Google is having issues | Your DB is self-hosted |
| `daily_summary` tab is a workaround | A single `GROUP BY` query replaces it entirely |
| Latency: 500ms–2s per Sheet read | SQLite: <5ms, PostgreSQL: <20ms |

---

## Which Database to Use

| Option | When to use | Cost |
|---|---|---|
| **SQLite** | Local development, single-server deploy | Free |
| **PostgreSQL** | Production on Render, multiple servers, Phase 2 | Free tier on Render/Supabase |

This guide does **SQLite first** (simplest, works immediately) then shows how to swap to **PostgreSQL** for production with one env variable change.

---

## Step 1 — Install Dependencies

```bash
pip install flask-sqlalchemy psycopg2-binary
```

Add to `requirements.txt`:
```
flask-sqlalchemy
psycopg2-binary
```

Remove from `requirements.txt` (no longer needed):
```
gspread
google-auth
```

---

## Step 2 — Create `database.py` (new file)

Create a new file `database.py` in the project root. This replaces `sheets.py` entirely.

```python
"""
MessMate Database Layer (database.py)
--------------------------------------
Replaces sheets.py. Uses SQLAlchemy to talk to SQLite (local)
or PostgreSQL (production). Swap between them via the DATABASE_URL
environment variable — no other code changes needed.
"""

import os
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ── Model — mirrors the Google Sheets "responses" tab exactly ────────────────

class Response(db.Model):
    __tablename__ = "responses"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    overall       = db.Column(db.Integer, nullable=False)          # Required 1–5
    rice_curry    = db.Column(db.Integer, nullable=True)
    rice_rasam    = db.Column(db.Integer, nullable=True)
    chapati       = db.Column(db.Integer, nullable=True)
    chapati_gravy = db.Column(db.Integer, nullable=True)
    poriyal       = db.Column(db.Integer, nullable=True)
    sweet         = db.Column(db.Integer, nullable=True)
    salad         = db.Column(db.Integer, nullable=True)
    curd          = db.Column(db.Integer, nullable=True)
    papad         = db.Column(db.Integer, nullable=True)
    pickle        = db.Column(db.Integer, nullable=True)
    review        = db.Column(db.String(150), nullable=True)
    suggestion    = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# ── Helpers — drop-in replacements for sheets.py functions ──────────────────

def append_response(data_dict):
    """Inserts one row into the responses table. Mirrors sheets.append_response()."""
    try:
        row = Response(
            overall       = data_dict.get("Overall"),
            rice_curry    = data_dict.get("Rice_Curry") or None,
            rice_rasam    = data_dict.get("Rice_Rasam") or None,
            chapati       = data_dict.get("Chapati") or None,
            chapati_gravy = data_dict.get("Chapati_Gravy") or None,
            poriyal       = data_dict.get("Poriyal") or None,
            sweet         = data_dict.get("Sweet") or None,
            salad         = data_dict.get("Salad") or None,
            curd          = data_dict.get("Curd") or None,
            papad         = data_dict.get("Papad") or None,
            pickle        = data_dict.get("Pickle") or None,
            review        = data_dict.get("Review") or None,
            suggestion    = data_dict.get("Suggestion") or None,
        )
        db.session.add(row)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"DB write error: {e}")
        return False


def get_today_responses():
    """Returns all responses from today. Mirrors sheets.get_today_responses()."""
    today = date.today()
    rows = Response.query.filter(
        db.func.date(Response.timestamp) == today
    ).all()
    return [r.to_dict() for r in rows]


def get_daily_summary():
    """
    Replaces the daily_summary Google Sheet tab entirely.
    Returns one dict per day with average scores and response count.
    This is a single SQL query — no formulas, no tab, no lag.
    """
    results = db.session.execute(db.text("""
        SELECT
            DATE(timestamp)            AS date,
            ROUND(AVG(overall), 1)     AS avg_overall,
            COUNT(*)                   AS response_count,
            ROUND(AVG(rice_curry), 1)  AS avg_rice_curry,
            ROUND(AVG(rice_rasam), 1)  AS avg_rice_rasam,
            ROUND(AVG(chapati), 1)     AS avg_chapati,
            ROUND(AVG(chapati_gravy), 1) AS avg_chapati_gravy,
            ROUND(AVG(poriyal), 1)     AS avg_poriyal,
            ROUND(AVG(sweet), 1)       AS avg_sweet,
            ROUND(AVG(salad), 1)       AS avg_salad,
            ROUND(AVG(curd), 1)        AS avg_curd,
            ROUND(AVG(papad), 1)       AS avg_papad,
            ROUND(AVG(pickle), 1)      AS avg_pickle
        FROM responses
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp) ASC
    """)).mappings().all()

    return [dict(row) for row in results]


def get_all_suggestions():
    """Returns all non-blank suggestions newest-first. Mirrors sheets.get_all_suggestions()."""
    rows = Response.query.filter(
        Response.suggestion != None,
        Response.suggestion != ""
    ).order_by(Response.timestamp.desc()).all()

    return [
        {"text": r.suggestion, "timestamp": str(r.timestamp)}
        for r in rows
    ]
```

---

## Step 3 — Update `app.py`

Three small changes to `app.py`:

### 3.1 Replace the import at the top

Remove:
```python
import sheets
```

Add:
```python
from database import db, append_response, get_today_responses, get_daily_summary, get_all_suggestions
```

### 3.2 Configure the database after `app = Flask(__name__)`

```python
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-dev-secret")

# ── Database config ───────────────────────────────────────────────────────────
# SQLite locally, PostgreSQL in production — swap via DATABASE_URL env variable
database_url = os.environ.get("DATABASE_URL", "sqlite:///messmate.db")

# Render PostgreSQL URLs start with postgres:// — SQLAlchemy needs postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create tables on first run
with app.app_context():
    db.create_all()
```

### 3.3 Update function calls in routes

In `/submit` route — change:
```python
success = sheets.append_response(data_dict)
```
To:
```python
success = append_response(data_dict)
```

In `/dashboard` route — change:
```python
summary_records = sheets.get_daily_summary()
today_responses = sheets.get_today_responses()
all_suggestions = sheets.get_all_suggestions()
```
To:
```python
summary_records = get_daily_summary()
today_responses = get_today_responses()
all_suggestions = get_all_suggestions()
```

### 3.4 Update `daily_summary` key names in the dashboard route

The SQL query returns lowercase keys. Update these references in `/dashboard`:

```python
# Old (Google Sheets keys)
date_val = str(row.get("Date", ""))
avg_val  = row.get("Avg_Overall", 0)

# New (SQL keys — lowercase)
date_val = str(row.get("date", ""))
avg_val  = row.get("avg_overall", 0)
```

And for item_data, update the fallback key names:
```python
# Old
"Response_Count"

# New
"response_count"
```

---

## Step 4 — Migrate Existing Seed Data (Optional)

If you want to keep the 76 rows already in Google Sheets, create `migrate_from_sheets.py`:

```python
"""
migrate_from_sheets.py
Run once to copy data from Google Sheets into the SQL database.
Delete this file after running.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# Import old sheets module temporarily
import sheets as old_sheets

# Import new database
from app import app
from database import db, Response
from datetime import datetime

with app.app_context():
    db.create_all()

    worksheet = old_sheets.get_sheet("responses")
    if not worksheet:
        print("Could not connect to Google Sheets")
        exit()

    records = worksheet.get_all_records()
    migrated = 0

    for record in records:
        ts_str = record.get("Timestamp", "")
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"Skipping bad timestamp: {ts_str}")
            continue

        def safe_int(val):
            try:
                v = str(val).strip()
                return int(v) if v else None
            except:
                return None

        row = Response(
            timestamp     = ts,
            overall       = safe_int(record.get("Overall")),
            rice_curry    = safe_int(record.get("Rice_Curry")),
            rice_rasam    = safe_int(record.get("Rice_Rasam")),
            chapati       = safe_int(record.get("Chapati")),
            chapati_gravy = safe_int(record.get("Chapati_Gravy")),
            poriyal       = safe_int(record.get("Poriyal")),
            sweet         = safe_int(record.get("Sweet")),
            salad         = safe_int(record.get("Salad")),
            curd          = safe_int(record.get("Curd")),
            papad         = safe_int(record.get("Papad")),
            pickle        = safe_int(record.get("Pickle")),
            review        = record.get("Review") or None,
            suggestion    = record.get("Suggestion") or None,
        )
        db.session.add(row)
        migrated += 1

    db.session.commit()
    print(f"✅ Migrated {migrated} rows from Google Sheets to SQL.")
```

Run it once:
```bash
python migrate_from_sheets.py
```

Then delete it. You no longer need `sheets.py`, `gspread`, or `google-auth` after this.

---

## Step 5 — Test Locally with SQLite

```bash
python app.py
```

On first run, SQLAlchemy creates `messmate.db` in the project root automatically.

Verify:
```bash
# Quick row count check
python3 -c "
from app import app
from database import db, Response
with app.app_context():
    print('Rows in DB:', Response.query.count())
"
```

Submit a test form at `http://127.0.0.1:5000` and confirm the row count increases.

---

## Step 6 — Switch to PostgreSQL for Production (Render)

### 6.1 Create a PostgreSQL database on Render

1. Render dashboard → **New → PostgreSQL**
2. Name: `messmate-db`
3. Region: Singapore
4. Plan: Free
5. Click **Create Database**
6. Copy the **Internal Database URL** from the database info page

### 6.2 Add the environment variable

In your Render **Web Service** (not the database) → Environment:

```
Key:   DATABASE_URL
Value: (paste the Internal Database URL from step 6.1)
```

The URL looks like:
```
postgres://messmate_user:password@dpg-xxx.singapore-postgres.render.com/messmate_db
```

The code in `app.py` already handles the `postgres://` → `postgresql://` conversion.

### 6.3 Deploy

```bash
git add .
git commit -m "Migrate from Google Sheets to PostgreSQL"
git push origin main
```

Render auto-deploys. On first boot, `db.create_all()` creates the `responses` table in PostgreSQL automatically.

---

## Step 7 — Update `.gitignore`

Add:
```
messmate.db
```

Remove (no longer needed if you've fully migrated):
```
credentials.json
```

---

## What You Can Delete After Migration

Once everything is working on SQL:

| File / package | Safe to remove? |
|---|---|
| `sheets.py` | ✅ Yes |
| `credentials.json` | ✅ Yes |
| `migrate_from_sheets.py` | ✅ Yes (run it first) |
| `gspread` in requirements.txt | ✅ Yes |
| `google-auth` in requirements.txt | ✅ Yes |
| `GOOGLE_CREDENTIALS_JSON` env var | ✅ Yes (remove from Render) |
| `SPREADSHEET_ID` env var | ✅ Yes (remove from Render) |
| `daily_summary` tab in Google Sheet | ✅ Yes (SQL query replaces it) |

---

## Summary — Files Changed

| File | What changes |
|---|---|
| `database.py` | **New file** — replaces sheets.py entirely |
| `app.py` | 4 small edits — import, db config, function calls, key names |
| `requirements.txt` | Add `flask-sqlalchemy`, `psycopg2-binary`. Remove `gspread`, `google-auth` |
| `migrate_from_sheets.py` | **New file** — run once, then delete |
| `.gitignore` | Add `messmate.db` |

Everything else — `templates/`, `static/`, `Procfile`, `generate_qr.py`, `seed_data.py` — stays exactly the same.

---

*MessMate · Google Sheets → SQL Migration Guide · v1.0 · March 2026*
