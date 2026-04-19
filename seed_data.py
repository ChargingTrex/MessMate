"""
MessMate Demo Data Seeding Script (seed_data.py)
-------------------------------------------------
Populates the 'responses' tab with 70 rows across 7 days (10/day) for the VC demo.
Also writes daily summaries via sheets.update_daily_summary_for_today().

Uses sheets.py functions (append_response, update_daily_summary_for_today) with
date_override parameter to seed past days.

Score distribution per day (10 rows):
  1×1, 2×2, 3×3, 3×4, 1×5 — realistic bell curve

Usage:
  python seed_data.py
"""

import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env before importing sheets (which needs SPREADSHEET_ID)
load_dotenv()

import sheets


# ── Sample Data ───────────────────────────────────────────────────────────────

REVIEW_TEXTS = [
    "Rice was a bit soggy today",
    "Chapati was really good!",
    "Poriyal could use more seasoning",
    "Sweet was excellent",
    "Overall decent meal",
    "Curd was fresh",
    "Pickle was too salty",
    "Chapati gravy was tasty",
    "Rice quality has improved",
    "Salad was fresh and crunchy"
]

SUGGESTION_TEXTS = [
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


def generate_timestamp(day_offset):
    """Generate a random timestamp between 12:00 and 14:30 for a specific day offset."""
    base_date = datetime.now() - timedelta(days=day_offset)

    # Random hour (12, 13, 14) and minute
    hour = random.choice([12, 13, 14])
    minute = random.randint(0, 59)
    if hour == 14:
        minute = random.randint(0, 30)  # Only up to 14:30

    ts = base_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def optional_rating(fill_prob, min_val, max_val):
    """Return a random rating with given probability, or empty string if skipped."""
    if random.random() < fill_prob:
        return random.randint(min_val, max_val)
    return ""


def seed_data():
    """Seed 300 rows of realistic demo data across 30 days."""

    print("🌱 Starting MessMate data seeding...")
    print(f"   Seeding 300 rows across 30 days (10 per day)")
    print()

    # Pools for reviews and suggestions — distributed across all rows
    reviews_pool = list(REVIEW_TEXTS)
    suggestions_pool = list(SUGGESTION_TEXTS)
    random.shuffle(reviews_pool)
    random.shuffle(suggestions_pool)

    total_rows = 0
    total_remaining = 300

    # Seed oldest day first (day 29) through today (day 0)
    for day_offset in range(29, -1, -1):
        day_date = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")

        # Overall score distribution: 1×1, 2×2, 3×3, 3×4, 1×5 (realistic bell curve)
        daily_scores = [1, 2, 2, 3, 3, 3, 4, 4, 4, 5]
        random.shuffle(daily_scores)

        print(f"   Day {day_date} (offset -{day_offset}): ", end="")

        for i, overall in enumerate(daily_scores):
            # Generate per-item ratings with realistic skews
            # Rice: 2-4, 50-70% fill rate
            rice_curry = optional_rating(0.6, 2, 4)
            rice_rasam = ""
            if not rice_curry:
                # If no curry, maybe rasam
                rice_rasam = optional_rating(0.6, 2, 4)
            elif random.random() < 0.2:
                # 20% chance both are served
                rice_rasam = optional_rating(1.0, 2, 4)

            chapati = optional_rating(0.7, 2, 4)
            chapati_gravy = optional_rating(0.7, 2, 4)
            poriyal = optional_rating(0.6, 2, 3)       # Skew lower
            sweet = optional_rating(0.5, 3, 5)          # Skew higher
            salad = optional_rating(0.5, 3, 4)
            curd = optional_rating(0.6, 3, 5)
            papad = optional_rating(0.6, 3, 5)
            pickle = optional_rating(0.6, 2, 3)         # Skew lower

            # Assign review text (probabilistic, exhaust pool)
            review = ""
            if reviews_pool and random.random() < (len(reviews_pool) / max(total_remaining, 1)):
                review = reviews_pool.pop()

            # Assign suggestion text (probabilistic, exhaust pool)
            suggestion = ""
            if suggestions_pool and random.random() < (len(suggestions_pool) / max(total_remaining, 1)):
                suggestion = suggestions_pool.pop()

            # Build data dict matching sheets.append_response format
            data_dict = {
                "Overall": overall,
                "Rice_Curry": rice_curry,
                "Rice_Rasam": rice_rasam,
                "Chapati": chapati,
                "Chapati_Gravy": chapati_gravy,
                "Poriyal": poriyal,
                "Sweet": sweet,
                "Salad": salad,
                "Curd": curd,
                "Papad": papad,
                "Pickle": pickle,
                "Review": review,
                "Suggestion": suggestion
            }

            # We need to write the timestamp manually for past days
            # Use get_sheet directly to append with a custom timestamp
            timestamp = generate_timestamp(day_offset)
            ws = sheets.get_sheet("responses")
            if ws:
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
                ws.append_row(row_data)

            total_rows += 1
            total_remaining -= 1

        print(f"✅ 10 rows seeded")

        # Update daily summary for this day using date_override
        try:
            sheets.update_daily_summary_for_today(date_override=day_date)
            print(f"   └─ Daily summary updated for {day_date}")
        except Exception as e:
            print(f"   └─ ⚠️ Failed to update summary for {day_date}: {e}")

    print()
    print(f"🎉 Seeded {total_rows} rows across 7 days. Daily summaries written.")
    print()
    print("📊 Next steps:")
    print("   1. Open /dashboard?token=YOUR_TOKEN to verify charts")
    print("   2. Check the Google Sheet to confirm data rows")


if __name__ == "__main__":
    seed_data()
