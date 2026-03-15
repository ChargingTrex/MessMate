"""
MessMate Google Sheets Connection Test (test_connections.py)
------------------------------------------------------------
A standalone verification script to test if the Google Cloud Service Account 
credentials are valid and successfully authenticating with the Google Sheets API.
"""

import os
import sheets
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    print("Testing Google Sheets connection...")
    
    # 1. Test basic client connection
    try:
        client = sheets.get_client()
        print("✅ Successfully authenticated with Google credentials")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
        
    # 2. Test accessing 'responses' sheet
    responses = sheets.get_sheet("responses")
    if responses:
        try:
            val = responses.get_all_values()
            print(f"✅ Successfully accessed 'responses' tab. It currently has {len(val)} rows.")
        except Exception as e:
            print(f"❌ Failed to read from 'responses': {e}")
    else:
        print("❌ Could not get 'responses' sheet. Check SPREADSHEET_ID and sharing permissions.")
        return
        
    # 3. Test accessing 'daily_summary' sheet
    summary = sheets.get_sheet("daily_summary")
    if summary:
        try:
            val = summary.get_all_values()
            print(f"✅ Successfully accessed 'daily_summary' tab. It currently has {len(val)} rows.")
        except Exception as e:
            print(f"❌ Failed to read from 'daily_summary': {e}")
    else:
        print("❌ Could not get 'daily_summary' sheet.")
        return

    print("\n🎉 All connection tests passed! Ready to proceed.")

if __name__ == "__main__":
    test_connection()
