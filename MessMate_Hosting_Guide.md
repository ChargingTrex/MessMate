# MessMate — Hosting Guide
**Deploy to Render.com · Flask + Google Sheets · Free Tier**

> This guide takes you from a working local app to a live public URL with a QR code — ready for the VC demo.

---

## Prerequisites

Before starting, confirm all of these:

- [ ] `python app.py` runs locally without errors
- [ ] `http://127.0.0.1:5000` and `/dashboard` load in browser
- [ ] `test/test_connections.py` passes all checks
- [ ] `credentials.json` is in `.gitignore` (never commit this)
- [ ] You have a GitHub account
- [ ] You have a Render.com account (free — sign up at render.com)

---

## Step 1 — Prepare the Repo for Deployment

### 1.1 Confirm `Procfile` exists in project root

```
web: gunicorn app:app
```

If missing, create it with exactly that one line. No file extension, capital P.

### 1.2 Confirm `requirements.txt` has all dependencies

```
flask
gspread
google-auth
flask-limiter
gunicorn
python-dotenv
qrcode
Pillow
```

Add any that are missing, then test locally:
```bash
pip install -r requirements.txt
```

### 1.3 Confirm `.gitignore` blocks secrets

```
credentials.json
.env
__pycache__/
*.pyc
venv/
.DS_Store
```

### 1.4 Confirm `app.py` reads credentials from environment, not file

In `sheets.py`, the `get_client()` function should already handle both cases:
```python
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if creds_json:
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
```

If yours looks like this — you're ready. No changes needed.

---

## Step 2 — Push to GitHub

```bash
# If not already a git repo
git init
git branch -M main

# Add all files (credentials.json will be blocked by .gitignore)
git add .
git commit -m "Initial MessMate prototype"

# Create a new repo on github.com, then:
git remote add origin https://github.com/ChargingTrex/MessMate.git
git push -u origin main
```

> Double-check on GitHub that `credentials.json` and `.env` do **not** appear in the file list.

---

## Step 3 — Deploy on Render.com

### 3.1 Create a new Web Service

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub account if not already done
3. Select the **MessMate** repository
4. Configure:

| Setting | Value |
|---|---|
| Name | `messmate` |
| Region | Singapore (closest to Chennai) |
| Branch | `main` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | `Free` |

5. Click **Create Web Service**

### 3.2 Set Environment Variables

In Render → your service → **Environment** tab, add these 3 variables:

**Variable 1:**
```
Key:   FLASK_SECRET_KEY
Value: (any long random string — e.g. messmate-secret-2026-vcready)
```

**Variable 2:**
```
Key:   SPREADSHEET_ID
Value: 1OSRGmdOALh1CA7OzoKtFc1tg01amrokqqmho4icFUNw
```

**Variable 3:**
```
Key:   GOOGLE_CREDENTIALS_JSON
Value: (paste the entire contents of your credentials.json as one line)
```

To get the credentials as a single line, run this in your terminal:
```bash
cat credentials.json | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))"
```

Copy the output and paste it as the value for `GOOGLE_CREDENTIALS_JSON`.

### 3.3 Trigger Deploy

Click **Deploy Latest Commit** — Render will:
1. Pull your code from GitHub
2. Run `pip install -r requirements.txt`
3. Start the app with `gunicorn app:app`

Watch the logs. A successful deploy ends with:
```
==> Your service is live 🎉
```

---

## Step 4 — Verify the Live App

Your live URL will be:
```
https://messmate.onrender.com
```

Check all three routes:

| Route | Expected |
|---|---|
| `https://messmate.onrender.com/` | Student feedback form loads |
| `https://messmate.onrender.com/dashboard` | Dashboard with charts |
| `https://messmate.onrender.com/health` | `{"status": "ok"}` |

Submit a test rating from the live URL and confirm it appears in your Google Sheet.

---

## Step 5 — Generate the QR Code

Update `generate_qr.py` with your live URL, then run:

```bash
python generate_qr.py
```

This creates `messmate_qr.png` in your project folder.

**Print tips for the demo:**
- Print at A5 size minimum — bigger is easier to scan from a distance
- Test scanning from 30cm away on a real phone before the demo
- Stick it on the mess notice board at least 30 minutes before the VC visit

---

## Step 6 — Demo Readiness Checklist

Run through this the day before the VC meeting:

- [ ] Scan QR code on Android phone → form opens
- [ ] Fill and submit the form → row appears in Google Sheet within 5 seconds
- [ ] Open `/dashboard` on a laptop → trend chart and bar chart render
- [ ] Today's average and response count show correctly
- [ ] Suggestions list shows seeded suggestions
- [ ] Try submitting twice from the same phone → second attempt is blocked
- [ ] Dashboard loads in under 3 seconds on college WiFi

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails on Render | Check `requirements.txt` includes `gunicorn` |
| `Application error` on load | Check Render logs — usually a missing env variable |
| `GOOGLE_CREDENTIALS_JSON` parse error | Re-run the `cat credentials.json` command and repaste — no line breaks |
| Dashboard shows 0 responses | Check `SPREADSHEET_ID` is correct and Sheet is shared with service account |
| QR code opens wrong URL | Edit the URL variable at the top of `generate_qr.py` |
| Render app sleeps after 15 min (free tier) | First load after sleep takes ~30 seconds — normal on free plan |

---

## Free Tier Limitations to Know

Render's free tier has one behaviour worth noting for the demo:

> The app **spins down after 15 minutes of inactivity**. The first request after that takes ~30 seconds to wake up.

**Fix for the demo:** Open the app in your browser 5 minutes before the VC arrives so it's already awake. Or upgrade to Render's $7/month Starter plan to avoid this.

---

*MessMate Hosting Guide · v1.0 · March 2026*
