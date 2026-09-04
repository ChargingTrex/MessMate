# Implementation Plan — SaiU Food Committee Module

**Scope:** a login page, a committee-only rating page (Taste, Quality, Variety, Hygiene, Menu + free-text review), a separate admin dashboard for that data, and an **admin UI for managing committee members**.

**Status:** plan only — no application code has been written yet.
**Target branch:** `claude/food-committee-dashboard-8fk021`

> **Revision 2** — member management moved from a CLI script into an admin web UI. This changes the security shape of the feature, not just its surface: see §3.3. The CLI is retained only as a break-glass tool.

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

1. **No user accounts and no sessions anywhere.** Student feedback is deliberately anonymous. Committee reviews are the first *attributed* data in the app — a deliberate policy change that must be stated on the login page.
2. **No CSRF protection anywhere.** Justified today: the only POST is an anonymous public form where forgery has no meaning. The moment an authenticated admin can create accounts by POST, that stops being true (§3.3).
3. **Timestamps are `%Y-%m-%d %H:%M:%S`.** `sheets.get_today_responses()` already carries a six-format fallback parser because Google Sheets silently reformats date-looking cells. New tabs should store a **separate plain-text `Date` column** so filtering never depends on parsing a timestamp.
4. **Blank ratings are `""`, never `0`/`None`** (`parse_rating` in `app.py`). Aggregation functions skip blanks.
5. **Escape once, not twice.** `app.py` calls `html.escape()` on `Review` at write time; `Suggestion` is left raw because Jinja2 auto-escapes at render. Committee reviews and member names *are* rendered on admin pages, so they must be stored **raw** and left to Jinja's auto-escaping — escaping at write would produce visible `&amp;` bugs.
6. **`worksheet.get_all_records()` requires unique, non-empty headers** in row 1 of every tab.
7. **Rate limiting is per-IP, in-memory.** Campus Wi-Fi puts every committee member behind one NAT IP, so a per-IP daily cap must **not** be applied to committee submissions.
8. **Google API quota is 100 reads / 100 s**, at 0.5–2 s per read. A per-request roster read is too expensive — cache it.

---

## 2. Requirements

| # | Requirement | Source |
|---|---|---|
| R1 | Login page restricted to Food Committee members | request |
| R2 | Rating page with Taste, Quality, Variety, Hygiene, Menu (1–5 each) | request |
| R3 | Free-text review field | request |
| R4 | A **separate** admin dashboard for committee data, distinct from the student dashboard | request |
| R5 | Members rotate periodically; roster must be changeable without a redeploy | recruitment blurb |
| R6 | **Admins add and manage members from a web UI, not a terminal** | request (rev 2) |
| R7 | Do not regress the existing anonymous student flow or its tests | codebase |

---

## 3. Proposed design

### 3.1 Routes

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/committee/login` | GET, POST | public | Email + password; sets member session |
| `/committee/logout` | POST | member | Clears session |
| `/committee` | GET | member | Rating page (5 dimensions + review) |
| `/committee/submit` | POST | member | Validates and appends one row |
| `/committee/thanks` | GET | member | Confirmation page |
| `/admin/login` | GET, POST | public | Admin password; sets admin session |
| `/admin/logout` | POST | admin | Clears admin session |
| `/dashboard/committee` | GET | admin **or** `?token=` | Committee dashboard (read-only) |
| `/admin/members` | GET | admin session only | Roster table + add form |
| `/admin/members/add` | POST | admin session only | Create one member |
| `/admin/members/bulk` | POST | admin session only | Create many from pasted list |
| `/admin/members/update` | POST | admin session only | Activate / deactivate / reset password |

Read-only dashboards keep accepting `?token=` so existing bookmarks and `tests/dashboard_tests.robot` keep working. **Roster mutations require a real admin session** — see below.

### 3.2 New Google Sheet tabs

**Tab `committee_members`** — the roster, now written by the app rather than by hand.

```
Email | Name | Password_Hash | Active | Must_Change_Password | Term_Start | Term_End | Created_At
```

* `Email` is column A so the existing `col_values(1)` + row-index update pattern from `update_daily_summary_for_today()` works for edits.
* `Active` = `TRUE`/`FALSE`. Rotation = flip `Active` and set `Term_End`; history is preserved.
* `Password_Hash` is a Werkzeug hash. **No plaintext password is ever written to the Sheet** — anyone with view access to the spreadsheet can read every cell.
* Admins may still edit this tab by hand; the app treats the Sheet as the source of truth either way.

**Tab `committee_reviews`** — one row per member per day.

```
Timestamp | Date | Member_Email | Member_Name | Taste | Quality | Variety | Hygiene | Menu | Review
```

* `Date` is a plain `YYYY-MM-DD` string used for all filtering (constraint 3).
* `Member_Name` is denormalised so the dashboard renders without a second roster read.
* The 5-dimension average is **computed on read**, not stored — one source of truth.

**Deferred:** a `committee_daily_summary` tab. At 5–15 rows/day, scanning `committee_reviews` is cheap; add it only if the dashboard gets slow.

### 3.3 Authentication — and why the admin UI forces an upgrade

Today `/dashboard` is gated by `?token=` in the query string (`app.py:154`). That is adequate for a read-only page. It is **not** adequate for a page that creates accounts and resets passwords, because a query-string secret leaks into browser history, `Referer` headers on any outbound link, and the hosting platform's access logs. Anyone who recovers that token could mint themselves a committee account.

So R6 promotes two items that revision 1 had parked in "optional":

**a) Admin session login (now a prerequisite, not optional).**

* New `ADMIN_PASSWORD_HASH` env var (generated once by a helper command). Verified with `check_password_hash`; the comparison is constant-time.
* On success: `session["is_admin"] = True`, 8-hour lifetime.
* `?token=` continues to authorise the **read-only** dashboards only. Every mutating route requires the session. This keeps backwards compatibility while ensuring the weaker credential can never change the roster.
* `@limiter.limit("10 per hour")` on the admin login POST.

**b) CSRF protection (now required).**

An authenticated admin session plus state-changing POSTs is exactly the condition CSRF exploits. A small `csrf.py` (~25 lines) generates a per-session token, embeds it as a hidden field, and verifies with `secrets.compare_digest` on every POST under `/admin/` and `/committee/`. Flask-WTF is the alternative; a hand-rolled helper matches this project's zero-extra-dependency style and needs no new package.

**Member auth** is unchanged from revision 1: `werkzeug.security` hashes (default scrypt, no new dependency), session cookie, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE=True` when not local, `PERMANENT_SESSION_LIFETIME=12h`. Roster lookups go through a 60-second TTL cache. A deactivated member is rejected at login *and* at submit, so removal takes effect immediately.

### 3.4 Admin member management UI (`/admin/members`)

A single page, styled with the existing `.card` system.

**Roster table** — Name, Email, Active badge, Term start/end, reviews submitted this month, and per-row actions:

| Action | Effect |
|---|---|
| Deactivate | `Active=FALSE`, `Term_End=today`. Existing reviews are preserved; the member can no longer log in |
| Reactivate | `Active=TRUE`, clears `Term_End` |
| Reset password | Generates a new one-time password, sets `Must_Change_Password=TRUE` |

**Add member form** — Name + Email. On submit the server:

1. Normalises and validates the email; rejects duplicates case-insensitively against the whole roster (including inactive members — reactivate instead of duplicating).
2. Optionally enforces a domain allowlist via `COMMITTEE_EMAIL_DOMAIN` (e.g. `saiuniversity.edu.in`); unset means any domain.
3. Generates a readable one-time password with `secrets.choice` over an alphabet excluding lookalike characters (`0/O`, `1/l/I`), formatted in groups — e.g. `mesa-7kfp-q3xr`.
4. Appends the row with the hash, `Must_Change_Password=TRUE`, `Term_Start=today`.
5. **Invalidates the roster cache immediately** so the new member can log in at once.
6. Re-renders with the password shown **once**, in a dismissible banner with a copy button.

**Bulk add** — a textarea accepting one `Name, email` pair per line, for the start of a rotation when ~8 members join together. Each line runs the same validation; the result is a table of generated credentials to hand out, plus a per-line list of any rejects. Valid rows are written in a single `append_rows` call rather than one API round-trip each.

**First-login password change.** Because the generated password is displayed on screen and then typically passed along over chat, `Must_Change_Password=TRUE` forces a redirect to `/committee/password` at next login, before any rating page is reachable. This is one extra route, one template, and one column — it can be dropped if you want the leanest possible v1, at the cost of long-lived shared passwords.

**What the UI deliberately does not do:** no password is ever displayed after its one-time reveal (only the hash is stored, so it genuinely cannot be re-shown — a reset is the only path); no member deletion, only deactivation, so review history stays attributable.

### 3.5 Rating page

Reuses the student form's visual language: `header` + `.card` sections + `.emoji-group` buttons + `.submit-btn`.

| Dimension | Field | Required |
|---|---|---|
| 😋 Taste | `taste` | yes |
| ✨ Quality | `quality` | yes |
| 🍽️ Variety | `variety` | yes |
| 🧼 Hygiene | `hygiene` | yes |
| 📋 Menu | `menu` | yes |
| ✍️ Review | `review` (textarea, 500 chars, counter) | optional |

* All five dimensions are required — unlike student per-item ratings. Submit stays disabled until all five are chosen.
* **One submission per member per day**, enforced server-side against `(Member_Email, Date)`. A duplicate renders a friendly "already submitted today" page, not an error. The residual double-click race is mitigated by the existing disable-on-submit pattern.
* Server-side validation mirrors `parse_rating`: each dimension must be a digit 1–5, else re-render with an error banner.

### 3.6 Admin committee dashboard

| Section | Content |
|---|---|
| Stat cards | Today's committee average (mean of the 5 dimensions), submissions today, active members, participation % |
| Dimension chart | Horizontal bar, today's average per dimension, red/amber/green at <2.5 / ≤3.5 / >3.5 — same thresholds and colours as `dashboard.js` |
| Trend chart | 7-day / 30-day toggle (same `.toggle-btn` pattern); overall committee average line with the 5 dimensions as toggleable datasets |
| Reviews feed | Newest first: member name, date, review text |

New file `static/committee_dashboard.js` rather than extending `dashboard.js` — the existing file is asserted against by `tests/dashboard_tests.robot`, and a separate file keeps that suite untouched (R7).

---

## 4. File-by-file changes

### 4.1 `sheets.py` (+ ~200 lines, no changes to existing functions)

```python
_roster_cache = None            # (fetched_at, [records])
ROSTER_TTL_SECONDS = 60

def get_committee_roster(force_refresh=False)   # cached read of committee_members
def invalidate_roster_cache()                   # called after every roster write
def get_committee_member(email)                 # case-insensitive lookup -> dict | None
def add_committee_member(email, name, pw_hash)  # -> bool, appends + invalidates
def add_committee_members_bulk(rows)            # single append_rows call
def update_committee_member(email, **fields)    # row lookup via col_values(1), cell update
def append_committee_review(data_dict)          # -> bool, same shape as append_response
def get_committee_reviews(days=None)            # -> list[dict], filtered by Date column
def has_submitted_today(email, date_str=None)   # -> bool
```

Existing behaviour is preserved: return `[]`/`False` on error, log to stdout, never raise into a route.

### 4.2 `auth.py` (new, ~110 lines)

```python
def verify_member(email, password)   # -> member dict | None (checks Active + hash)
def current_member()                 # -> dict | None from session
def login_required(view)             # member session -> redirect to /committee/login
def admin_required(view)             # admin SESSION only — for mutations
def admin_view_required(view)        # admin session OR ?token= — for read-only dashboards
def generate_password()              # readable one-time password, secrets-based
def normalize_email(raw)             # strip + lowercase + validate + domain allowlist
```

`admin_view_required` also refactors `/dashboard`'s inline token check into one shared place — behaviour identical, including the 403 message.

### 4.3 `csrf.py` (new, ~25 lines)

`issue_token()` / `validate_token()` over `session["_csrf"]`, compared with `secrets.compare_digest`; exposed to templates as a Jinja global so every form can render `{{ csrf_field() }}`.

### 4.4 `app.py` (+ ~260 lines)

Twelve new routes per §3.1, session config, CSRF wiring, and the aggregation used by the dashboard. Existing routes are untouched apart from `/dashboard` adopting `admin_view_required`.

### 4.5 Templates & static (new files)

* `templates/committee_login.html` — email/password, error banner (`.error-banner`, matching existing test selectors), an explicit "committee reviews are attributed, not anonymous" notice.
* `templates/committee_password.html` — first-login password change.
* `templates/committee_form.html` — five rating cards + review textarea.
* `templates/committee_thanks.html` — confirmation; doubles as the "already submitted today" page via a flag.
* `templates/admin_login.html` — admin password.
* `templates/admin_members.html` — roster table, add form, bulk-add textarea, one-time credential banner.
* `templates/committee_dashboard.html` — §3.6 layout.
* `static/committee.js` — the emoji-select widget extracted from `form.html`'s inline script, used by the committee form only. `form.html` is left alone in v1; migrating it is a clean follow-up once the committee suite is green.
* `static/committee_dashboard.js` — Chart.js setup.
* `static/style.css` — append a committee/admin section (login card, roster table, credential banner). No existing rule is modified.

### 4.6 `manage_committee.py` (new, root level — matches `seed_data.py` / `generate_qr.py`)

Reduced to a **break-glass tool** now that the UI exists, for the cases the UI cannot serve:

```
python manage_committee.py hash-admin-password   # generates ADMIN_PASSWORD_HASH for .env
python manage_committee.py add --email … --name … # when the admin password itself is lost
python manage_committee.py list                   # roster dump / header validation
```

---

## 5. Phased delivery

| Phase | Work | Acceptance criteria | Est. |
|---|---|---|---|
| **0 — Data** | Create both tabs with exact headers; `manage_committee.py`; generate `ADMIN_PASSWORD_HASH` | `get_committee_roster()` returns rows; Sheet holds a hash, not a password | 1 h |
| **1 — Auth core** | `auth.py`, `csrf.py`, session config, admin + member login/logout | Valid logins set sessions; bad password shows the error banner; deactivated member refused; `/committee` while logged out redirects; POST without a CSRF token is rejected | 3 h |
| **2 — Member UI** | `/admin/members` page, add / bulk-add / activate / deactivate / reset, one-time credential reveal, cache invalidation | Adding a member lets them log in immediately; duplicate email rejected; deactivation blocks login while preserving reviews; reset issues a new password; roster mutations refuse a `?token=`-only request | 4 h |
| **3 — Rating** | Rating page, `/committee/submit`, first-login password change, thanks page, duplicate guard | A submission writes exactly one correctly ordered row; a second same-day attempt is refused; missing dimension re-renders with an error; a `Must_Change_Password` member cannot reach the rating page | 3 h |
| **4 — Dashboard** | `/dashboard/committee`, template, charts, cross-links | Correct auth renders live data; wrong token 403s; empty data renders empty states, not a crash | 3 h |
| **5 — Tests & docs** | `tests/committee_tests.robot`, `tests/resources/committee_keywords.resource`, `test/test_committee.py`, README + CHANGELOG | Full Robot suite green, including pre-existing student suites | 3 h |

Total: **≈ 17 hours** (revision 1 was ~10–11 h; the admin UI, admin session auth, and CSRF add roughly 6).

---

## 6. Test plan

**Robot Framework** (`tests/committee_tests.robot`, tagged `smoke` / `api` so the existing CI filter picks it up):

* Member login valid → rating page; invalid → error banner, no session
* `/committee` unauthenticated → redirects to `/committee/login`
* Submit all five dimensions → thanks page; missing dimension → error
* Duplicate submission same day → "already submitted" page
* Admin login → `/admin/members` renders the roster
* **Add member → the new member can log in with the generated password**
* **Duplicate email → rejected with a clear message**
* **Deactivate → that member's login is refused**
* **`/admin/members` with only `?token=` → refused** (the privilege-separation guarantee)
* **POST without a CSRF token → rejected**
* `/dashboard/committee` without a token → 403; with one → stat cards present
* Regression: existing `form_tests.robot` and `dashboard_tests.robot` still pass

Tests create members under a `robot-test-*` email prefix and deactivate them in teardown, so the shared test spreadsheet stays clean.

**CI:** add `ADMIN_PASSWORD` and `TEST_COMMITTEE_EMAIL` / `TEST_COMMITTEE_PASSWORD` secrets to `.github/workflows/messmate_tests.yml`.

**Manual QA:** mobile rendering at 375 px, session expiry, member deactivated mid-session, Sheets unreachable (pages must render empty states, not 500), bulk add with a mix of valid and invalid lines.

---

## 7. Security & privacy notes

| Concern | Handling |
|---|---|
| Passwords in a shared spreadsheet | Werkzeug hashes only; the app never writes plaintext |
| **Account creation behind a weak credential** | Roster mutations require an admin **session**; `?token=` authorises read-only views only |
| **CSRF on admin mutations** | Per-session token on every POST under `/admin/` and `/committee/` |
| One-time password handling | Generated server-side, shown once, never recoverable (hash-only storage); `Must_Change_Password` forces a rotation at first login |
| Password in transit | Render terminates HTTPS. On local HTTP dev the password is in the clear — documented in the README; `SESSION_COOKIE_SECURE` is enabled off-localhost |
| Brute force | 20 member logins/hour/IP, 10 admin logins/hour/IP; note the in-memory limiter resets on restart |
| Attribution | Committee reviews are **not** anonymous — stated on the login page and in the README so members consent knowingly |
| Revocation | `Active=FALSE` enforced at login *and* at submit |
| Audit trail | `Term_Start` / `Term_End` / `Created_At` record roster changes; deactivation over deletion preserves review history |

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Multiple gunicorn workers each hold their own roster cache, so a member added in worker A is invisible to worker B | The 60 s TTL self-heals; the add flow invalidates the local worker's cache so the admin sees the change immediately |
| Google Sheets latency/quota on roster reads | TTL cache; one read per login, not per request; bulk add uses a single `append_rows` |
| Sheets reformats the `Date` column | Store as a plain string; set the column to Plain Text at tab creation |
| Header drift breaks `get_all_records()` | Exact headers documented in the README; `manage_committee.py list` fails loudly on mismatch |
| Concurrent roster edits (admin in the UI, someone else in the Sheet) | Row lookup happens immediately before each write; last write wins. Acceptable for a single-admin, ~10-member roster |
| Admin password lost | `manage_committee.py hash-admin-password` regenerates it; the Sheet is always directly editable as a fallback |
| Shared NAT IP | Committee routes are excluded from the per-IP daily cap; duplicate control is per-member-per-day |

---

## 9. Decisions taken (change any of these before Phase 0)

1. **Lunch only, one review per member per day** — matches the existing lunch-scoped app. A `Meal` column is the natural extension but adds a dimension to every chart.
2. **Email + password**, not Google SSO or magic links — no mail service is configured in this project, and SSO needs OAuth client setup.
3. **Single shared admin credential**, not per-admin accounts — matches the existing single `DASHBOARD_TOKEN` model. Per-admin logins are a later step if you want to know *which* admin added whom.
4. **Server-generated passwords**, not admin-chosen — removes the weakest link (an admin typing `saiu123` for everyone) and makes the one-time reveal meaningful.
5. **Deactivate, never delete** — review history stays attributable, and rotation history is preserved.
6. **Committee data stays separate** from student data everywhere. A five-person committee average and a 200-student average mean different things and should not be mixed.
7. **No public self-signup** — the recruitment blurb implies a human selection step; admins add the chosen members through the UI.
8. **`form.html` is not refactored** in v1, to keep the existing test suites untouched.

---

## 10. Out of scope

Public self-signup page, email delivery of credentials, per-admin accounts with an audit log, per-meal ratings, photo uploads, committee meeting minutes, PDF export, and the SQL migration described in `MessMate_SQL_Migration_Guide.md` (this plan stays on Sheets; every new function is written so the migration swaps `sheets.py` the same way the guide describes).
