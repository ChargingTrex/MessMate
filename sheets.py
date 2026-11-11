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

READS ARE CACHED. Every tab is read into memory once and served from there
until the next scheduled refresh: every 30 minutes on the clock, plus a few
minutes before breakfast, lunch and dinner open (see "Read cache" below).
Writes still go straight to Google, and also patch the cached copy, so the
app always sees its own writes immediately.
"""

import os
import re
import json
import time
import threading
import gspread
from gspread.utils import numericise
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
        _client = gspread.authorize(creds, http_client=_RetryOn429HTTPClient)
    return _client


class _RetryOn429HTTPClient(gspread.HTTPClient):
    """
    Retries a request that Google refused for quota (HTTP 429), waiting 1, 2
    then 4 seconds. Only 429: it means the request was NOT applied, so a retried
    append cannot double-write a row. A 5xx might have been applied, so it is
    left to fail. gspread's own BackOffHTTPClient is not used because it can
    retry indefinitely, which would hang a worker past gunicorn's timeout.
    """
    RETRY_WAITS = (1, 2, 4)

    def request(self, *args, **kwargs):
        for wait in self.RETRY_WAITS:
            try:
                return super().request(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                if e.code != 429:
                    raise
                print(f"Sheets quota hit (429); retrying in {wait}s", flush=True)
                time.sleep(wait)
        return super().request(*args, **kwargs)


# Spreadsheet and worksheet handles. open_by_key() and .worksheet() each fetch
# the spreadsheet's metadata, so resolving a tab per call cost two reads
# before any data moved. Handles stay valid for the life of the process.
_spreadsheet = None
_worksheets = {}   # tab name -> gspread.Worksheet


def get_sheet(tab_name):
    """
    Gets the spreadsheet by SPREADSHEET_ID env var and returns the named worksheet.
    Handles are cached, so only the first call per tab touches the API.
    Returns None on error (logged to console).
    """
    global _spreadsheet
    try:
        if tab_name in _worksheets:
            return _worksheets[tab_name]
        spreadsheet_id = os.environ.get("SPREADSHEET_ID")
        if not spreadsheet_id:
            print("ERROR: SPREADSHEET_ID environment variable not set")
            return None
        if _spreadsheet is None:
            _spreadsheet = get_client().open_by_key(spreadsheet_id)
        worksheet = _spreadsheet.worksheet(tab_name)
        _worksheets[tab_name] = worksheet
        return worksheet
    except Exception as e:
        print(f"Error accessing sheet '{tab_name}': {e}")
        return None


# ── Read cache ────────────────────────────────────────────────────────────────
# Google allows ~60 reads a minute for the whole app (one service account), and
# reading a tab is a read whether or not anything changed. So each tab is read
# once and kept in memory until the next REFRESH POINT:
#
#   * every REFRESH_EVERY_MINUTES on the clock (:00 and :30), and
#   * PRE_MEAL_REFRESH_MINUTES before each meal opens (MEAL_OPENS, below),
#     so a menu fixed just before service is what students see when it opens.
#
# A tab loaded before a refresh point is stale after it and is re-read on its
# next use; start_refresh_scheduler() also re-reads every loaded tab right at
# each point so the first visitor afterwards does not wait for Google.
#
# Writes made through this module go to Google first and then patch the cached
# copy (_cache_append / _cache_replace), so a submission shows on the dashboard
# at once and the one-review-per-meal check sees it. Admin writes to the roster
# and the menu drop that tab instead, and the next read fetches it fresh.
#
# What the cache does NOT see until the next refresh point: rows typed into the
# sheet by hand, rows written by scripts (seed_demo.py etc.), and writes made
# by ANOTHER process. The Procfile runs one gunicorn worker, so that is only a
# concern if workers are added — each would then hold its own cache.
REFRESH_EVERY_MINUTES = 30
PRE_MEAL_REFRESH_MINUTES = 10
RETRY_FAILED_LOAD_SECONDS = 60   # after a failed refresh, serve stale data this long

_cache_lock = threading.RLock()
_tab_cache = {}       # tab -> {"records": [dict, ...], "loaded_at": datetime}
_failed_at = {}       # tab -> time.monotonic() of the last failed load


def refresh_points(day):
    """Every refresh time on a calendar day, sorted, as datetimes."""
    start = datetime(day.year, day.month, day.day)
    points = {start + timedelta(minutes=m)
              for m in range(0, 24 * 60, REFRESH_EVERY_MINUTES)}
    for hour, minute in MEAL_OPENS.values():
        opens = start + timedelta(hours=hour, minutes=minute)
        points.add(opens - timedelta(minutes=PRE_MEAL_REFRESH_MINUTES))
    return sorted(points)


def next_refresh_after(moment):
    """The first refresh point strictly after `moment`."""
    for point in refresh_points(moment):
        if point > moment:
            return point
    return refresh_points(moment + timedelta(days=1))[0]


def invalidate_cache(tab=None):
    """Drops one tab's cached rows (or every tab's), so the next read refetches."""
    with _cache_lock:
        if tab is None:
            _tab_cache.clear()
            _failed_at.clear()
        else:
            _tab_cache.pop(tab, None)
            _failed_at.pop(tab, None)


def _load_tab(tab):
    """One API read: the whole tab as record dicts. Raises on failure."""
    worksheet = get_sheet(tab)
    if not worksheet:
        raise LookupError(f"sheet '{tab}' is unavailable")
    return worksheet.get_all_records()


def _cached_records(tab):
    """
    The tab's rows, from memory when fresh. Returns a new list each call so a
    caller cannot reorder the cache, but the dicts are shared: do not mutate.

    If a refresh fails and an older copy exists, the older copy is served (and
    the load is not retried for RETRY_FAILED_LOAD_SECONDS) — a dashboard a
    little out of date beats an empty one. With nothing cached, it raises, and
    each caller's own try/except decides what failure means.
    """
    with _cache_lock:
        entry = _tab_cache.get(tab)
        now = datetime.now()
        if entry and now < next_refresh_after(entry["loaded_at"]):
            return list(entry["records"])

        failed = _failed_at.get(tab)
        if entry and failed is not None and \
                time.monotonic() - failed < RETRY_FAILED_LOAD_SECONDS:
            return list(entry["records"])

        try:
            records = _load_tab(tab)
        except Exception as e:
            _failed_at[tab] = time.monotonic()
            if entry:
                print(f"Refreshing '{tab}' failed, serving cached copy: {e}")
                return list(entry["records"])
            raise

        _tab_cache[tab] = {"records": records, "loaded_at": now}
        _failed_at.pop(tab, None)
        return list(records)


def _as_read(value):
    """A written value as get_all_records() would hand it back."""
    if value is None:
        return ""
    return numericise(str(value))


def _cache_append(tab, headers, rows):
    """Adds just-written rows to the cached copy, if the tab is cached."""
    with _cache_lock:
        entry = _tab_cache.get(tab)
        if entry is None:
            return   # nothing cached: the next read loads the tab, rows included
        for row in rows:
            entry["records"].append(
                {h: _as_read(v) for h, v in zip(headers, row)})


def _cache_replace(tab, headers, match, row):
    """Replaces the first cached record where match(record) is true, or appends."""
    with _cache_lock:
        entry = _tab_cache.get(tab)
        if entry is None:
            return
        record = {h: _as_read(v) for h, v in zip(headers, row)}
        for index, existing in enumerate(entry["records"]):
            if match(existing):
                entry["records"][index] = record
                return
        entry["records"].append(record)


def _cache_remove(tab, match):
    """Drops the first cached record where match(record) is true."""
    with _cache_lock:
        entry = _tab_cache.get(tab)
        if entry is None:
            return
        for index, existing in enumerate(entry["records"]):
            if match(existing):
                del entry["records"][index]
                return


def refresh_all():
    """Re-reads every tab that has been loaded. One API read per tab."""
    with _cache_lock:
        tabs = list(_tab_cache)
    for tab in tabs:
        try:
            records = _load_tab(tab)
        except Exception as e:
            print(f"Scheduled refresh of '{tab}' failed, keeping cached copy: {e}")
            continue
        with _cache_lock:
            _tab_cache[tab] = {"records": records, "loaded_at": datetime.now()}
            _failed_at.pop(tab, None)


_scheduler_started = False


def start_refresh_scheduler():
    """
    Starts a background thread that refreshes the cache at each refresh point,
    so the first request after one is served from memory. Safe to call more
    than once; does nothing without SPREADSHEET_ID (tests, scripts).
    """
    global _scheduler_started
    if _scheduler_started or not os.environ.get("SPREADSHEET_ID"):
        return
    _scheduler_started = True

    def run():
        while True:
            wait = (next_refresh_after(datetime.now()) - datetime.now()).total_seconds()
            time.sleep(max(wait, 0) + 1)   # +1s: land just past the point
            try:
                refresh_all()
            except Exception as e:   # the thread must never die
                print(f"Cache refresh error: {e}")

    threading.Thread(target=run, name="sheets-cache-refresh", daemon=True).start()


# Column order of the student tabs, for patching the cache after a write.
# Must match row 1 of each tab, as the committee *_HEADERS lists below do.
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
        _cache_append("responses", RESPONSE_HEADERS, [row_data])
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
    try:
        records = _cached_records("responses")

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
    try:
        return _cached_records("daily_summary")
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

        _cache_replace("daily_summary", SUMMARY_HEADERS,
                       lambda r: str(r.get("Date", "")).strip() == today_str,
                       row_data)
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
    try:
        records = _cached_records("responses")
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
    "Taste", "Quality", "Variety", "Hygiene", "Menu", "Review", "Meal"
]
# Meal is LAST on purpose: it was added after the tab went live, and appending
# it keeps every existing column where it was. Rows written before it existed
# have Meal blank — a whole-day review — and count as no particular meal.

# One row per dish per review. The dish list differs meal to meal and day to
# day (it comes from the menu tab), so it cannot be fixed columns on the
# review row. Long format keeps "how has Sambar done this month" a filter.
COMMITTEE_DISH_RATINGS_TAB = "committee_dish_ratings"
DISH_RATING_HEADERS = [
    "Timestamp", "Date", "Meal", "Member_Email", "Dish", "Rating"
]

# The five dimensions the committee rates. Order matters — it drives the
# column order on write and the display order on the dashboard.
DIMENSIONS = ["Taste", "Quality", "Variety", "Hygiene", "Menu"]

# ── Roster cache ──────────────────────────────────────────────────────────────
# The roster lives in the read cache like every tab. Writes invalidate it
# immediately, which is what makes a newly added member able to log in at once
# and a deactivated one locked out at once.
#
# Each gunicorn worker holds its own cache. With more than one worker, a change
# made in worker A reaches worker B only at the next refresh point (up to
# REFRESH_EVERY_MINUTES) — including a deactivation. Keep one worker, or move
# the roster to a shared store, before scaling out.

def invalidate_roster_cache():
    """Drops the cached roster so the next read hits Sheets. Call after every write."""
    invalidate_cache(COMMITTEE_MEMBERS_TAB)


def get_committee_roster(force_refresh=False):
    """
    Returns all committee_members rows as dicts, from the read cache.
    Returns [] on error (never raises).
    """
    if force_refresh:
        invalidate_roster_cache()
    try:
        return _cached_records(COMMITTEE_MEMBERS_TAB)
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


def append_committee_review(data_dict, dish_ratings=None):
    """
    Appends one committee review row in REVIEW_HEADERS order, plus one
    committee_dish_ratings row per entry in `dish_ratings` — a list of
    (dish_name, rating) pairs in menu order.

    Dish rows are written FIRST. The review row is what has_submitted_today()
    checks, so if the dish write fails nothing is recorded and the member can
    simply retry. The other order would mark the meal reviewed with its dish
    ratings missing and no way to resubmit. A failure between the two writes
    can leave orphan dish rows; get_committee_dish_ratings() ignores dish rows
    with no matching review row for exactly that reason.

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
        stamp = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        email = str(data_dict.get("Member_Email", "")).strip().lower()
        meal = data_dict.get("Meal", "")

        if dish_ratings:
            dish_sheet = get_sheet(COMMITTEE_DISH_RATINGS_TAB)
            if not dish_sheet:
                return False
            dish_rows = [[stamp, date_str, meal, email, dish, rating]
                         for dish, rating in dish_ratings]
            dish_sheet.append_rows(dish_rows, value_input_option="RAW")
            _cache_append(COMMITTEE_DISH_RATINGS_TAB, DISH_RATING_HEADERS, dish_rows)

        row_data = [
            stamp,                               # Timestamp
            date_str,                            # Date — plain text, never parsed
            email,
            data_dict.get("Member_Name", ""),
            data_dict.get("Taste", ""),
            data_dict.get("Quality", ""),
            data_dict.get("Variety", ""),
            data_dict.get("Hygiene", ""),
            data_dict.get("Menu", ""),
            data_dict.get("Review", ""),
            meal,                                # Meal — Breakfast / Lunch / Dinner
        ]
        worksheet.append_row(row_data, value_input_option="RAW")
        _cache_append(COMMITTEE_REVIEWS_TAB, REVIEW_HEADERS, [row_data])
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
        records = _cached_records(COMMITTEE_REVIEWS_TAB)

        if days is None:
            return records

        cutoff = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        # Dates are ISO-formatted, so string comparison is chronological
        return [r for r in records
                if str(r.get("Date", "")).strip() >= cutoff]
    except Exception as e:
        print(f"Error reading committee reviews: {e}")
        return []


def reviewed_meals(email, date_str=None):
    """
    The meals this member has reviewed on a date (default today), as a set of
    MEALS names. A legacy whole-day row (blank Meal) adds nothing.

    Fails OPEN like has_submitted_today(): an unreachable sheet reads as
    "nothing reviewed yet".
    """
    if not email:
        return set()

    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    target_email = str(email).strip().lower()

    meals = set()
    for record in get_committee_reviews():
        if (str(record.get("Date", "")).strip() == target_date and
                str(record.get("Member_Email", "")).strip().lower() == target_email):
            meal = str(record.get("Meal", "")).strip().title()
            if meal in MEALS:
                meals.add(meal)
    return meals


def has_submitted_today(email, date_str=None, meal=None):
    """
    With `meal`: True if this member has already reviewed that meal on the
    given date (defaults to today) — the one-review-per-meal-per-day rule.

    Without `meal`: True if they have any review row that date, legacy
    whole-day rows included. Dashboards use this for "has rated today".

    Fails OPEN: if the sheet is unreachable this returns False, so an outage
    lets a member through rather than locking the committee out entirely.
    """
    if not email:
        return False

    if meal:
        return meal in reviewed_meals(email, date_str)

    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    target_email = str(email).strip().lower()

    for record in get_committee_reviews():
        if (str(record.get("Date", "")).strip() == target_date and
                str(record.get("Member_Email", "")).strip().lower() == target_email):
            return True
    return False


def get_committee_dish_ratings(date_str=None):
    """
    Per-dish committee ratings, optionally for one date, as record dicts.

    Only rows backed by a committee_reviews row (same Date, Meal and member)
    are returned, so orphans from a half-failed write never count — see
    append_committee_review(). [] on error.
    """
    try:
        records = _cached_records(COMMITTEE_DISH_RATINGS_TAB)

        def key(r):
            return (str(r.get("Date", "")).strip(),
                    str(r.get("Meal", "")).strip().title(),
                    str(r.get("Member_Email", "")).strip().lower())

        filed = {key(r) for r in get_committee_reviews()}
        return [r for r in records
                if key(r) in filed and
                (date_str is None or key(r)[0] == date_str)]
    except Exception as e:
        print(f"Error reading committee dish ratings: {e}")
        return []


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

# ── Menu categories ──────────────────────────────────────────────────────────
# The rows of the mess's own weekly sheet, in its order and under its names
# (snacks are not served as a meal here, so they are left out). A dish is
# stored as "Category: Dish", one per line, inside the meal's cell — so the
# menu tab keeps its Date/Breakfast/Lunch/Dinner columns and a dish typed
# without a category still works. The labels describe the sheet's rows, not
# the dish in them: the mess sometimes puts a gravy under "Korma" or a curry
# under "Dry Poriyal", and the app keeps their naming rather than guess.
# A repeated name ("Spread" for butter and jam) is two rows in the CSV
# template, shown to students as one line.
MENU_CATEGORIES = {
    "Breakfast": [
        "Main Item", "Side Dish", "Chutney", "Vada / Banana", "Egg",
        "Bread", "Spread", "Spread", "Beverage",
    ],
    "Lunch": [
        "Bread", "Side Dish", "Rice", "Sambar / Kulambu", "Poriyal / Kootu",
        "Rasam", "Papad / Fryums", "Curd", "Pickle", "Podi / Oil & Thogayal",
        "Sweet / Fruits",
    ],
    "Dinner": [
        "Rice", "Dry Poriyal", "Bread / Tiffin", "Korma", "Rasam", "Curd",
        "Pickle", "Milk / Tea / Coffee",
    ],
}


def _menu_text(pairs):
    """[("Main Item", "Idiy"), ("", "Tea")] -> "Main Item: Idiy\\nTea"."""
    return "\n".join(f"{c}: {d}" if c else d for c, d in pairs if d)


# ── Weekly template ──────────────────────────────────────────────────────────
# A starting point for the admin menu editor, keyed by weekday (0=Monday).
# It is deliberately NOT shown to students: a day with nothing published
# renders as "Menu not published yet" (see CONTRIBUTING.md). A fabricated menu
# that happens to be wrong is a worse message than an honest blank, so the
# template only ever reaches the sheet when an admin fills a day from it and
# saves. seed_demo.py reuses it for demo data.
#
# The dishes are Sai University's menu for the 2nd week of November 2026,
# under the categories above. The mess rotates its menu, so treat this as a
# week to adapt, not the week to publish.
_B, _L, _D = (MENU_CATEGORIES[m] for m in MEALS)

WEEKLY_MENU_DEFAULTS = {
    0: {  # Monday
        "Breakfast": _menu_text(zip(_B, [
            "Mix Veg Sevai", "Tiffin Sambar", "Coconut Chutney", "Masala Vada",
            "Boiled Egg", "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Chapathi", "Green Gram Kurma", "Steamed Rice", "Mullangi Sambar",
            "Beetroot Chana Poriyal", "Tomato Rasam", "Fryums", "Curd", "",
            "Gongura Thovayal", "Mix Fruit"])),
        "Dinner": _menu_text(zip(_D, [
            "Mint Pulao / Steamed Rice", "Veg Makhanwala", "Chappathi",
            "Andhra Tomato Pappu", "Rasam", "Curd", "Pickle / Podi & Oil",
            "Milk"])),
    },
    1: {  # Tuesday
        "Breakfast": _menu_text(zip(_B, [
            "Idly", "Tiffin Sambar", "Peanut Chutney", "Banana", "Boiled Egg",
            "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Malabar Paratha", "Paneer Peas Curry", "Mushroom Biryani",
            "Onion Raitha", "Steamed Rice", "Garlic Rasam", "Fryums", "Curd",
            "Pickle", "Poondu Podi & Oil", "Sago Dal Payasam"])),
        "Dinner": _menu_text(zip(_D, [
            "Steamed Rice", "Aloo Peas Masala Dry", "Mix Veg Uttapam",
            "Kaikari Sambar", "Rasam", "Curd", "Thengai Thogayal", "Milk"])),
    },
    2: {  # Wednesday
        "Breakfast": _menu_text(zip(_B, [
            "Pongal", "Tiffin Sambar", "Coconut Chutney", "Medhu Vada",
            "Boiled Egg", "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Chappathi", "Dal Tadka", "Steamed Rice", "Bonda Mor Kuzhambu",
            "Kovakkai Kara Masala", "Mysore Rasam", "Fryums", "Curd", "",
            "Mint Thovayal", "Green Banana"])),
        "Dinner": _menu_text(zip(_D, [
            "Steamed Rice", "Paneer Butter Masala", "Malabar Parotta",
            "Karaikudi Chicken Curry", "Rasam", "Curd", "Pickle / Podi & Oil",
            "Milk"])),
    },
    3: {  # Thursday
        "Breakfast": _menu_text(zip(_B, [
            "Podi Dosa", "Tiffin Sambar", "Mix Dal Kara Chutney", "Banana",
            "Boiled Egg", "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Malabar Paratha", "Veg Salna", "Steamed Rice",
            "Mix Vathal Kara Kuzhambu", "Pudalangai Kootu", "Aravai Rasam",
            "Appalam", "Curd", "Pickle", "Curry Leaves Podi & Oil",
            "Thinai Arisi Payasam"])),
        "Dinner": _menu_text(zip(_D, [
            "Veg Chettinad / Steamed Rice", "Cucumber Raita", "Chappathi",
            "Chow Chow Kurma", "Rasam", "Curd", "Onion Peanut Thogayal",
            "Milk"])),
    },
    4: {  # Friday
        "Breakfast": _menu_text(zip(_B, [
            "Rava Kichadi", "Tiffin Sambar", "Coconut Chutney", "Masala Vada",
            "", "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Chapathi", "Double Beans Kurma", "Soya Peas Pulao",
            "Mix Veg Masala Dry", "Steamed Rice", "Lemon Rasam", "Fryums",
            "Curd", "", "Beetroot Thogayal", "Cut Watermelon"])),
        "Dinner": _menu_text(zip(_D, [
            "Steamed Rice", "Kalan Peas Semi Gravy", "Kal Dosa", "Egg Curry",
            "Rasam", "Curd", "Pickle / Podi & Oil", "Milk"])),
    },
    5: {  # Saturday
        "Breakfast": _menu_text(zip(_B, [
            "Set Dosa", "Vada Curry", "Kara Chutney", "", "Boiled Egg",
            "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "Chapathi", "Mirchi Ka Salan", "Steamed Rice",
            "Mochai Puli Kuzhambu", "Cabbage Kootu", "Arachuvitta Rasam",
            "Appalam", "Curd", "Pickle", "Dal Podi & Oil", "Fruit Kesari"])),
        "Dinner": _menu_text(zip(_D, [
            "Jeera Pulao / Steamed Rice", "Mix Veg Tawa Dry", "Malabar Parotta",
            "Vegetable Salna", "Rasam", "Curd", "Mint Thogayal", "Milk"])),
    },
    6: {  # Sunday
        "Breakfast": _menu_text(zip(_B, [
            "Semiya Bath", "Tiffin Sambar", "Coconut Chutney", "Methu Vada",
            "Boiled Egg", "Bread", "Butter", "Jam", "Coffee"])),
        "Lunch": _menu_text(zip(_L, [
            "", "Veg Briyani", "Chicken Briyani", "Plain Salan", "Steamed Rice",
            "Aravai Puli Rasam", "Mix Veg 65", "Onion Raitha", "Pickle", "",
            "Ice Cream"])),
        "Dinner": _menu_text(zip(_D, [
            "Steamed Rice", "Lauki Chana Masala", "Chappathi",
            "Chettinad Veg Kurma", "Mint Rasam", "Curd",
            "Pickle / Dal Podi & Oil", "Milk"])),
    },
}


def menu_template_for_date(date_str):
    """{"Breakfast": "Idli, ...", ...} from the weekly template for one date."""
    try:
        weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    except (ValueError, TypeError):
        return {meal: "" for meal in MEALS}
    template = WEEKLY_MENU_DEFAULTS.get(weekday, {})
    return {meal: template.get(meal, "") for meal in MEALS}


def week_start(date_str=None):
    """
    The Monday on or before a date, as YYYY-MM-DD. The editor pages by
    calendar week because that is how a mess plans: Monday to Sunday.
    """
    try:
        day = (datetime.strptime(date_str, "%Y-%m-%d") if date_str
               else datetime.now())
    except (ValueError, TypeError):
        day = datetime.now()
    return (day - timedelta(days=day.weekday())).strftime("%Y-%m-%d")


# Menu reads happen on every home-page load and come from the read cache. A
# menu saved in the admin editor drops the cached copy, so it shows at once.


def invalidate_menu_cache():
    """Drops the cached menu. Called after every menu write."""
    invalidate_cache(MENU_TAB)


def get_menu_records(force_refresh=False):
    """All rows of the menu tab as dicts, cached. [] on error."""
    if force_refresh:
        invalidate_menu_cache()
    try:
        return _cached_records(MENU_TAB)
    except Exception as e:
        print(f"Error reading menu: {e}")
        return []


_CATEGORY_RE = re.compile(r"^([^:]{1,40}):(.*)$")


def menu_entries(raw):
    """
    A meal cell as [(category, dish), ...], in order.

        'Main Item: Pongal\\nChutney: Coconut Chutney, Tea'
        -> [('Main Item', 'Pongal'), ('Chutney', 'Coconut Chutney'), ('', 'Tea')]

    Dishes are separated by commas or newlines. "Category: Dish" carries a
    category; a bare dish has category "". A category with no dish after it
    (a blank row left from the template) is dropped, not published.
    """
    text = str(raw or "").replace("\n", ",")
    entries = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = _CATEGORY_RE.match(part)
        if match:
            category, dish = match.group(1).strip(), match.group(2).strip()
            if dish:
                entries.append((category, dish))
        else:
            entries.append(("", part))
    return entries


def _split_items(raw):
    """
    The dish names of a meal cell, categories left off — what ratings and the
    committee form key on. 'Idli, Rice: Sambar' -> ['Idli', 'Sambar'].
    """
    return [dish for _, dish in menu_entries(raw)]


def menu_groups(raw):
    """
    A meal cell for display: [{"category": str, "dishes": [str]}, ...].
    Consecutive dishes under one category share a group ("Spread: Butter,
    Jam"); a dish without a category is a group of its own, as before.
    """
    groups = []
    for category, dish in menu_entries(raw):
        if category and groups and groups[-1]["category"] == category:
            groups[-1]["dishes"].append(dish)
        else:
            groups.append({"category": category, "dishes": [dish]})
    return groups


def normalise_menu_text(raw):
    """
    The stored form of a meal cell: one "Category: Dish" (or bare dish) per
    line, blank category rows dropped, so a template row nobody filled in
    never counts as published.
    """
    return _menu_text(menu_entries(raw))


def _menu_rows_by_date():
    """{date: row} for every published row, latest row winning a duplicate."""
    return {str(r.get("Date", "")).strip(): r for r in get_menu_records()}


def get_menu_for_date(date_str=None):
    """
    Returns {"Breakfast": [...], "Lunch": [...], "Dinner": [...]} for one date.
    Meals with nothing published come back as empty lists, which the home page
    renders as "not published yet" rather than pretending the mess is closed —
    or inventing a menu. The weekly template is an editor convenience only.
    """
    target = date_str or datetime.now().strftime("%Y-%m-%d")
    row = _menu_rows_by_date().get(target, {})
    return {meal: _split_items(row.get(meal, "")) for meal in MEALS}


def get_menu_groups_for_date(date_str=None):
    """
    Same date lookup as get_menu_for_date(), shaped for display:
    {"Breakfast": [{"category": "Main Item", "dishes": ["Pongal"]}, ...], ...}.
    """
    target = date_str or datetime.now().strftime("%Y-%m-%d")
    row = _menu_rows_by_date().get(target, {})
    return {meal: menu_groups(row.get(meal, "")) for meal in MEALS}


def get_menu_week(start_date=None, days=7):
    """
    One entry per day from start_date (default: today), for the editor and the
    home page's day switcher. Each entry carries:

        date, label, weekday, is_today, is_past
        Breakfast / Lunch / Dinner   what is published — "" when nothing is
        published                    {meal: bool} — True when a value is stored
        template                     {meal: str}  — the weekly template, as a
                                     suggestion for the editor to offer
        has_row                      the date has a row in the sheet at all
    """
    start = (datetime.strptime(start_date, "%Y-%m-%d") if start_date
             else datetime.now())
    rows = _menu_rows_by_date()
    today_str = datetime.now().strftime("%Y-%m-%d")

    week = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        date_str = day.strftime("%Y-%m-%d")
        row = rows.get(date_str)
        stored = {meal: str((row or {}).get(meal, "") or "").strip()
                  for meal in MEALS}

        entry = {
            "date": date_str,
            "label": day.strftime("%a %d %b"),
            "weekday": day.strftime("%A"),
            "is_today": date_str == today_str,
            "is_past": date_str < today_str,
            "has_row": row is not None,
            "published": {meal: bool(stored[meal]) for meal in MEALS},
            "template": menu_template_for_date(date_str),
        }
        entry.update(stored)
        week.append(entry)
    return week


def save_menu_for_date(date_str, breakfast, lunch, dinner):
    """
    Upserts one day's menu: updates the row if that date exists, appends if not.
    Mirrors update_daily_summary_for_today()'s row-lookup pattern, which is why
    Date must stay in column A.

    Returns True on success, False on failure.
    """
    return save_menu_week([(date_str, breakfast, lunch, dinner)])


def save_menu_week(days):
    """
    Upserts several days at once. `days` is a list of
    (date_str, breakfast, lunch, dinner) tuples.

    One col_values read finds the existing rows; each of those is updated in
    place, and every new date goes out in a single append_rows call — so a
    whole unpublished week costs two API calls rather than fourteen.

    Returns True on success, False on failure.
    """
    if not days:
        return True

    try:
        worksheet = get_sheet(MENU_TAB)
        if not worksheet:
            return False

        dates = [str(v).strip() for v in worksheet.col_values(1)]
        new_rows = []
        for date_str, breakfast, lunch, dinner in days:
            row_data = [date_str] + [normalise_menu_text(m)
                                     for m in (breakfast, lunch, dinner)]
            if date_str in dates:
                row_index = dates.index(date_str) + 1   # gspread is 1-indexed
                worksheet.update(f"A{row_index}:D{row_index}", [row_data])
            else:
                new_rows.append(row_data)
                dates.append(date_str)   # a date repeated in `days` updates, not duplicates

        if new_rows:
            if len(new_rows) == 1:
                worksheet.append_row(new_rows[0], value_input_option="RAW")
            else:
                worksheet.append_rows(new_rows, value_input_option="RAW")

        invalidate_menu_cache()
        return True
    except Exception as e:
        print(f"Error saving menu: {e}")
        return False


def append_meal_rating(meal, rating, suggestion=""):
    """
    Stores one quick reaction. Anonymous: no identity, no IP, nothing that
    could tie the row to a student — the same promise the per-dish form makes.

    Suggestion is stored RAW; Jinja escapes it when the dashboard renders it.

    Returns the row's Timestamp string on success (truthy; the device cookie
    keeps it so the tap can be undone), "" on failure.
    """
    try:
        worksheet = get_sheet(MEAL_RATINGS_TAB)
        if not worksheet:
            return False

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [stamp, stamp[:10], meal, rating, suggestion]
        worksheet.append_row(row, value_input_option="RAW")
        _cache_append(MEAL_RATINGS_TAB, MEAL_RATING_HEADERS, [row])
        return stamp
    except Exception as e:
        print(f"Error appending meal rating: {e}")
        return ""


def get_meal_ratings(date_str=None):
    """
    Meal ratings, optionally for one date. [] on error.
    """
    try:
        records = _cached_records(MEAL_RATINGS_TAB)
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


# ── Serving windows as rules, and taking a tap back ───────────────────────────
# MEAL_TIMINGS above is the display string. These are the same windows as
# numbers, so the home page can refuse a rating for a meal that has not been
# served yet: a student cannot have an opinion about dinner at 8 am, and a row
# that says they do is noise the committee would average. A meal stays open
# after its window ends — someone who ate late still ate.
MEAL_OPENS = {
    "Breakfast": (7, 30),
    "Lunch": (12, 0),
    "Dinner": (19, 30),
}
MEAL_OPENS_LABEL = {
    "Breakfast": "7:30 am",
    "Lunch": "12:00 pm",
    "Dinner": "7:30 pm",
}


def meal_is_open(meal, now=None):
    """True once today's serving window for `meal` has started."""
    hour, minute = MEAL_OPENS.get(meal, (0, 0))
    now = now or datetime.now()
    return (now.hour, now.minute) >= (hour, minute)


def delete_meal_rating(timestamp, date_str, meal):
    """
    Removes one quick reaction, identified by the Timestamp, Date and Meal the
    device remembered when it tapped. Used by Undo. Deletes the first matching
    row only; the fields together are as good as unique.

    Returns True when a row was removed, False otherwise.
    """
    try:
        worksheet = get_sheet(MEAL_RATINGS_TAB)
        if not worksheet:
            return False
        for index, record in enumerate(worksheet.get_all_records()):
            if (str(record.get("Timestamp", "")).strip() == timestamp
                    and str(record.get("Date", "")).strip() == date_str
                    and str(record.get("Meal", "")).strip().title() == meal):
                worksheet.delete_rows(index + 2)   # row 1 is the header
                _cache_remove(MEAL_RATINGS_TAB, lambda r: (
                    str(r.get("Timestamp", "")).strip() == timestamp
                    and str(r.get("Date", "")).strip() == date_str
                    and str(r.get("Meal", "")).strip().title() == meal))
                return True
        return False
    except Exception as e:
        print(f"Error deleting meal rating: {e}")
        return False
