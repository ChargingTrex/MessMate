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
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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
