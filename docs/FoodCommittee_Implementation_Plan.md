# Implementation Plan — SaiU Food Committee Module

**Scope:** a login page, a committee-only rating page (Taste, Quality, Variety, Hygiene, Menu + free-text review), and a separate admin dashboard for that data.

**Status:** plan only — no application code has been written yet.
**Target branch:** `claude/food-committee-dashboard-8fk021`

---

## 1. What exists today (codebase survey)

MessMate is a small, flat Flask app with Google Sheets as its database. Everything relevant lives in five files:

| File | Role | Notes for this feature |
|---|---|---|
| `app.py` (~310 lines) | All routes, validation, aggregation | `FLASK_SECRET_KEY` is already required at boot, so Flask sessions work out of the box. Flask-Limiter is initialised with `default_limits=[]`, so only `/submit` is throttled. |
| `sheets.py` (~300 lines) | Data layer over `gspread` | Module-level cached client (`_client`), one function per read/write. Every function returns `[]`/`False` on error instead of raising — routes stay alive when Sheets is down. |
| `templates/form.html` | Student form | Emoji rating widget + its inline JS. The widget is the pattern to reuse. |
| `templates/dashboard.html` | Admin dashboard | Token-gated via `?token=`, Chart.js from CDN, page-local `<style>` block. |
| `static/style.css`, `static/dashboard.js` | Shared styles, chart setup | `.card`, `.emoji-group`, `.emoji-btn.selected`, `.toggle-btn`, `.empty-state` are reusable. |

Supporting: `seed_data.py`, `generate_qr.py`, `test/*.py` (ad-hoc scripts), `tests/*.robot` (Robot Framework suites run in CI by `.github/workflows/messmate_tests.yml`).

### Conventions that constrain the design

1. **No user accounts anywhere.** Student feedback is deliberately anonymous. Committee reviews are the first *attributed* data in the app — a deliberate policy change that must be stated on the login page.
2. **Timestamps are `%Y-%m-%d %H:%M:%S`.** `sheets.get_today_responses()` already carries a six-format fallback parser because Google Sheets silently reformats date-looking cells. New tabs should store a **separate plain-text `Date` column** so filtering never depends on parsing a timestamp.
3. **Blank ratings are `""`, never `0`/`None`** (`parse_rating` in `app.py`). Aggregation functions skip blanks.
4. **Escape once, not twice.** `app.py` calls `html.escape()` on `Review` at write time; `Suggestion` is left raw because Jinja2 auto-escapes at render. Committee reviews *are* rendered on the dashboard, so they must be stored **raw** and left to Jinja's auto-escaping — escaping at write would produce visible `&amp;` bugs.
5. **`worksheet.get_all_records()` requires unique, non-empty headers** in row 1 of every tab.
6. **Rate limiting is per-IP, in-memory.** Campus Wi-Fi puts every committee member behind one NAT IP, so a per-IP daily cap must **not** be applied to committee submissions.
7. **Google API quota is 100 reads / 100 s.** Every Sheets read costs 0.5–2 s. A per-request roster read on every page load is too expensive — cache it.

---

## 2. Requirements

| # | Requirement | Source |
|---|---|---|
| R1 | Login page restricted to Food Committee members | request |
| R2 | Rating page with Taste, Quality, Variety, Hygiene, Menu (1–5 each) | request |
| R3 | Free-text review field | request |
| R4 | A **separate** admin dashboard for committee data, distinct from the student dashboard | request |
| R5 | Members rotate periodically; roster must be changeable without a redeploy | recruitment blurb |
| R6 | Do not regress the existing anonymous student flow or its tests | codebase |

---

## 3. Proposed design

### 3.1 Routes

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/committee/login` | GET, POST | public | Email + password form; sets session on success |
| `/committee/logout` | POST | session | Clears session, redirects to login |
| `/committee` | GET | session | Rating page (5 dimensions + review) |
| `/committee/submit` | POST | session | Validates and appends one row |
| `/committee/thanks` | GET | session | Confirmation page |
| `/dashboard/committee` | GET | `?token=` | Admin committee dashboard |

`/dashboard/committee` deliberately mirrors the existing `?token=DASHBOARD_TOKEN` gate so admins keep one credential, and the two dashboards cross-link in their headers.

### 3.2 New Google Sheet tabs

**Tab `committee_members`** — the roster; edited directly in the Sheet, which satisfies R5 with no redeploy.

```
Email | Name | Password_Hash | Active | Term_Start | Term_End | Created_At
```

* `Active` = `TRUE`/`FALSE`. Rotation = flip `Active` and set `Term_End`; history is preserved.
* `Password_Hash` is a Werkzeug hash. **No plaintext passwords ever touch the Sheet** — anyone with view access to the spreadsheet can read every cell.

**Tab `committee_reviews`** — one row per member per day.

```
Timestamp | Date | Member_Email | Member_Name | Taste | Quality | Variety | Hygiene | Menu | Review
```

* `Date` is a plain `YYYY-MM-DD` string used for all filtering (see constraint 2).
* `Member_Name` is denormalised so the dashboard renders without a second roster read.
* The 5-dimension average is **computed on read**, not stored — one source of truth.

**Deferred:** a `committee_daily_summary` tab. At 5–15 rows/day, scanning `committee_reviews` is cheap; add the summary tab only if the dashboard gets slow.

### 3.3 Authentication

Session-cookie auth, no new dependency — `werkzeug.security` ships with Flask.

* `generate_password_hash` / `check_password_hash` (default scrypt).
* On success: `session["member_email"]`, `session["member_name"]`, `session.permanent = True`.
* Cookie hardening in `app.py`: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE=True` when not local (env-driven), `PERMANENT_SESSION_LIFETIME=12h`.
* Roster lookups go through a **60-second TTL cache** in `sheets.py` to stay inside the Google read quota.
* A deactivated member is rejected at login *and* at submit — a live session must not outlive removal from the committee.
* Login POST gets `@limiter.limit("20 per hour")` as brute-force friction. (In-memory storage resets on restart; documented, acceptable at this scale.)

**No self-signup in v1.** Admins add members with a CLI script (§4.5), which is the only place a password is generated. This keeps the recruitment/selection process human, as the blurb describes.

### 3.4 Rating page

Reuses the student form's visual language: `header` + `.card` sections + `.emoji-group` buttons + `.submit-btn`.

| Dimension | Field | Required |
|---|---|---|
| 😋 Taste | `taste` | yes |
| ✨ Quality | `quality` | yes |
| 🍽️ Variety | `variety` | yes |
| 🧼 Hygiene | `hygiene` | yes |
| 📋 Menu | `menu` | yes |
| ✍️ Review | `review` (textarea, 500 chars, counter) | optional |

* All five dimensions are required — unlike the student per-item ratings, which are optional. Submit stays disabled until all five are chosen.
* **One submission per member per day**, enforced server-side by checking `committee_reviews` for `(Member_Email, Date)`. A duplicate renders a friendly "already submitted today" page rather than an error. The residual double-click race is mitigated by the existing disable-on-submit pattern; a duplicate row would not corrupt averages materially.
* Server-side validation mirrors `parse_rating`: each dimension must be a digit 1–5, else re-render with an error banner.

### 3.5 Admin committee dashboard

| Section | Content |
|---|---|
| Stat cards | Today's committee average (mean of the 5 dimensions), submissions today, active members, participation % |
| Dimension chart | Horizontal bar, today's average per dimension, red/amber/green at <2.5 / ≤3.5 / >3.5 — same thresholds and colours as `dashboard.js` |
| Trend chart | 7-day / 30-day toggle (same `.toggle-btn` pattern); overall committee average line, with the 5 dimensions as toggleable datasets |
| Reviews feed | Newest first, showing member name, date, and the review text |

New file `static/committee_dashboard.js` rather than extending `dashboard.js` — the existing file is asserted against by `tests/dashboard_tests.robot`, and a separate file keeps that suite untouched (R6).

---

## 4. File-by-file changes

### 4.1 `sheets.py` (+ ~140 lines, no changes to existing functions)

```python
_roster_cache = None            # (timestamp, [records])
ROSTER_TTL_SECONDS = 60

def get_committee_roster(force_refresh=False)      # cached read of committee_members
def get_committee_member(email)                    # case-insensitive lookup -> dict | None
def append_committee_review(data_dict)             # -> bool, same shape as append_response
def get_committee_reviews(days=None)               # -> list[dict], filtered by Date column
def has_submitted_today(email, date_str=None)      # -> bool
```

Existing behaviour is preserved: return `[]`/`False` on error, log to stdout, never raise into a route.

### 4.2 `auth.py` (new, ~70 lines)

```python
def verify_member(email, password)   # -> member dict | None (checks Active + hash)
def current_member()                 # -> dict | None from session
def login_required(view)             # decorator -> redirect to /committee/login
def admin_token_required(view)       # decorator wrapping the existing ?token= check
```

`admin_token_required` also refactors `/dashboard`'s inline check into one shared place — behaviour identical, including the 403 message.

### 4.3 `app.py` (+ ~150 lines)

Six new routes per §3.1, plus session config and the `committee_avg` aggregation used by the dashboard. Existing routes are untouched apart from `/dashboard` adopting the new decorator.

### 4.4 Templates & static (new files)

* `templates/committee_login.html` — email/password, error banner (`.error-banner`, matching existing test selectors), an explicit "committee reviews are attributed, not anonymous" notice.
* `templates/committee_form.html` — five rating cards + review textarea.
* `templates/committee_thanks.html` — confirmation, doubles as the "already submitted today" page via a flag.
* `templates/committee_dashboard.html` — §3.5 layout.
* `static/committee.js` — the emoji-select widget extracted from `form.html`'s inline script, used by the committee form only. `form.html` is left alone in v1; migrating it to the shared file is a clean follow-up once the committee suite is green.
* `static/committee_dashboard.js` — Chart.js setup.
* `static/style.css` — append a small committee section (login card, dimension rows). No existing rule is modified.

### 4.5 `manage_committee.py` (new, root level — matches `seed_data.py` / `generate_qr.py`)

```
python manage_committee.py add    --email a@sai.edu --name "A B"   # generates + prints a one-time password
python manage_committee.py reset  --email a@sai.edu                 # new password
python manage_committee.py rotate --out a@sai.edu --in b@sai.edu    # deactivate + add
python manage_committee.py list                                     # roster with Active state
```

This is the only path that writes `Password_Hash`, so plaintext never reaches the Sheet.

---

## 5. Phased delivery

| Phase | Work | Acceptance criteria | Est. |
|---|---|---|---|
| **0 — Data** | Create both tabs with exact headers; `manage_committee.py`; seed one test member | `get_committee_roster()` returns the member; Sheet holds a hash, not a password | 1 h |
| **1 — Auth** | `auth.py`, session config, login/logout routes + template | Valid login lands on `/committee`; bad password shows the error banner; deactivated member is refused; `/committee` while logged out redirects to login | 2 h |
| **2 — Rating** | Rating page, `/committee/submit`, thanks page, duplicate guard | A submission writes exactly one correctly ordered row; a second attempt the same day is refused; missing dimension re-renders with an error | 2–3 h |
| **3 — Dashboard** | `/dashboard/committee`, template, charts, cross-links | Correct token renders live data; wrong token 403s; empty data renders empty states, not a crash | 3 h |
| **4 — Tests & docs** | `tests/committee_tests.robot`, `tests/resources/committee_keywords.resource`, `test/test_committee.py`, README + CHANGELOG | Full Robot suite green, including the pre-existing student suites | 2 h |
| **5 — Optional** | `committee_daily_summary` tab, session-based admin login, in-app member management, participation reminders | — | — |

Total for phases 0–4: **≈ 10–11 hours**.

---

## 6. Test plan

**Robot Framework** (`tests/committee_tests.robot`, tagged `smoke` / `api` so the existing CI filter picks it up):

* Login with valid credentials → rating page loads
* Login with invalid password → error banner, no session
* `/committee` unauthenticated → redirects to `/committee/login`
* Submit with all five dimensions → thanks page
* Submit with a missing dimension → error, submit button stays disabled client-side
* Duplicate submission same day → "already submitted" page
* `/dashboard/committee` without a token → 403
* `/dashboard/committee` with the token → stat cards present
* Regression: the existing `form_tests.robot` and `dashboard_tests.robot` still pass

**CI:** add `TEST_COMMITTEE_EMAIL` / `TEST_COMMITTEE_PASSWORD` secrets to `.github/workflows/messmate_tests.yml` and seed that member into the test spreadsheet once.

**Manual QA:** mobile rendering at 375 px, session expiry after 12 h, member deactivated mid-session, Sheets unreachable (dashboard must render empty states, not 500).

---

## 7. Security & privacy notes

| Concern | Handling |
|---|---|
| Passwords in a shared spreadsheet | Werkzeug hashes only; CLI is the sole writer |
| Session forgery | Signed cookie via the already-mandatory `FLASK_SECRET_KEY`; HttpOnly, SameSite=Lax, Secure in production |
| Brute force | 20 login attempts/hour/IP; note the in-memory limiter resets on restart |
| Admin token in the query string | Leaks into browser history, referrers, and server logs. Retained for compatibility; §5 Phase 5 proposes replacing it with a session login reusing `auth.py` |
| Attribution | Committee reviews are **not** anonymous. This is stated on the login page and in the README so members consent knowingly |
| Revocation | `Active=FALSE` is enforced at login *and* at submit, so removal takes effect immediately |

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Google Sheets latency/quota on roster reads | 60 s TTL cache; one read per login, not per request |
| Sheets reformats the `Date` column | Store `Date` as a plain string and set the column format to Plain Text at tab creation |
| Header drift breaks `get_all_records()` | Document exact headers in the README; `manage_committee.py list` fails loudly on mismatch |
| Members forget passwords (no email delivery configured) | `manage_committee.py reset` — deliberately manual for a 10-person committee |
| Shared NAT IP | Committee routes are excluded from the per-IP daily cap; duplicate control is per-member-per-day instead |

---

## 9. Decisions taken (change any of these before Phase 0)

1. **Lunch only, one review per member per day** — matches the existing app, which is lunch-scoped. A `Meal` column (breakfast/lunch/dinner) is the natural extension but adds a dimension to every chart.
2. **Email + password**, not Google SSO or magic links — no mail service is configured in this project, and SSO needs OAuth client setup.
3. **Committee data stays separate** from student data everywhere: separate tabs, separate dashboard, no mixing of averages. A five-person committee average and a 200-student average mean different things and should not be summed.
4. **No public self-signup form** in v1 — the recruitment blurb implies a human selection step; admins add the chosen members via CLI.
5. **`form.html` is not refactored** in v1, to keep the existing test suites untouched.

---

## 10. Out of scope

Member self-signup page, email notifications/reminders, per-meal ratings, photo uploads, committee meeting minutes, exporting reports to PDF, and the SQL migration described in `MessMate_SQL_Migration_Guide.md` (this plan stays on Sheets; every new function is written so the migration swaps `sheets.py` the same way the guide describes).
