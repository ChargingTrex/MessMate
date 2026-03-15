"""
MessMate End-to-End Database Test (test_e2e.py)
-----------------------------------------------
A verification script that tests the full data pipeline by programmatically 
sending a mock feedback row directly to the 'responses' tab and then querying 
the 'daily_summary' tab to ensure the API is reading and writing correctly.
"""

import sheets
import time

def run_tests():
    print("----- E2E Test: Sending feedback and verifying daily summary -----")
    
    # 1. Send test data
    test_feedback = {
        "Overall": "4",
        "Rice_Curry": "3",
        "Salad": "5",
        "Review": "Test review from automated script!",
        "Suggestion": "Automated script test suggestion"
    }
    
    print("\n1. Sending test feedback to 'responses' tab...")
    try:
        success = sheets.append_response(test_feedback)
        if success:
            print("  ✅ Feedback appended successfully!")
        else:
            print("  ❌ Failed to append feedback.")
            return
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return
        
    print("\nWaiting 3 seconds for Google Sheets formulas to potentially update...")
    time.sleep(3)
    
    # 2. Get data from daily_summary
    print("\n2. Fetching from 'daily_summary' tab...")
    try:
        summary_records = sheets.get_daily_summary()
        if summary_records:
            print(f"  ✅ Successfully retrieved {len(summary_records)} rows from 'daily_summary'.")
            
            # Print the most recent / last row to see if it makes sense
            last_record = summary_records[-1] if len(summary_records) > 0 else None
            if last_record:
                print(f"  📊 Most recent daily summary entry: {last_record}")
        else:
            print("  ⚠️ 'daily_summary' is empty or could not be read.")
    except Exception as e:
        print(f"  ❌ Error reading daily summary: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_tests()
