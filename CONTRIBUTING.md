# Contributing to MessMate

Thanks for helping improve the mess. This file covers how the project is put
together, the conventions that are easy to break by accident, and how to run
the tests.

---

## The three feedback layers

MessMate collects feedback three different ways. They are deliberately kept
apart, and **their numbers are never combined** — a tally of taps, a mean of
1–5 dish scores, and a five-dimension committee review measure different
things from different populations.

| Surface | Who | What it asks | Stored in |
|---|---|---|---|
| `/home` | any student, no login | One tap per meal: good / bad / skip, plus an optional suggestion | `meal_ratings` |
| `/` | any student, no login | Per-dish 1–5 ratings, a review and a suggestion | `responses`, rolled up into `daily_summary` |
| `/committee` | committee members, signed in | Taste, quality, variety, hygiene, menu — attributed, not anonymous | `committee_reviews` |

If you add a fourth, give it its own tab and its own dashboard section. Do not
fold it into an existing average.

---

## The menu

The breakfast / lunch / dinner menu has **two equally valid editors**, and
neither is the source of truth over the other. Both write the same rows to the
`menu` tab:

1. **The spreadsheet.** Mess staff can type straight into the `menu` tab.
2. **The admin UI** at `/admin/menu`. A week at a glance, one row per day,
   each saved independently. Requires an admin session.

Items are comma-separated (`Idli, Sambar, Coconut Chutney`). Newlines work
too — `_split_items()` accepts either, and drops blanks, so a trailing comma
is harmless.

A day with no row, or a meal left blank, renders as **"Menu not published
yet"** rather than an empty card. An empty card reads as "the mess is closed",
which is a different and much worse message.

Writes go through `save_menu_for_date()`, which upserts: it updates the row if
that date exists and appends if not. That is why **`Date` must stay in column
A** of the `menu` tab — the row lookup scans that column.

---

## Google Sheet schema

Six tabs. Headers must match **exactly**: `get_all_records()` maps row 1 to
dict keys, so a rename silently breaks every lookup downstream.

| Tab | Headers |
|---|---|
| `responses` | Timestamp, Overall, Rice_Curry, Rice_Rasam, Chapati, Chapati_Gravy, Poriyal, Sweet, Salad, Curd, Papad, Pickle, Review, Suggestion |
| `daily_summary` | Date, Avg_Overall, Response_Count, Avg_Rice_Curry, … Avg_Pickle |
| `committee_members` | Email, Name, Password_Hash, Active, Must_Change_Password, Term_Start, Term_End, Created_At |
| `committee_reviews` | Timestamp, Date, Member_Email, Member_Name, Taste, Quality, Variety, Hygiene, Menu, Review |
| `menu` | Date, Breakfast, Lunch, Dinner |
| `meal_ratings` | Timestamp, Date, Meal, Rating, Suggestion |

**Do not hand-type this.** `template.csv` and `sheet_templates/*.csv` are
generated from `sheets.SHEET_TEMPLATES`:

```bash
python manage_committee.py sheet-template
```

Import one `sheet_templates/<tab>.csv` per tab via **File → Import → Insert new
sheet(s)**, then rename each tab to match the file name. If you add or rename a
column, change `SHEET_TEMPLATES` and regenerate — `test/test_smoke.py` fails
when the committed CSVs stop matching the code, so the repo's schema and the
code's schema cannot silently diverge.

`sheets.RESPONSE_HEADERS` and `sheets.SUMMARY_HEADERS` are documentation-only:
`append_response()` and `update_daily_summary_for_today()` still build their rows
positionally. `test/fake_sheets.py` imports them rather than copying, so the
journey suites' column-position assertions validate them too.

Set every `Date` column to **Plain Text** formatting. Google Sheets reformats
date-looking cells, which is exactly why `get_today_responses()` still carries
a six-format fallback parser. Newer tabs store `Date` as a literal
`YYYY-MM-DD` string and compare it directly, sidestepping the problem.

---

## Conventions that are easy to break

**Escape once, not twice.** `Review` on the student form is `html.escape()`d at
write time; `Suggestion` is stored raw because Jinja auto-escapes at render.
Anything you display through a template must be stored raw, or readers see
literal `&amp;`.

**Blank is not zero.** An unrated dish is `""`, never `0`. Aggregation skips
blanks; a zero would silently drag every average down.

**Never raise into a route.** Every `sheets.py` function returns `[]`, `False`
or `None` on failure and logs to stdout. Keep the `get_sheet()` call *inside*
the `try` — an exception escaping the data layer turns a Sheets outage into a
500 on the login page.

**Anonymity is load-bearing.** The student surfaces store no name, email, IP or
session marker. Committee reviews are the one attributed surface, and the
login page says so explicitly.

**Rate limits are per IP and in-memory.** `/submit` allows one a day;
`/home/rate` allows three, one per meal. Committee submissions are exempt —
campus Wi-Fi puts everyone behind one NAT address, so a per-IP cap there would
lock out the whole committee after the first person.

**Privilege split.** `?token=` opens the read-only dashboards only. Every route
that changes state — the roster, the menu — requires an admin session, because
a query-string secret leaks through browser history, `Referer` headers and
access logs.

---

## Running the tests

### No credentials needed

```bash
python test/test_smoke.py           # 34 checks, 18 features, ~1 second
python test/test_committee.py       # 59 checklist checks
python test/test_e2e_committee.py   # 64 steps, 9 committee journeys
python test/test_e2e_student.py     # 53 steps, 9 student journeys
python test/test_e2e_home.py        # 51 steps, 7 home/menu journeys
```

These replace only `sheets.get_sheet()`. Everything else — the caches, row
construction, the `col_values` lookup, `update_cell` — is the real code path.

### Browser tests

```bash
python test/fake_server.py 5001 &
robot --variable BASE_URL:http://127.0.0.1:5001 tests/home_tests.robot
```

`fake_server.py` runs the real app on the in-memory backend, so the UI suites
need no spreadsheet and leave nothing behind. Set `CHROME_BINARY` and
`CHROME_DRIVER` if the system Chrome is not the one you want to drive.

### Smoke against a deployment

```bash
python test/test_smoke.py --url https://your-app.onrender.com --token YOUR_TOKEN
```

Read-only: write checks report `SKIP`, so pointing this at production cannot
submit feedback, create members or change the menu.

---

## Two traps worth knowing

**Browser tests catch what HTTP tests cannot.** Two bugs in the `/home` feature
were invisible to the Python suites because those POST fields directly rather
than serialising a real form:

- A hidden `<input name="rating">` alongside submit buttons of the same name.
  The browser sends both, the empty one first, so every tap read as no choice.
- Disabling the submit button inside its own `submit` handler. The button *is*
  the submitter, and disabling it there drops its name/value from the payload.

If you touch a form, exercise it in a browser before believing it works.

**`app.config["RATELIMIT_ENABLED"]` does nothing** after the `Limiter` is
constructed — Flask-Limiter reads it at init. Use `app_module.limiter.enabled`.
See `memory.md`; getting this wrong produces failures that look exactly like
broken authentication.

---

## Before you open a pull request

- Run the five credential-free suites; they take seconds.
- Run the browser suite for anything touching a template or form.
- Add a `CHANGELOG.md` entry using the template at the bottom of that file.
- Keep test-case IDs unique across `tests/*.robot`; the suites are numbered in
  non-overlapping ranges.
