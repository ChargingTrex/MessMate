import sheets
from dotenv import load_dotenv
load_dotenv()

def main():
    worksheet = sheets.get_sheet("daily_summary")
    if worksheet:
        headers = worksheet.row_values(1)
        print("headers:", headers)
    else:
        print("Could not get sheet.")

if __name__ == "__main__":
    main()
