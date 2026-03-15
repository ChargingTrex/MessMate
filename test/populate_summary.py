"""
MessMate Summary Formulas Seeding Script (populate_summary.py)
--------------------------------------------------------------
A utility script to programmatically write Google Sheets AVERAGEIF and COUNTIF 
formulas into the 'daily_summary' tab for the past 30 days. This ensures that 
new incoming data is automatically averaged and tracked over time.
"""
import sheets
from datetime import datetime, timedelta

def populate_formulas():
    print("Formatting 'daily_summary' tab with correct dates and formulas...")
    
    worksheet = sheets.get_sheet("daily_summary")
    if not worksheet:
        print("Failed to get daily_summary sheet.")
        return
        
    # The columns we need to write
    headers = [
        "Date", "Avg_Overall", "Response_Count", "Avg_Rice_Curry", "Avg_Rice_Rasam",
        "Avg_Chapati", "Avg_Chapati_Gravy", "Avg_Poriyal", "Avg_Sweet", "Avg_Salad",
        "Avg_Curd", "Avg_Papad", "Avg_Pickle"
    ]
    
    # We want to do this for the last 30 days (including today)
    # The timestamps in 'responses' are formatted as "%Y-%m-%d %H:%M:%S"
    # So we use "%Y-%m-%d" for the Date column to allow wildcard matching
    
    updates = []
    updates.append(headers)
    
    # We'll generate rows for today and the past 29 days
    for i in range(30):
        # 29 down to 0 so oldest is first
        day_offset = 29 - i 
        date_str = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        row_num = i + 2  # +2 because 1-indexed and row 1 is headers
        
        # Google sheets formulas:
        # A2&" *" matches the prefix in responses!A:A
        search_pattern = f'$A{row_num}&" *"'
        
        row = [
            date_str, # A: Date
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!B:B), "")', # B: Avg_Overall
            f'=COUNTIF(responses!$A:$A, {search_pattern})', # C: Response_Count
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!C:C), "")', # D: Avg_Rice_Curry
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!D:D), "")', # E: Avg_Rice_Rasam
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!E:E), "")', # F: Avg_Chapati
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!F:F), "")', # G: Avg_Chapati_Gravy
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!G:G), "")', # H: Avg_Poriyal
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!H:H), "")', # I: Avg_Sweet
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!I:I), "")', # J: Avg_Salad
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!J:J), "")', # K: Avg_Curd
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!K:K), "")', # L: Avg_Papad
            f'=IFERROR(AVERAGEIF(responses!$A:$A, {search_pattern}, responses!L:L), "")', # M: Avg_Pickle
        ]
        updates.append(row)
        
    # Clear the sheet and update with new data and formulas
    worksheet.clear()
    worksheet.update('A1', updates, value_input_option='USER_ENTERED')
    
    print("✅ Successfully updated the 'daily_summary' tab!")
    print("The formulas have been injected and will now auto-aggregate your responses.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    populate_formulas()
