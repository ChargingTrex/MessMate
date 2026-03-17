import sheets
from dotenv import load_dotenv
load_dotenv()

def main():
    print("Testing submission + daily summary auto-update...")
    dummy_data = {
        "Overall": 5,
        "Rice_Curry": 4,
        "Rice_Rasam": 5,
        "Chapati": 3,
        "Chapati_Gravy": 4,
        "Poriyal": 5,
        "Sweet": 4,
        "Salad": 3,
        "Curd": 5,
        "Papad": 4,
        "Pickle": 5,
        "Review": "Great food today!",
        "Suggestion": "More dessert options."
    }
    
    print("1. Appending dummy response...")
    success = sheets.append_response(dummy_data)
    print(f"Append success: {success}")
    
    if success:
        print("2. Calling update_daily_summary_for_today()...")
        update_success = sheets.update_daily_summary_for_today()
        print(f"Update success: {update_success}")
        
    print("\n3. Verifying daily_summary sheet...")
    worksheet = sheets.get_sheet("daily_summary")
    if worksheet:
        rows = worksheet.get_all_values()
        if rows and len(rows) > 1:
            print(f"Last Row: {rows[-1]}")
        else:
            print("No data in daily_summary.")
    else:
        print("Failed to get sheet.")

if __name__ == "__main__":
    main()
