"""
MessMate Demo Data Seeding Script (seed_data.py)
------------------------------------------------
This development script injects 70 rows of realistic, diverse, mock student 
feedback data into the 'responses' tab of the Google Sheet. It generates random 
timestamps across the past 7 days to populate the dashboard charts for the VC presentation.
"""

import random
import os
import json
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# Basic configuration
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Set of sample reviews
SAMPLE_REVIEWS = [
    "Rice was a bit soggy today", 
    "Chapati was really good!",
    "Poriyal could use more seasoning", 
    "Sweet was excellent",
    "Overall decent meal", 
    "Curd was fresh", 
    "Pickle was too salty",
    "Chapati gravy was tasty", 
    "Rice quality has improved",
    "Salad was fresh and crunchy",
    "Very good food today",
    "Loved the sweet",
    "Everything was perfect",
    "Please add more salt to the rasam",
    "The curd could be thicker"
]

# Set of sample suggestions
SAMPLE_SUGGESTIONS = [
    "Puliyodarai", 
    "Chole Bhature on Sundays", 
    "More variety in sweet",
    "Lemon rice option", 
    "Sambar rice", 
    "Raita with chapati",
    "Sprouts salad", 
    "Fruit bowl option", 
    "Kesari on Fridays",
    "Gobi manchurian", 
    "Tomato soup", 
    "Papad every day"
]

def get_sheet(tab_name="responses"):
    """Authenticate and get a specific tab."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Fallback to file for local script
        try:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        except:
            print("Could not find credentials file or environment variable.")
            return None

    client = gspread.authorize(creds)
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        print("SPREADSHEET_ID missing from environment.")
        return None
        
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        print(f"Failed to access sheet: {e}")
        return None

def generate_timestamp(day_offset):
    """Generate a random timestamp between 12:00 and 14:30 for a specific day offset."""
    base_date = datetime.now() - timedelta(days=day_offset)
    
    # Random hour (12, 13, 14) and minute
    hour = random.choice([12, 13, 14])
    minute = random.randint(0, 59)
    if hour == 14:
        minute = random.randint(0, 30) # Only up to 14:30
        
    ts = base_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))
    return ts.strftime("%Y-%m-%d %H:%M:%S")

def generate_row(day_offset, overall_score, has_review, review_text, has_suggestion, suggestion_text):
    """Generate a single row of data matching the schema."""
    timestamp = generate_timestamp(day_offset)
    
    # Basic setup
    row = [timestamp, overall_score]
    
    # 50-70% fill rate for optional items
    def optional_score(base_prob, min_val, max_val):
        if random.random() < base_prob:
            return random.randint(min_val, max_val)
        return ""

    # Generate item scores according to prompt spec
    # Vary scores per item - Poriyal/Pickle tend lower(2-3), Sweet higher(3-5), Rice vary(2-4)
    rice_curry = optional_score(0.6, 2, 4)
    rice_rasam = optional_score(0.6, 2, 4) if not rice_curry else "" # roughly mutual exclusive, sometimes both
    if random.random() < 0.2: # Both
         rice_curry = optional_score(1.0, 2, 4)
         rice_rasam = optional_score(1.0, 2, 4)

    chapati = optional_score(0.7, 3, 5)
    chapati_gravy = optional_score(0.7, 2, 4)
    poriyal = optional_score(0.6, 2, 3)
    sweet = optional_score(0.5, 3, 5)
    salad = optional_score(0.5, 3, 4)
    curd = optional_score(0.6, 3, 5)
    papad = optional_score(0.6, 3, 5)
    pickle = optional_score(0.6, 2, 3)
    
    row.extend([
        rice_curry,
        rice_rasam,
        chapati,
        chapati_gravy,
        poriyal,
        sweet,
        salad,
        curd,
        papad,
        pickle,
        review_text if has_review else "",
        suggestion_text if has_suggestion else ""
    ])
    return row

def seed_data():
    from dotenv import load_dotenv
    load_dotenv()
    
    worksheet = get_sheet("responses")
    ds_worksheet = get_sheet("daily_summary")
    if not worksheet or not ds_worksheet:
        print("Aborting.")
        return

    print("Starting data seeding...")
    
    all_rows = []
    daily_summary_rows = []
    
    # Use 15 reviews and 12 suggestions spread across 70 rows
    reviews_pool = SAMPLE_REVIEWS.copy()
    suggestions_pool = SAMPLE_SUGGESTIONS.copy()
    
    # Generate 10 rows per day for last 7 days (day offset 0-6)
    for day in range(7):
        # Overall score distribution: mostly 3s and 4s
        # Requested spec: [1×1, 2×2, 3×3, 3×4, 1×5] = 10 rows
        daily_scores = [1, 2, 2, 3, 3, 3, 4, 4, 4, 5]
        random.shuffle(daily_scores)
        
        day_rows = []
        for score in daily_scores:
            # Assign review/suggestion randomly but exhaust pools
            has_review = False
            review_text = ""
            if reviews_pool and random.random() < (len(reviews_pool) / (70 - len(all_rows))):
                has_review = True
                review_text = reviews_pool.pop()
                
            has_suggestion = False
            suggestion_text = ""
            if suggestions_pool and random.random() < (len(suggestions_pool) / (70 - len(all_rows))):
                has_suggestion = True
                suggestion_text = suggestions_pool.pop()
                
            row = generate_row(day, score, has_review, review_text, has_suggestion, suggestion_text)
            all_rows.append(row)
            day_rows.append(row)
            
        # Calculate daily averages for this day
        date_str = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
        
        def calc_avg(idx):
            scores = []
            for r in day_rows:
                val = r[idx]
                if val != "":
                    try:
                        scores.append(float(val))
                    except ValueError:
                        pass
            return round(sum(scores) / len(scores), 1) if scores else 0
            
        summary_row = [
            date_str,
            calc_avg(1),   # Overall
            len(day_rows), # Response_Count
            calc_avg(2),   # Rice_Curry
            calc_avg(3),   # Rice_Rasam
            calc_avg(4),   # Chapati
            calc_avg(5),   # Chapati_Gravy
            calc_avg(6),   # Poriyal
            calc_avg(7),   # Sweet
            calc_avg(8),   # Salad
            calc_avg(9),   # Curd
            calc_avg(10),  # Papad
            calc_avg(11)   # Pickle
        ]
        daily_summary_rows.append(summary_row)

    print(f"Generated {len(all_rows)} rows across 7 days. Uploading to Sheets...")
    
    worksheet.append_rows(all_rows)
    print("✅ Seeded 70 rows into responses")
    
    print("Uploading to daily_summary sheet...")
    # Reverse so that oldest days come first chronologically (standard sheet orientation)
    daily_summary_rows.reverse()
    ds_worksheet.append_rows(daily_summary_rows)
    print("✅ Appended 7 daily averages into daily_summary")

    print("\n--- NEXT STEPS ---")
    print("1. Open the responses and daily_summary sheets to verify the new rows")
    print("2. Reload /dashboard on your local server and confirm the charts look populated")

if __name__ == "__main__":
    seed_data()
