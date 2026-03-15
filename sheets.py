"""
MessMate Google Sheets Database Interface (sheets.py)
---------------------------------------------------
This module acts as the database layer for the application.
It uses the `gspread` library and Google Cloud Service Account credentials
to authenticate and interact with the 'MessMate Base' Google Sheet.
Functions here handle fetching live trend data, finding today's responses,
reading suggestions, and appending new student feedback.
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

def get_client():
    # Locally: reads from credentials.json file
    # On Render/Railway: reads from environment variable
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

    if creds_json:
        # Production — credentials stored as env variable
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Local development — credentials stored as file
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

    return gspread.authorize(creds)

def get_sheet(tab_name):
    """Helper formatting spreadsheet fetch."""
    try:
        client = get_client()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID")
        if not spreadsheet_id:
            print("SPREADSHEET_ID environment variable not set")
            return None
        spreadsheet = client.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        print(f"Error accessing sheet {tab_name}: {e}")
        return None

def append_response(data_dict):
    """Appends one row to 'responses' tab."""
    worksheet = get_sheet("responses")
    if not worksheet:
        return False
    
    # Adding timestamp automatically
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Matches Google Sheet column order:
    # Timestamp, Overall, Rice_Curry, Rice_Rasam, Chapati, Chapati_Gravy, Poriyal,
    # Sweet, Salad, Curd, Papad, Pickle, Review, Suggestion
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
    
    worksheet.append_row(row_data)
    return True

def get_daily_summary():
    """Reads all rows from 'daily_summary' tab."""
    worksheet = get_sheet("daily_summary")
    if not worksheet:
        return []
    return worksheet.get_all_records()

def get_today_responses():
    """Filters today's rows from 'responses'."""
    worksheet = get_sheet("responses")
    if not worksheet:
        return []
    
    records = worksheet.get_all_records()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    today_responses = []
    for record in records:
        ts = str(record.get("Timestamp", ""))
        if ts.startswith(today_str):
            today_responses.append(record)
            
    return today_responses

def get_all_suggestions():
    """Returns all non-blank Suggestion values."""
    worksheet = get_sheet("responses")
    if not worksheet:
        return []
        
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
