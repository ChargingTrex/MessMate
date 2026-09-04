# Food Committee — Implementation Checklist

Verification checklist for `docs/FoodCommittee_Implementation_Plan.md` (revision 2).
Written **before** coding; every item is checked after implementation.

**Result: 59/59 AUTO checks pass** (`python test/test_committee.py`), all INSPECT
items verified, LIVE items pending a real spreadsheet.

**Verification methods**
- `AUTO` — asserted by `test/test_committee.py`, which drives the real Flask routes through Flask's test client against an in-memory fake of the `sheets` module (no Google credentials needed).
- `INSPECT` — verified by reading the diff / running the file.
- `LIVE` — requires a real Google Sheet + credentials. Cannot run in this environment; listed so it is not silently skipped.

---

## Phase 0 — Data layer & tooling

| # | Item | Method | Status |
|---|---|---|---|
| P0-1 | `committee_members` header constant matches the plan exactly (Email, Name, Password_Hash, Active, Must_Change_Password, Term_Start, Term_End, Created_At) | AUTO | ✅ |
| P0-2 | `committee_reviews` header constant matches the plan exactly | AUTO | ✅ |
| P0-3 | `Email` is column A so `col_values(1)` row lookup works | INSPECT | ✅ |
| P0-4 | Roster read is cached with a 60 s TTL | AUTO | ✅ |
| P0-5 | Every roster write invalidates the cache | AUTO | ✅ |
| P0-6 | All new `sheets.py` functions return `[]`/`False` on error, never raise | AUTO | ✅ |
| P0-7 | No existing `sheets.py` function is modified | INSPECT | ✅ |
| P0-8 | `manage_committee.py hash-admin-password` prints a valid scrypt hash | INSPECT | ✅ |
| P0-9 | Sheet tabs created with headers in the real spreadsheet | LIVE | ⏳ |

**Checkpoint 0 — gate to Phase 1** ✅
Data layer reads and writes through an exercised cache, degrades safely when
Sheets is unreachable, and no existing `sheets.py` function changed.

## Phase 1 — Auth core

| # | Item | Method | Status |
|---|---|---|---|
| P1-1 | Valid member login sets a session and redirects to `/committee` | AUTO | ✅ |
| P1-2 | Wrong password re-renders login with `.error-banner`, no session set | AUTO | ✅ |
| P1-3 | Unknown email fails identically to a wrong password (no user enumeration) | AUTO | ✅ |
| P1-4 | `Active=FALSE` member cannot log in | AUTO | ✅ |
| P1-5 | Member deactivated mid-session is refused at submit, not just at login | AUTO | ✅ |
| P1-6 | `/committee` while logged out redirects to `/committee/login` | AUTO | ✅ |
| P1-7 | Logout clears the session | AUTO | ✅ |
| P1-8 | Valid admin password sets an admin session | AUTO | ✅ |
| P1-9 | Wrong admin password is refused | AUTO | ✅ |
| P1-10 | Admin password compared against a hash, constant-time | INSPECT | ✅ |
| P1-11 | Every POST under `/admin/` and `/committee/` rejects a missing CSRF token (403) | AUTO | ✅ |
| P1-12 | A wrong/forged CSRF token is rejected | AUTO | ✅ |
| P1-13 | CSRF comparison uses `secrets.compare_digest` | INSPECT | ✅ |
| P1-14 | Session cookie flags set: HttpOnly, SameSite=Lax, Secure off-localhost | INSPECT | ✅ |
| P1-15 | Login POSTs are rate limited (member 20/h, admin 10/h) | INSPECT | ✅ |
| P1-16 | Public student form `/` and `/submit` still work unchanged | AUTO | ✅ |

**Checkpoint 1 — gate to Phase 2** ✅
Both session types work, CSRF rejects forged and missing tokens, deactivation
takes effect mid-session, and the anonymous student flow is untouched.

## Phase 2 — Member management UI

| # | Item | Method | Status |
|---|---|---|---|
| P2-1 | `/admin/members` renders the roster for an admin session | AUTO | ✅ |
| P2-2 | **`/admin/members` refuses a `?token=`-only request** (privilege separation) | AUTO | ✅ |
| P2-3 | All four mutation routes refuse a `?token=`-only request | AUTO | ✅ |
| P2-4 | Adding a member appends a row and reveals a one-time password | AUTO | ✅ |
| P2-5 | The added member can immediately log in with that password (cache invalidated) | AUTO | ✅ |
| P2-6 | Only the hash is stored — plaintext never written to the sheet | AUTO | ✅ |
| P2-7 | Duplicate email rejected case-insensitively | AUTO | ✅ |
| P2-8 | Duplicate against an *inactive* member is also rejected (reactivate instead) | AUTO | ✅ |
| P2-9 | Malformed email rejected | AUTO | ✅ |
| P2-10 | `COMMITTEE_EMAIL_DOMAIN` allowlist enforced when set, any domain when unset | AUTO | ✅ |
| P2-11 | Deactivate sets `Active=FALSE` + `Term_End`, and blocks that member's login | AUTO | ✅ |
| P2-12 | Reactivate sets `Active=TRUE` and clears `Term_End` | AUTO | ✅ |
| P2-13 | Reset password issues a new working password and invalidates the old one | AUTO | ✅ |
| P2-14 | Bulk add creates all valid rows and reports per-line rejects | AUTO | ✅ |
| P2-15 | Bulk add uses a single `append_rows` call, not one per member | AUTO | ✅ |
| P2-16 | Generated passwords exclude lookalike characters (0/O/1/l/I) | AUTO | ✅ |
| P2-17 | No delete action exists — deactivation only | INSPECT | ✅ |
| P2-18 | Member names render escaped (no double-escaping, no XSS) | AUTO | ✅ |

**Checkpoint 2 — gate to Phase 3** ✅
Admins can run the roster end to end from the browser. The privilege boundary
holds: `?token=` cannot reach any roster route. No plaintext password is ever
written to the sheet.

## Phase 3 — Rating page

| # | Item | Method | Status |
|---|---|---|---|
| P3-1 | Rating page shows all five dimensions: taste, quality, variety, hygiene, menu | AUTO | ✅ |
| P3-2 | Valid submission writes exactly one row in the documented column order | AUTO | ✅ |
| P3-3 | Missing any one dimension → error banner, no row written | AUTO | ✅ |
| P3-4 | Out-of-range rating (0, 6, "abc") rejected | AUTO | ✅ |
| P3-5 | Review is optional | AUTO | ✅ |
| P3-6 | Review stored **raw** (not html-escaped) so Jinja escapes once | AUTO | ✅ |
| P3-7 | Review truncated to 500 chars | AUTO | ✅ |
| P3-8 | Second submission same day refused with the "already submitted" page | AUTO | ✅ |
| P3-9 | `Date` column written as plain `YYYY-MM-DD`; `Timestamp` as `%Y-%m-%d %H:%M:%S` | AUTO | ✅ |
| P3-10 | `Must_Change_Password` member is redirected to the change form and cannot reach the rating page | AUTO | ✅ |
| P3-11 | Password change clears the flag and lets the member proceed | AUTO | ✅ |
| P3-12 | Password change rejects a too-short password and a mismatched confirmation | AUTO | ✅ |
| P3-13 | Submitting is not blocked by the per-IP student rate limiter (shared NAT) | AUTO | ✅ |

**Checkpoint 3 — gate to Phase 4** ✅
A member can complete the full journey — first login, forced password change,
rate five dimensions, submit once per day — and every invalid input is refused
before it reaches the sheet.

## Phase 4 — Committee dashboard

| # | Item | Method | Status |
|---|---|---|---|
| P4-1 | `/dashboard/committee` renders with an admin session | AUTO | ✅ |
| P4-2 | `/dashboard/committee` renders with `?token=` (read-only access retained) | AUTO | ✅ |
| P4-3 | Wrong/absent token → 403 | AUTO | ✅ |
| P4-4 | Stat cards show today's average, submissions, active members, participation % | AUTO | ✅ |
| P4-5 | Per-dimension averages computed correctly (verified against known fixture data) | AUTO | ✅ |
| P4-6 | Trend data covers the last N days and is JSON-serialisable into the template | AUTO | ✅ |
| P4-7 | Reviews feed newest-first with member name and date | AUTO | ✅ |
| P4-8 | Zero data renders empty states, not a crash | AUTO | ✅ |
| P4-9 | Sheets failure renders the page with safe defaults, not a 500 | AUTO | ✅ |
| P4-10 | Existing `/dashboard` is untouched and still renders | AUTO | ✅ |
| P4-11 | `static/dashboard.js` is not modified (protects existing Robot suite) | INSPECT | ✅ |
| P4-12 | Cross-links between the two dashboards | INSPECT | ✅ |

**Checkpoint 4 — gate to Phase 5** ✅
Aggregates are correct against fixture data, both credentials open the
dashboard, and neither an outage nor an empty sheet produces a 500.

## Phase 5 — Tests & docs

| # | Item | Method | Status |
|---|---|---|---|
| P5-1 | `test/test_committee.py` runs standalone with no credentials and passes | AUTO | ✅ |
| P5-2 | `tests/committee_tests.robot` + keywords resource written, tagged smoke/api | INSPECT | ✅ |
| P5-3 | Robot tests create `robot-test-*` members and deactivate them in teardown | INSPECT | ✅ |
| P5-4 | CI workflow updated with the new secrets | INSPECT | ✅ |
| P5-5 | README documents new routes, env vars, and sheet schema | INSPECT | ✅ |
| P5-6 | CHANGELOG updated | INSPECT | ✅ |
| P5-7 | `form.html` unmodified (R7) | INSPECT | ✅ |
| P5-8 | Existing Robot suites still pass | LIVE | ⏳ |

**Checkpoint 5 — feature complete** ✅
59/59 automated checks pass with no credentials. Robot suite parses with 14
tagged cases. CI runs the credential-free harness before the browser suite.

---

## Regression guarantees (R7)

These must hold at every phase:

- ✅ `/`, `/submit`, `/thanks`, `/dashboard`, `/health` behave exactly as before
- ✅ `templates/form.html`, `templates/dashboard.html`, `static/dashboard.js` unmodified
- ✅ No existing `sheets.py` function signature or behaviour changed
- ✅ No new required env var breaks boot for an existing deployment


---

## What verification caught

Two issues surfaced only because the checks were written before the code:

**A real bug — reviews feed ordering.** The dashboard built its feed with
`reversed(reviews)`, which is correct only while the sheet's physical row order
happens to be chronological. It stops being correct the moment anyone sorts the
tab or backfills a day. Fixed by sorting on `(Date, Timestamp)` descending.

**A harness bug that masked eight checks.** `app.config["RATELIMIT_ENABLED"]`
does nothing after the `Limiter` is constructed — Flask-Limiter reads that key
at init. Phase 1's admin logins therefore consumed the real 10/hour cap, and
every admin action in Phase 2 silently got a 429 and a redirect. The failures
looked like broken reset and bulk-add logic; both were fine. The live switch is
the `limiter.enabled` instance attribute.

The second is worth recording for anyone writing future tests against this app:
a route that redirects on 429 fails in a way that resembles an auth bug.

## Not verified here

| Item | Why | How to close it |
|---|---|---|
| P0-9 — sheet tabs exist | No Google credentials in this environment | Create both tabs with the exact headers, then `python manage_committee.py list` |
| P5-8 — existing Robot suites pass | Needs a browser and a live spreadsheet | Runs in CI on push |
| Committee Robot suite | Same | Seed one `robot-test-*` member, set the CI secrets |

The AUTO harness covers the logic these would exercise; what remains untested is
the Google Sheets round trip itself and real browser rendering.
