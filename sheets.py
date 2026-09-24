"""
MessMate Google Sheets Database Interface (sheets.py)
-----------------------------------------------------
This module acts as the database layer for the application.
It uses the `gspread` library and Google Cloud Service Account credentials
to authenticate and interact with the Google Sheet backend.

CRITICAL: The gspread client is cached at module level to avoid
re-authenticating on every request (~2 seconds saved per call).

Functions:
  get_client()                       — Cached gspread client
  get_sheet(tab_name)                — Get a named worksheet
  append_response(data_dict)         — Write one feedback row
  get_today_responses(date_override) — Read today's filtered rows
  get_daily_summary()                — Read daily_summary tab
  update_daily_summary_for_today()   — Recalculate and upsert today's summary
  get_all_suggestions()              — Read all non-blank suggestions
"""

import os
import json
import time
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ── Auth ──────────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Module-level client cache — avoids 2s re-auth overhead on every request
_client = None


def get_client():
    """
    Returns a cached gspread client. Creates one only on the first call.
    Locally: reads from credentials.json file.
    On Render/production: reads from GOOGLE_CREDENTIALS_JSON env var (JSON string).
    """
    global _client
    if _client is None:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            # Production — credentials stored as environment variable
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            # Local development — credentials stored as file
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_sheet(tab_name):
    """
    Gets the spreadsheet by SPREADSHEET_ID env var and returns the named worksheet.
    Returns None on error (logged to console).
    """
    try:
        client = get_client()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID")
        if not spreadsheet_id:
            print("ERROR: SPREADSHEET_ID environment variable not set")
            return None
        spreadsheet = client.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        print(f"Error accessing sheet '{tab_name}': {e}")
        return None


def append_response(data_dict):
    """
    Appends one row to the 'responses' tab.
    Timestamp is auto-generated in YYYY-MM-DD HH:MM:SS format.

    Column order:
      Timestamp, Overall, Rice_Curry, Rice_Rasam, Chapati, Chapati_Gravy,
      Poriyal, Sweet, Salad, Curd, Papad, Pickle, Review, Suggestion

    Returns True on success, False on failure.
    """
    worksheet = get_sheet("responses")
    if not worksheet:
        return False

    try:
        # Auto-generate timestamp in the canonical format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row_data = [
            timestamp,
            data_dict.get("Overall", ""),
            data_dict.get("Rice_Curry", ""),
            data_dict.get("Rice_Rasam", ""),
            data_dict.get("Chapati", ""),
            data_dict.get("Chapati_Gravy", ""),
            data_dict.get("Poriyal", ""),
            data_dict.get("Sweet", ""),
            data_dict.get("Salad", ""),
            data_dict.get("Curd", ""),
            data_dict.get("Papad", ""),
            data_dict.get("Pickle", ""),
            data_dict.get("Review", ""),
            data_dict.get("Suggestion", "")
        ]

        worksheet.append_row(row_data, value_input_option='RAW')
        return True
    except Exception as e:
        print(f"Error appending response: {e}")
        return False


def get_today_responses(date_override=None):
    """
    Reads all rows from the 'responses' tab and filters to today's rows.
    Handles multiple timestamp formats to guard against Google Sheets
    auto-reformatting dates.

    Args:
        date_override: Optional date string (YYYY-MM-DD) for seeding past days.

    Returns list of record dicts.
    """
    worksheet = get_sheet("responses")
    if not worksheet:
        return []

    try:
        records = worksheet.get_all_records()

        if date_override:
            target_date = datetime.strptime(date_override, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()

        today_responses = []
        for record in records:
            ts = str(record.get("Timestamp", "")).strip()
            if not ts:
                continue

            # Try multiple date formats to handle Sheets auto-reformatting
            parsed_date = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                        "%m/%d/%Y %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y",
                        "%m/%d/%Y"):
                try:
                    parsed_date = datetime.strptime(ts, fmt).date()
                    break
                except ValueError:
                    continue

            if parsed_date == target_date:
                today_responses.append(record)

        return today_responses
    except Exception as e:
        print(f"Error getting today's responses: {e}")
        return []


def get_daily_summary():
    """
    Reads all rows from the 'daily_summary' tab.
    Returns list of record dicts.
    """
    worksheet = get_sheet("daily_summary")
    if not worksheet:
        return []

    try:
        return worksheet.get_all_records()
    except Exception as e:
        print(f"Error reading daily summary: {e}")
        return []


def update_daily_summary_for_today(date_override=None):
    """
    Calculates today's averages from responses and updates/appends to 'daily_summary'.

    Steps:
      1. Fetch today's responses (or date_override's responses)
      2. If none: return True immediately (nothing to update)
      3. Calculate averages for all 11 item columns (skip blank/non-numeric)
      4. Build summary row
      5. If today's date exists in column A: UPDATE that row
      6. If not: APPEND a new row

    CRITICAL: today_str uses "%Y-%m-%d" — must match Timestamp prefix exactly.

    Args:
        date_override: Optional date string (YYYY-MM-DD) for seeding past days.

    Returns True on success, False on failure.
    """
    today_str = date_override or datetime.now().strftime("%Y-%m-%d")

    # 1. Get today's responses
    today_responses = get_today_responses(date_override=today_str)
    response_count = len(today_responses)

    if response_count == 0:
        return True  # Nothing to update

    # 2. Calculate averages — skip blank and non-numeric values
    def calc_avg(key):
        """Calculate average for a given column key, ignoring blanks."""
        scores = []
        for r in today_responses:
            val = r.get(key, "")
            try:
                if str(val).strip():
                    scores.append(float(val))
            except ValueError:
                pass
        return round(sum(scores) / len(scores), 1) if scores else 0

    avg_overall = calc_avg("Overall")
    avg_rice_curry = calc_avg("Rice_Curry")
    avg_rice_rasam = calc_avg("Rice_Rasam")
    avg_chapati = calc_avg("Chapati")
    avg_chapati_gravy = calc_avg("Chapati_Gravy")
    avg_poriyal = calc_avg("Poriyal")
    avg_sweet = calc_avg("Sweet")
    avg_salad = calc_avg("Salad")
    avg_curd = calc_avg("Curd")
    avg_papad = calc_avg("Papad")
    avg_pickle = calc_avg("Pickle")

    row_data = [
        today_str,
        avg_overall,
        response_count,
        avg_rice_curry,
        avg_rice_rasam,
        avg_chapati,
        avg_chapati_gravy,
        avg_poriyal,
        avg_sweet,
        avg_salad,
        avg_curd,
        avg_papad,
        avg_pickle
    ]

    # 3. Update or append to daily_summary
    worksheet = get_sheet("daily_summary")
    if not worksheet:
        return False

    try:
        # Get all dates in column A to check if today already exists
        dates = worksheet.col_values(1)

        if today_str in dates:
            # Row exists — update it (1-indexed in gspread)
            row_index = dates.index(today_str) + 1
            cell_range = f"A{row_index}:M{row_index}"
            worksheet.update(cell_range, [row_data])
        else:
            # Row doesn't exist — append it
            worksheet.append_row(row_data)

        return True
    except Exception as e:
        print(f"Error updating daily summary: {e}")
        return False


def get_all_suggestions():
    """
    Reads all rows from the 'responses' tab and returns a list of
    {text, timestamp} dicts for rows where Suggestion is non-blank.

    Does NOT reverse order — let app.py handle display ordering.
    """
    worksheet = get_sheet("responses")
    if not worksheet:
        return []

    try:
        records = worksheet.get_all_records()
        suggestions = []

        for record in records:
            suggestion = record.get("Suggestion", "")
            if isinstance(suggestion, str):
                suggestion = suggestion.strip()
            if suggestion:
                ts = record.get("Timestamp", "")
                suggestions.append({"text": suggestion, "timestamp": ts})

        return suggestions
    except Exception as e:
        print(f"Error reading suggestions: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Food Committee — roster and review storage
# ══════════════════════════════════════════════════════════════════════════════
# These functions back the Food Committee module. They follow the same
# conventions as the student-feedback functions above: never raise into a
# route, log to stdout, and return []/False/None on failure.
#
# The get_sheet() call sits INSIDE each try block deliberately. get_sheet()
# swallows its own errors today, so this looks redundant — but if it ever
# raises, an exception escaping from here reaches a route that has no handler
# for it, and a member sees a 500 on the login page instead of a normal
# failure. Keeping it inside makes the "never raises" contract true rather
# than incidentally true.
#
# CRITICAL: 'Email' must stay in column A of committee_members — the row-lookup
# used by update_committee_member() reads col_values(1), the same pattern
# update_daily_summary_for_today() uses for dates.

COMMITTEE_MEMBERS_TAB = "committee_members"
COMMITTEE_REVIEWS_TAB = "committee_reviews"

# Row 1 of each tab must match these exactly — get_all_records() maps them to
# dict keys, so a rename here silently breaks every lookup downstream.
MEMBER_HEADERS = [
    "Email", "Name", "Password_Hash", "Active",
    "Must_Change_Password", "Term_Start", "Term_End", "Created_At"
]

REVIEW_HEADERS = [
    "Timestamp", "Date", "Member_Email", "Member_Name",
    "Taste", "Quality", "Variety", "Hygiene", "Menu", "Review"
]

# The five dimensions the committee rates. Order matters — it drives the
# column order on write and the display order on the dashboard.
DIMENSIONS = ["Taste", "Quality", "Variety", "Hygiene", "Menu"]

# ── Roster cache ──────────────────────────────────────────────────────────────
# A roster read costs 0.5-2s and counts against Google's 100-reads/100s quota,
# so it is cached. Writes invalidate it immediately, which is what makes a
# newly added member able to log in at once rather than up to a minute later.
#
# Each gunicorn worker holds its own cache. A member added in worker A is
# invisible to worker B until the TTL lapses — self-healing, and the admin who
# did the adding always sees their own change because that worker was
# invalidated by the write.
ROSTER_TTL_SECONDS = 60
_roster_cache = None  # tuple: (fetched_at_monotonic, [records]) or None


def invalidate_roster_cache():
    """Drops the cached roster so the next read hits Sheets. Call after every write."""
    global _roster_cache
    _roster_cache = None


def get_committee_roster(force_refresh=False):
    """
    Returns all committee_members rows as dicts, cached for ROSTER_TTL_SECONDS.
    Returns [] on error (never raises).
    """
    global _roster_cache

    if not force_refresh and _roster_cache is not None:
        fetched_at, records = _roster_cache
        if (time.monotonic() - fetched_at) < ROSTER_TTL_SECONDS:
            return records

    try:
        worksheet = get_sheet(COMMITTEE_MEMBERS_TAB)
        if not worksheet:
            return []
        records = worksheet.get_all_records()
        _roster_cache = (time.monotonic(), records)
        return records
    except Exception as e:
        print(f"Error reading committee roster: {e}")
        return []


def _is_true(val):
    """
    Sheets returns booleans inconsistently — TRUE, 'TRUE', 'true', True, 1.
    Treats all of those as True and everything else (including '') as False.
    """
    return str(val).strip().upper() in ("TRUE", "1", "YES")


def get_committee_member(email):
    """
    Case-insensitive roster lookup. Returns the member dict or None.
    The returned dict carries the sheet's raw values plus normalised
    'is_active' / 'must_change_password' booleans.
    """
    if not email:
        return None

    target = str(email).strip().lower()
    for record in get_committee_roster():
        if str(record.get("Email", "")).strip().lower() == target:
            member = dict(record)
            member["is_active"] = _is_true(record.get("Active"))
            member["must_change_password"] = _is_true(record.get("Must_Change_Password"))
            return member
    return None


def _member_row(email, name, password_hash, today):
    """Builds one committee_members row in MEMBER_HEADERS order."""
    return [
        str(email).strip().lower(),
        name,
        password_hash,
        "TRUE",   # Active
        "TRUE",   # Must_Change_Password — the generated password is single-use
        today,    # Term_Start
        "",       # Term_End
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]


def add_committee_member(email, name, password_hash):
    """
    Appends one member. Returns True on success, False on failure.
    Caller is responsible for duplicate checking (see auth.normalize_email).
    """
    try:
        worksheet = get_sheet(COMMITTEE_MEMBERS_TAB)
        if not worksheet:
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        worksheet.append_row(_member_row(email, name, password_hash, today),
                             value_input_option="RAW")
        invalidate_roster_cache()
        return True
    except Exception as e:
        print(f"Error adding committee member: {e}")
        return False


def add_committee_members_bulk(members):
    """
    Appends many members in a SINGLE API call.

    Args:
        members: list of (email, name, password_hash) tuples.

    Returns True on success, False on failure.
    """
    if not members:
        return True

    try:
        worksheet = get_sheet(COMMITTEE_MEMBERS_TAB)
        if not worksheet:
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        rows = [_member_row(e, n, h, today) for e, n, h in members]
        # One append_rows beats N append_row calls against the quota
        worksheet.append_rows(rows, value_input_option="RAW")
        invalidate_roster_cache()
        return True
    except Exception as e:
        print(f"Error bulk-adding committee members: {e}")
        return False


def update_committee_member(email, **fields):
    """
    Updates named columns of one member row, found by email in column A.

    Accepts any MEMBER_HEADERS name as a keyword, e.g.
        update_committee_member(e, Active="FALSE", Term_End="2026-09-04")

    Returns True on success, False if the member or sheet is missing.
    """
    try:
        worksheet = get_sheet(COMMITTEE_MEMBERS_TAB)
        if not worksheet:
            return False
        target = str(email).strip().lower()
        # Column A holds emails; row 1 is the header
        emails = [str(v).strip().lower() for v in worksheet.col_values(1)]
        if target not in emails:
            print(f"Cannot update unknown committee member: {email}")
            return False

        row_index = emails.index(target) + 1  # gspread is 1-indexed

        for key, value in fields.items():
            if key not in MEMBER_HEADERS:
                print(f"Ignoring unknown member field: {key}")
                continue
            col_index = MEMBER_HEADERS.index(key) + 1
            worksheet.update_cell(row_index, col_index, value)

        invalidate_roster_cache()
        return True
    except Exception as e:
        print(f"Error updating committee member: {e}")
        return False


def append_committee_review(data_dict):
    """
    Appends one committee review row in REVIEW_HEADERS order.

    CRITICAL: Review is stored RAW, not html.escape()d. It is rendered through
    Jinja2 on the dashboard, which auto-escapes — escaping here too would show
    literal "&amp;" to admins. This mirrors how Suggestion is handled in
    append_response().

    Returns True on success, False on failure.
    """
    try:
        worksheet = get_sheet(COMMITTEE_REVIEWS_TAB)
        if not worksheet:
            return False
        now = datetime.now()
        row_data = [
            now.strftime("%Y-%m-%d %H:%M:%S"),   # Timestamp
            now.strftime("%Y-%m-%d"),            # Date — plain text, never parsed
            str(data_dict.get("Member_Email", "")).strip().lower(),
            data_dict.get("Member_Name", ""),
            data_dict.get("Taste", ""),
            data_dict.get("Quality", ""),
            data_dict.get("Variety", ""),
            data_dict.get("Hygiene", ""),
            data_dict.get("Menu", ""),
            data_dict.get("Review", "")
        ]
        worksheet.append_row(row_data, value_input_option="RAW")
        return True
    except Exception as e:
        print(f"Error appending committee review: {e}")
        return False


def get_committee_reviews(days=None):
    """
    Reads committee_reviews, optionally limited to the last `days` days.

    Filtering uses the plain-text Date column rather than parsing Timestamp —
    Google Sheets reformats date-looking cells, which is why
    get_today_responses() needs a six-format fallback parser. Storing Date as
    text sidesteps that entirely.

    Returns a list of record dicts, oldest first. [] on error.
    """
    try:
        worksheet = get_sheet(COMMITTEE_REVIEWS_TAB)
        if not worksheet:
            return []
        records = worksheet.get_all_records()

        if days is None:
            return records

        cutoff = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        # Dates are ISO-formatted, so string comparison is chronological
        return [r for r in records
                if str(r.get("Date", "")).strip() >= cutoff]
    except Exception as e:
        print(f"Error reading committee reviews: {e}")
        return []


def has_submitted_today(email, date_str=None):
    """
    True if this member already has a review row for the given date
    (defaults to today). Used to enforce one review per member per day.

    Fails OPEN: if the sheet is unreachable this returns False, so an outage
    lets a member through rather than locking the committee out entirely.
    """
    if not email:
        return False

    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    target_email = str(email).strip().lower()

    for record in get_committee_reviews():
        if (str(record.get("Date", "")).strip() == target_date and
                str(record.get("Member_Email", "")).strip().lower() == target_email):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Daily menu and quick meal ratings
# ══════════════════════════════════════════════════════════════════════════════
# Backs the student home page: today's breakfast/lunch/dinner, and a one-tap
# good / bad / skip reaction per meal.
#
# This is deliberately NOT the same data as the student per-dish form or the
# committee's five-dimension review. It answers a cruder question — "was that
# meal alright, and did you even turn up" — which is the question most students
# will actually stop to answer.
#
# Same conventions as above: never raise into a route, log to stdout, return
# []/False/None on failure. Date is plain text so Sheets cannot reformat it
# out from under the lookup.

# ── Sheet schema, in one place ─────────────────────────────────────────────────
# Column order for the two original student tabs. These are documentation-only:
# append_response() and update_daily_summary_for_today() still build their rows
# positionally, exactly as before. They exist so the CSV templates and the test
# fake have one authoritative source instead of three hand-copied lists, and
# test_smoke.py checks the committed CSVs still match them.
RESPONSE_HEADERS = [
    "Timestamp", "Overall", "Rice_Curry", "Rice_Rasam", "Chapati",
    "Chapati_Gravy", "Poriyal", "Sweet", "Salad", "Curd", "Papad",
    "Pickle", "Review", "Suggestion"
]

SUMMARY_HEADERS = [
    "Date", "Avg_Overall", "Response_Count", "Avg_Rice_Curry",
    "Avg_Rice_Rasam", "Avg_Chapati", "Avg_Chapati_Gravy", "Avg_Poriyal",
    "Avg_Sweet", "Avg_Salad", "Avg_Curd", "Avg_Papad", "Avg_Pickle"
]

MENU_TAB = "menu"
MEAL_RATINGS_TAB = "meal_ratings"

MENU_HEADERS = ["Date", "Breakfast", "Lunch", "Dinner"]
MEAL_RATING_HEADERS = ["Timestamp", "Date", "Meal", "Rating", "Suggestion"]

MEALS = ["Breakfast", "Lunch", "Dinner"]

# Display-only serving windows. Shown on the home page so students know whether
# they are early or late; nothing in the app enforces them.
MEAL_TIMINGS = {
    "Breakfast": "7:30 – 9:30 am",
    "Lunch": "12:00 – 2:30 pm",
    "Dinner": "7:30 – 9:30 pm",
}

RATINGS = ["good", "bad", "skip"]

# Menu reads happen on every home-page load, so they are cached like the roster.
# A shorter TTL than the roster: a menu correction should appear quickly.
MENU_TTL_SECONDS = 30
_menu_cache = None  # (fetched_at_monotonic, [records]) or None


def invalidate_menu_cache():
    """Drops the cached menu. Called after every menu write."""
    global _menu_cache
    _menu_cache = None


def get_menu_records(force_refresh=False):
    """All rows of the menu tab as dicts, cached. [] on error."""
    global _menu_cache

    if not force_refresh and _menu_cache is not None:
        fetched_at, records = _menu_cache
        if (time.monotonic() - fetched_at) < MENU_TTL_SECONDS:
            return records

    try:
        worksheet = get_sheet(MENU_TAB)
        if not worksheet:
            return []
        records = worksheet.get_all_records()
        _menu_cache = (time.monotonic(), records)
        return records
    except Exception as e:
        print(f"Error reading menu: {e}")
        return []


def _split_items(raw):
    """
    'Idli, Sambar, Coconut Chutney' -> ['Idli', 'Sambar', 'Coconut Chutney'].
    Accepts commas or newlines so staff can type it either way.
    """
    text = str(raw or "").replace("\n", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def get_menu_for_date(date_str=None):
    """
    Returns {"Breakfast": [...], "Lunch": [...], "Dinner": [...]} for one date.
    Meals with nothing published come back as empty lists, which the home page
    renders as "not published yet" rather than pretending the mess is closed.
    """
    target = date_str or datetime.now().strftime("%Y-%m-%d")

    for record in get_menu_records():
        if str(record.get("Date", "")).strip() == target:
            return {meal: _split_items(record.get(meal, "")) for meal in MEALS}

    return {meal: [] for meal in MEALS}


def get_menu_week(start_date=None, days=7):
    """
    Menu rows for `days` days from start_date, for the admin editor.
    Always returns one entry per day, with blanks for days not yet published.
    """
    start = (datetime.strptime(start_date, "%Y-%m-%d") if start_date
             else datetime.now())
    published = {str(r.get("Date", "")).strip(): r for r in get_menu_records()}

    week = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        date_str = day.strftime("%Y-%m-%d")
        row = published.get(date_str, {})
        week.append({
            "date": date_str,
            "label": day.strftime("%a %d %b"),
            "is_today": date_str == datetime.now().strftime("%Y-%m-%d"),
            "Breakfast": str(row.get("Breakfast", "")),
            "Lunch": str(row.get("Lunch", "")),
            "Dinner": str(row.get("Dinner", "")),
        })
    return week


def save_menu_for_date(date_str, breakfast, lunch, dinner):
    """
    Upserts one day's menu: updates the row if that date exists, appends if not.
    Mirrors update_daily_summary_for_today()'s row-lookup pattern, which is why
    Date must stay in column A.

    Returns True on success, False on failure.
    """
    try:
        worksheet = get_sheet(MENU_TAB)
        if not worksheet:
            return False

        row_data = [date_str, breakfast, lunch, dinner]
        dates = [str(v).strip() for v in worksheet.col_values(1)]

        if date_str in dates:
            row_index = dates.index(date_str) + 1   # gspread is 1-indexed
            worksheet.update(f"A{row_index}:D{row_index}", [row_data])
        else:
            worksheet.append_row(row_data, value_input_option="RAW")

        invalidate_menu_cache()
        return True
    except Exception as e:
        print(f"Error saving menu for {date_str}: {e}")
        return False


def append_meal_rating(meal, rating, suggestion=""):
    """
    Stores one quick reaction. Anonymous: no identity, no IP, nothing that
    could tie the row to a student — the same promise the per-dish form makes.

    Suggestion is stored RAW; Jinja escapes it when the dashboard renders it.

    Returns True on success, False on failure.
    """
    try:
        worksheet = get_sheet(MEAL_RATINGS_TAB)
        if not worksheet:
            return False

        now = datetime.now()
        worksheet.append_row([
            now.strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d"),
            meal,
            rating,
            suggestion,
        ], value_input_option="RAW")
        return True
    except Exception as e:
        print(f"Error appending meal rating: {e}")
        return False


def get_meal_ratings(date_str=None):
    """
    Meal ratings, optionally for one date. [] on error.
    """
    try:
        worksheet = get_sheet(MEAL_RATINGS_TAB)
        if not worksheet:
            return []
        records = worksheet.get_all_records()
        if date_str is None:
            return records
        return [r for r in records
                if str(r.get("Date", "")).strip() == date_str]
    except Exception as e:
        print(f"Error reading meal ratings: {e}")
        return []


def summarise_meal_ratings(date_str=None):
    """
    Per-meal tallies for one day:
        {"Lunch": {"good": 12, "bad": 3, "skip": 5, "total": 20, "score": 80}, ...}

    `score` is good as a percentage of those who actually ate (good + bad).
    Skips are counted but deliberately excluded from it — a student who never
    turned up is telling you about attendance, not about the food.
    """
    target = date_str or datetime.now().strftime("%Y-%m-%d")
    summary = {meal: {"good": 0, "bad": 0, "skip": 0, "total": 0, "score": 0}
               for meal in MEALS}

    for record in get_meal_ratings(target):
        meal = str(record.get("Meal", "")).strip().title()
        rating = str(record.get("Rating", "")).strip().lower()
        if meal in summary and rating in RATINGS:
            summary[meal][rating] += 1
            summary[meal]["total"] += 1

    for meal in MEALS:
        ate = summary[meal]["good"] + summary[meal]["bad"]
        summary[meal]["score"] = round(summary[meal]["good"] / ate * 100) if ate else 0

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Sheet template registry
# ══════════════════════════════════════════════════════════════════════════════
# Every tab the app touches, its exact column order, and the notes that matter
# when creating it by hand. This drives template.csv and sheet_templates/*.csv
# via `python manage_committee.py sheet-template`, so the files in the repo
# cannot drift from the code that reads the sheet.
#
# Headers must match a tab's row 1 exactly: get_all_records() maps row 1 to dict
# keys, so a rename here or there silently breaks every lookup downstream.

SHEET_TEMPLATES = [
    {
        "tab": "responses",
        "headers": RESPONSE_HEADERS,
        "written_by": "The per-dish student form at /",
        "notes": {
            "Timestamp": "YYYY-MM-DD HH:MM:SS. Never change the format — date filtering parses it.",
            "Overall": "Required, 1-5.",
            "Rice_Curry": "Optional, 1-5. Blank means not rated — never write 0.",
            "Review": "Stored html-escaped at write time.",
            "Suggestion": "Stored raw; Jinja escapes it when rendering.",
        },
    },
    {
        "tab": "daily_summary",
        "headers": SUMMARY_HEADERS,
        "written_by": "update_daily_summary_for_today(), after each submission",
        "notes": {
            "Date": "YYYY-MM-DD, plain text. Column A — the upsert finds the row by scanning it.",
            "Avg_Overall": "Recalculated on every submission for that date.",
            "Response_Count": "Submissions counted for that date.",
        },
    },
    {
        "tab": COMMITTEE_MEMBERS_TAB,
        "headers": MEMBER_HEADERS,
        "written_by": "/admin/members, or manage_committee.py",
        "notes": {
            "Email": "Column A — roster edits find the row by scanning it. Lowercase.",
            "Password_Hash": "Werkzeug scrypt hash. NEVER put a plaintext password here.",
            "Active": "TRUE or FALSE. FALSE blocks login immediately.",
            "Must_Change_Password": "TRUE forces a password change at next sign-in.",
            "Term_Start": "YYYY-MM-DD, plain text.",
            "Term_End": "YYYY-MM-DD, plain text. Blank while serving.",
            "Created_At": "YYYY-MM-DD HH:MM:SS.",
        },
    },
    {
        "tab": COMMITTEE_REVIEWS_TAB,
        "headers": REVIEW_HEADERS,
        "written_by": "The committee review page at /committee",
        "notes": {
            "Date": "YYYY-MM-DD, plain text. All filtering reads this, not Timestamp.",
            "Member_Email": "Committee reviews are attributed, unlike student feedback.",
            "Taste": "1-5. All five dimensions are required.",
            "Review": "Stored raw; Jinja escapes it on the dashboard.",
        },
    },
    {
        "tab": MENU_TAB,
        "headers": MENU_HEADERS,
        "written_by": "/admin/menu, or typed straight into this tab",
        "notes": {
            "Date": "YYYY-MM-DD, plain text. Column A — the upsert finds the row by scanning it.",
            "Breakfast": "Comma-separated dishes, e.g. 'Idli, Sambar, Coconut Chutney'. Newlines work too. Blank shows as 'Menu not published yet'.",
        },
    },
    {
        "tab": MEAL_RATINGS_TAB,
        "headers": MEAL_RATING_HEADERS,
        "written_by": "The one-tap reactions on /home",
        "notes": {
            "Date": "YYYY-MM-DD, plain text.",
            "Meal": "Breakfast, Lunch or Dinner.",
            "Rating": "good, bad or skip. Skips are counted but excluded from a meal's score.",
            "Suggestion": "Optional, stored raw. Anonymous — no identity is recorded.",
        },
    },
]
