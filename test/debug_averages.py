"""
MessMate Dashboard Math Debugger (debug_averages.py)
----------------------------------------------------
A script written to figure out why the Today's Average stat card differed from 
the line graph. It fetches the live responses and re-calculates the averages 
locally in standard output to locate type-casting bugs.
"""

import sheets
from datetime import datetime

def debug():
    print("--- Debugging Daily Summary vs Today Responses ---")
    
    # 1. Daily Summary
    summary = sheets.get_daily_summary()
    if summary:
        print("\nLast 3 Daily Summary Rows:")
        for r in summary[-3:]:
             print(r)
             
    # 2. Today Responses
    today_responses = sheets.get_today_responses()
    print(f"\nToday Responses Count: {len(today_responses)}")
    
    if len(today_responses) > 0:
        overall_total = sum([int(r.get("Overall", 0)) for r in today_responses if str(r.get("Overall", "")).isdigit()])
        today_avg = overall_total / len(today_responses)
        print(f"Calculated Today Avg: {today_avg} (Total Overall: {overall_total} / Count: {len(today_responses)})")
        
        # Look at the Overall values we parsed
        overalls = [r.get("Overall") for r in today_responses]
        print(f"Overall values pulled from today responses: {overalls}")
        
    # Let's also look at all records to see timestamp formatting
    worksheet = sheets.get_sheet("responses")
    records = worksheet.get_all_records()
    print("\nLast 5 Timestamps in Responses sheet:")
    for r in records[-5:]:
        print(f"Timestamp: '{r.get('Timestamp')}', Overall: '{r.get('Overall')}'")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    debug()
