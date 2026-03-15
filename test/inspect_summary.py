"""
MessMate Dashboard Debug Tool (inspect_summary.py)
--------------------------------------------------
A small utility script to quickly fetch and print the headers and first/last 
rows of the 'daily_summary' tab. Useful for diagnosing formula mismatches.
"""

import sheets

def inspect():
    worksheet = sheets.get_sheet("daily_summary")
    if not worksheet:
        print("Failed to get daily_summary sheet")
        return
        
    all_values = worksheet.get_all_values()
    print(f"Total rows: {len(all_values)}")
    if all_values:
        print("Headers:")
        print(all_values[0])
        print("First data row:")
        if len(all_values) > 1:
            print(all_values[1])
        print("Last data row:")
        print(all_values[-1])

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    inspect()
