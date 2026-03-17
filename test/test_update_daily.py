import sheets
from dotenv import load_dotenv
load_dotenv()

def main():
    print("Fetching today's responses...")
    today_responses = sheets.get_today_responses()
    print(f"Found {len(today_responses)} responses for today.")
    
    print("\nUpdating daily summary for today...")
    success = sheets.update_daily_summary_for_today()
    if success:
        print("Successfully updated daily summary!")
    else:
        print("Failed to update daily summary.")
        
    print("\nFetching daily summary headers to verify update...")
    worksheet = sheets.get_sheet("daily_summary")
    if worksheet:
        rows = worksheet.get_all_values()
        if rows:
            print("Headers:", rows[0])
            if len(rows) > 1:
                print("Last Row:", rows[-1])
        else:
            print("Sheet is empty.")
    else:
        print("Could not get sheet.")

if __name__ == "__main__":
    main()
