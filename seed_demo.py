"""
MessMate Demo Data Seeder (seed_demo.py)
-----------------------------------------
Fills every dashboard with realistic 30-day demo data ending *today*:

    /dashboard            responses + daily_summary
    /home                 menu + meal_ratings
    /dashboard/committee  committee_members + committee_reviews

Supersedes seed_data.py, which wrote one row per API call (300+ calls, well
past Google's 60-writes-per-minute-per-user quota) and only covered the
student dashboard. Every tab here is written in a single append_rows() call.

Summaries are computed locally from the generated rows rather than by calling
update_daily_summary_for_today() once per day — same arithmetic, 1 API call
instead of 60.

Usage:
    python seed_demo.py --dry-run     # print what would be written, touch nothing
    python seed_demo.py --yes         # wipe data rows and reseed all tabs
    python seed_demo.py --yes --keep  # append without wiping
    python seed_demo.py --yes --only responses,daily_summary
"""

import argparse
import random
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

# .env must load before sheets is imported — it reads SPREADSHEET_ID at call time
load_dotenv()

import sheets
import auth


# Fixed seed: re-running produces the same demo data, so a screenshot taken
# today still matches the sheet tomorrow.
random.seed(20260930)

DAYS = 30                      # days of history, ending today
COMMITTEE_PASSWORD = "MessMate@2026"   # demo password shared by every seeded member


# ── Sample text ───────────────────────────────────────────────────────────────

REVIEW_TEXTS = [
    "Rice was a bit soggy today", "Chapati was really good!",
    "Poriyal could use more seasoning", "Sweet was excellent",
    "Overall a decent meal", "Curd was fresh", "Pickle was too salty",
    "Chapati gravy was tasty", "Rice quality has improved",
    "Salad was fresh and crunchy", "Sambar was watery",
    "Loved the payasam today", "Food was served cold",
    "Portions were generous", "Dinner was much better than lunch",
    "Chapati was undercooked", "Please keep the counter cleaner",
    "Best meal this week", "Rasam had good pepper",
]

SUGGESTION_TEXTS = [
    "Puliyodarai", "Chole Bhature on Sundays", "More variety in sweet",
    "Lemon rice option", "Sambar rice", "Raita with chapati",
    "Sprouts salad", "Fruit bowl option", "Kesari on Fridays",
    "Gobi manchurian", "Tomato soup", "Papad every day",
    "Millet dosa once a week", "Less oil in the gravy",
    "Hot water for tea after 9pm", "Boiled eggs at breakfast",
    "Curd rice on hot days", "Mushroom curry sometimes",
]

COMMITTEE_REVIEW_TEXTS = [
    "Kitchen hygiene was satisfactory during the inspection.",
    "Oil usage in the gravy is still higher than agreed.",
    "Variety has improved since last week's meeting.",
    "Serving counter was cleaned on schedule today.",
    "Rice quality is consistent; sambar needs more dal.",
    "Vegetables looked fresh at the morning check.",
    "Staff were wearing gloves and caps throughout.",
    "Menu deviated from the published plan for dinner.",
    "Portion sizes at dinner were below the standard.",
    "Water storage area needs attention this week.",
    "Good improvement in the breakfast turnaround time.",
    "Requested millet options are now on the menu.",
]

COMMITTEE_MEMBERS = [
    ("arjun.r@messmate.demo",   "Arjun Ramesh"),
    ("priya.n@messmate.demo",   "Priya Natarajan"),
    ("karthik.s@messmate.demo", "Karthik Subramanian"),
    ("divya.m@messmate.demo",   "Divya Menon"),
    ("faizal.a@messmate.demo",  "Faizal Ahmed"),
]

ITEM_COLUMNS = [
    "Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy",
    "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle",
]

SUMMARY_HEADERS = ["Date", "Avg_Overall", "Response_Count"] + \
                  [f"Avg_{item}" for item in ITEM_COLUMNS]


# ── Helpers ───────────────────────────────────────────────────────────────────

def day_dates(days=DAYS):
    """Oldest-first list of YYYY-MM-DD strings ending today."""
    today = datetime.now()
    return [(today - timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(days - 1, -1, -1)]


def timestamp_for(date_str, hour_choices, late_cutoff=None):
    """A random HH:MM:SS on date_str within the given serving hours."""
    hour = random.choice(hour_choices)
    minute = random.randint(0, late_cutoff) if (late_cutoff is not None and
                                                hour == hour_choices[-1]) \
        else random.randint(0, 59)
    return f"{date_str} {hour:02d}:{minute:02d}:{random.randint(0, 59):02d}"


def drifting_mean(index, total, start=2.9, end=4.0):
    """
    Mean score for day `index`, drifting from `start` to `end` across the run
    with a little week-to-week wobble. A flat 3.1 every day (what seed_data.py
    produced) makes the trend chart look broken rather than boring.
    """
    progress = index / max(total - 1, 1)
    return start + (end - start) * progress + random.uniform(-0.18, 0.18)


def score_around(mean, low=1, high=5):
    """One integer score drawn around `mean`, clamped to [low, high]."""
    return max(low, min(high, round(random.gauss(mean, 0.85))))


def optional_score(mean, fill_prob, low=1, high=5):
    """A score, or '' when this respondent skipped the item."""
    return score_around(mean, low, high) if random.random() < fill_prob else ""


def ensure_capacity(worksheet, needed_rows):
    """Grows the grid if the incoming rows would not fit."""
    if worksheet.row_count < needed_rows + 1:
        worksheet.resize(rows=needed_rows + 50)


def wipe_data_rows(worksheet):
    """Clears every row below the header, leaving row 1 intact."""
    if worksheet.row_count > 1:
        worksheet.batch_clear([f"A2:Z{worksheet.row_count}"])


def get_or_create_tab(spreadsheet, title, headers, rows=500):
    """Returns the named worksheet, creating it with headers if it is missing."""
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        print(f"   creating missing tab '{title}'")
        worksheet = spreadsheet.add_worksheet(title=title, rows=rows,
                                              cols=max(len(headers), 10))
        worksheet.update([headers], "A1")
        return worksheet


# ── Row builders — pure functions, no API calls ──────────────────────────────

def build_responses(dates):
    """
    (response_rows, summary_rows) for the student dashboard.

    Summaries are derived from the same rows that get written, so the trend
    chart and the underlying responses can never disagree.
    """
    rows, summaries = [], []

    for index, date_str in enumerate(dates):
        mean = drifting_mean(index, len(dates))
        # More responses on recent days — a product gaining traction
        count = random.randint(8, 12) + int(index / len(dates) * 6)

        day_rows = []
        for _ in range(count):
            overall = score_around(mean)

            # Rice is served as curry or rasam; occasionally both
            rice_curry = optional_score(mean, 0.60, 2, 5)
            rice_rasam = ""
            if not rice_curry:
                rice_rasam = optional_score(mean, 0.60, 2, 5)
            elif random.random() < 0.20:
                rice_rasam = score_around(mean, 2, 5)

            day_rows.append([
                timestamp_for(date_str, [12, 13, 14], late_cutoff=30),
                overall,
                rice_curry,
                rice_rasam,
                optional_score(mean, 0.70, 2, 5),          # Chapati
                optional_score(mean, 0.70, 2, 5),          # Chapati_Gravy
                optional_score(mean - 0.4, 0.60, 1, 4),    # Poriyal — runs low
                optional_score(mean + 0.5, 0.50, 3, 5),    # Sweet — runs high
                optional_score(mean, 0.50, 2, 5),          # Salad
                optional_score(mean + 0.3, 0.60, 2, 5),    # Curd
                optional_score(mean + 0.2, 0.60, 2, 5),    # Papad
                optional_score(mean - 0.5, 0.60, 1, 4),    # Pickle — runs low
                random.choice(REVIEW_TEXTS) if random.random() < 0.16 else "",
                random.choice(SUGGESTION_TEXTS) if random.random() < 0.14 else "",
            ])

        day_rows.sort(key=lambda r: r[0])
        rows.extend(day_rows)
        summaries.append(summarise_day(date_str, day_rows))

    return rows, summaries


def summarise_day(date_str, day_rows):
    """One daily_summary row, matching update_daily_summary_for_today()'s format."""
    def average(column_index):
        values = [float(r[column_index]) for r in day_rows
                  if str(r[column_index]).strip()]
        return round(sum(values) / len(values), 1) if values else 0

    # Column 1 is Overall; items start at column 2 in the same order as ITEM_COLUMNS
    return [date_str, average(1), len(day_rows)] + \
           [average(2 + offset) for offset in range(len(ITEM_COLUMNS))]


def build_menu(past_days=14, future_days=7):
    """
    Menu rows spanning past_days back to future_days ahead, so /home has both
    today's menu and something to show when a student pages forward or back.

    Reuses sheets.WEEKLY_MENU_DEFAULTS rather than restating the templates —
    seed_data.py kept a second copy that could drift out of sync with the
    fallback the app actually serves when Sheets is unreachable.
    """
    rows = []
    start = datetime.now() - timedelta(days=past_days)
    for offset in range(past_days + future_days + 1):
        day = start + timedelta(days=offset)
        template = sheets.WEEKLY_MENU_DEFAULTS[day.weekday()]
        rows.append([
            day.strftime("%Y-%m-%d"),
            template["Breakfast"], template["Lunch"], template["Dinner"],
        ])
    return rows


def build_meal_ratings(dates):
    """
    good / bad / skip taps per meal. Only the most recent days are seeded:
    /home summarises a single date at a time, so 30 days x 3 meals x ~25 taps
    would be thousands of rows nobody ever reads.
    """
    hours = {"Breakfast": ([7, 8, 9], None),
             "Lunch": ([12, 13, 14], 30),
             "Dinner": ([19, 20, 21], 30)}
    rows = []

    for index, date_str in enumerate(dates):
        # Later days skew more positive, matching the student-dashboard trend
        good_weight = 0.52 + 0.18 * (index / max(len(dates) - 1, 1))
        for meal in sheets.MEALS:
            hour_choices, cutoff = hours[meal]
            for _ in range(random.randint(14, 26)):
                draw = random.random()
                if draw < good_weight:
                    rating = "good"
                elif draw < good_weight + 0.24:
                    rating = "bad"
                else:
                    rating = "skip"
                rows.append([
                    timestamp_for(date_str, hour_choices, late_cutoff=cutoff),
                    date_str, meal, rating,
                    random.choice(SUGGESTION_TEXTS) if random.random() < 0.08 else "",
                ])

    rows.sort(key=lambda r: r[0])
    return rows


def build_committee_members():
    """Roster rows. Every member shares COMMITTEE_PASSWORD for the demo."""
    password_hash = auth.hash_password(COMMITTEE_PASSWORD)
    today = datetime.now().strftime("%Y-%m-%d")
    term_start = (datetime.now() - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    rows = []
    for email, name in COMMITTEE_MEMBERS:
        rows.append([
            email, name, password_hash,
            "TRUE",    # Active
            "FALSE",   # Must_Change_Password — demo accounts log straight in
            term_start,
            "",        # Term_End
            f"{today} 09:00:00",
        ])
    return rows


def build_committee_reviews(dates):
    """
    Five-dimension reviews, at most one per member per day — the same
    constraint sheets.has_submitted_today() enforces in the live app.
    """
    rows = []
    for index, date_str in enumerate(dates):
        mean = drifting_mean(index, len(dates), start=3.0, end=4.1)
        # Not everyone reviews every day; participation climbs over the month.
        # The last few days are kept high on purpose — a demo opens on today,
        # and "40% participation" reads as a broken feature rather than a
        # realistic quiet day.
        progress = index / max(len(dates) - 1, 1)
        floor = 2 if progress < 0.5 else 3
        reviewers = random.sample(COMMITTEE_MEMBERS,
                                  k=random.randint(floor, 5) if index >= len(dates) - 3
                                  else random.randint(floor, 4))
        for position, (email, name) in enumerate(reviewers):
            scores = {
                "Taste": score_around(mean),
                "Quality": score_around(mean),
                "Variety": score_around(mean - 0.4),   # the standing complaint
                "Hygiene": score_around(mean + 0.4),
                "Menu": score_around(mean),
            }
            rows.append([
                timestamp_for(date_str, [13, 14, 15]),
                date_str, email, name,
                scores["Taste"], scores["Quality"], scores["Variety"],
                scores["Hygiene"], scores["Menu"],
                # The feed shows text-only reviews, so today always needs at
                # least one — otherwise the newest entry is silently stale.
                random.choice(COMMITTEE_REVIEW_TEXTS)
                if (random.random() < 0.45 or
                    (index == len(dates) - 1 and position == 0)) else "",
            ])

    rows.sort(key=lambda r: r[0])
    return rows


# ── Writing ───────────────────────────────────────────────────────────────────

def write_tab(worksheet, label, rows, wipe, dry_run):
    """Wipes (optionally) and writes every row in one append_rows() call."""
    print(f"   {label:20} {len(rows):5} rows", end="")
    if dry_run:
        print("  [dry-run, not written]")
        return
    if wipe:
        wipe_data_rows(worksheet)
    ensure_capacity(worksheet, len(rows) + (0 if wipe else worksheet.row_count))
    if rows:
        worksheet.append_rows(rows, value_input_option="RAW")
    print("  ✅")


def main():
    parser = argparse.ArgumentParser(description="Seed MessMate demo data.")
    parser.add_argument("--yes", action="store_true",
                        help="required to write anything")
    parser.add_argument("--dry-run", action="store_true",
                        help="print row counts without touching the sheet")
    parser.add_argument("--keep", action="store_true",
                        help="append instead of wiping existing data rows")
    parser.add_argument("--only", default="",
                        help="comma-separated tab names to seed")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        parser.error("refusing to write without --yes (or use --dry-run)")

    wipe = not args.keep
    selected = {name.strip() for name in args.only.split(",") if name.strip()}

    def wanted(tab):
        return not selected or tab in selected

    dates = day_dates()
    print(f"🌱 MessMate demo seed — {dates[0]} → {dates[-1]} ({DAYS} days)")
    print(f"   mode: {'WIPE + reseed' if wipe else 'append'}"
          f"{' (dry run)' if args.dry_run else ''}")
    print()

    spreadsheet = None
    if not args.dry_run:
        import os
        spreadsheet = sheets.get_client().open_by_key(os.environ["SPREADSHEET_ID"])

    def tab(title, headers=None, rows=500):
        if args.dry_run:
            return None
        if headers:
            return get_or_create_tab(spreadsheet, title, headers, rows)
        return spreadsheet.worksheet(title)

    # ── /dashboard ───────────────────────────────────────────────────────────
    print("📊 /dashboard")
    response_rows, summary_rows = build_responses(dates)
    if wanted("responses"):
        write_tab(tab("responses"), "responses", response_rows, wipe, args.dry_run)
    if wanted("daily_summary"):
        write_tab(tab("daily_summary"), "daily_summary", summary_rows, wipe,
                  args.dry_run)

    # ── /home ────────────────────────────────────────────────────────────────
    print("\n🍽️  /home")
    if wanted("menu"):
        write_tab(tab("menu", sheets.MENU_HEADERS, 100), "menu",
                  build_menu(), wipe, args.dry_run)
    if wanted("meal_ratings"):
        rating_rows = build_meal_ratings(dates[-10:])
        write_tab(tab("meal_ratings", sheets.MEAL_RATING_HEADERS, 2000),
                  "meal_ratings", rating_rows, wipe, args.dry_run)

    # ── /dashboard/committee ─────────────────────────────────────────────────
    print("\n👥 /dashboard/committee")
    if wanted("committee_members"):
        write_tab(tab(sheets.COMMITTEE_MEMBERS_TAB, sheets.MEMBER_HEADERS, 100),
                  "committee_members", build_committee_members(), wipe,
                  args.dry_run)
    if wanted("committee_reviews"):
        write_tab(tab(sheets.COMMITTEE_REVIEWS_TAB, sheets.REVIEW_HEADERS, 1000),
                  "committee_reviews", build_committee_reviews(dates), wipe,
                  args.dry_run)

    if not args.dry_run:
        sheets.invalidate_roster_cache()
        sheets.invalidate_menu_cache()

    today_count = sum(1 for r in response_rows if r[0].startswith(dates[-1]))
    print()
    print(f"🎉 Done. Today ({dates[-1]}) has {today_count} student responses.")
    print()
    print("   /dashboard            trend + today's per-item averages")
    print("   /home                 today's menu and meal reactions")
    print("   /dashboard/committee  five-dimension trend and review feed")
    print()
    print(f"   Committee demo login password: {COMMITTEE_PASSWORD}")
    print(f"   e.g. {COMMITTEE_MEMBERS[0][0]}")


if __name__ == "__main__":
    sys.exit(main())
