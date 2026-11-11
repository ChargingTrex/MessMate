"""
MessMate Sheets Read Cache (test/test_cache.py)
------------------------------------------------
Checks the read cache in sheets.py against the in-memory fake: when it
refreshes, that repeat reads cost no API calls, and that the app's own writes
show up without a re-read.

Usage:
    python test/test_cache.py

Exit code 0 = all checks passed.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_sheets  # noqa: E402
import sheets  # noqa: E402

BOOK = fake_sheets.install()
results = []


def check(label, condition, detail=""):
    results.append(condition)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  — {detail}"))


def at(hh, mm, day=datetime(2026, 11, 10)):
    return day.replace(hour=hh, minute=mm)


print("Refresh points")
points = sheets.refresh_points(datetime(2026, 11, 10))
times = {(p.hour, p.minute) for p in points}
check("every 30 minutes on the clock", {(9, 0), (9, 30), (23, 30)} <= times)
check("10 minutes before breakfast, lunch and dinner",
      {(7, 20), (11, 50), (19, 20)} <= times, sorted(times))
check("after 11:31 the next refresh is 11:50 (pre-lunch)",
      sheets.next_refresh_after(at(11, 31)) == at(11, 50))
check("after 11:50 the next refresh is 12:00",
      sheets.next_refresh_after(at(11, 50)) == at(12, 0))
check("after 23:45 the next refresh is midnight",
      sheets.next_refresh_after(at(23, 45)) == datetime(2026, 11, 11))

print("Reads are served from memory")
BOOK.reset()
BOOK.seed_meal_rating("2026-11-10", "Lunch", "good")
ws = BOOK.meal_ratings()
before = ws.read_count
for _ in range(5):
    sheets.get_meal_ratings("2026-11-10")
check("five reads cost one API call", ws.read_count - before == 1,
      f"reads={ws.read_count - before}")

print("Writes patch the cache")
before = ws.read_count
sheets.append_meal_rating("Dinner", "bad")
today = datetime.now().strftime("%Y-%m-%d")
dinner = [r for r in sheets.get_meal_ratings(today) if r["Meal"] == "Dinner"]
check("a quick tap is visible at once", len(dinner) == 1)
check("...without re-reading the tab", ws.read_count == before,
      f"reads={ws.read_count - before}")

stamp = dinner[0]["Timestamp"]
sheets.delete_meal_rating(stamp, today, "Dinner")
check("undo removes it from the cache too",
      not [r for r in sheets.get_meal_ratings(today) if r["Meal"] == "Dinner"])

BOOK.reset()
resp = BOOK.responses()
sheets.get_today_responses()          # load the tab
before = resp.read_count
sheets.append_response({"Overall": 4, "Rice_Curry": 5})
sheets.update_daily_summary_for_today()
todays = sheets.get_today_responses()
check("a student submission is visible at once",
      len(todays) == 1 and todays[0]["Overall"] == 4, todays)
check("...and the summary is computed without re-reading responses",
      resp.read_count == before, f"reads={resp.read_count - before}")
summary = [r for r in sheets.get_daily_summary() if r["Date"] == today]
check("today's summary row is in the cache",
      len(summary) == 1 and summary[0]["Response_Count"] == 1, summary)
sheets.append_response({"Overall": 2})
sheets.update_daily_summary_for_today()
summary = [r for r in sheets.get_daily_summary() if r["Date"] == today]
check("a second submission updates that row, not a new one",
      len(summary) == 1 and summary[0]["Response_Count"] == 2
      and summary[0]["Avg_Overall"] == 3.0, summary)

print("Staleness")
BOOK.reset()
reviews = BOOK.reviews()
sheets.get_committee_reviews()
before = reviews.read_count
with sheets._cache_lock:
    sheets._tab_cache[sheets.COMMITTEE_REVIEWS_TAB]["loaded_at"] -= timedelta(minutes=31)
sheets.get_committee_reviews()
check("a tab loaded before a refresh point is re-read after it",
      reviews.read_count - before == 1, f"reads={reviews.read_count - before}")

print("Outages")
BOOK.reset()
BOOK.seed_meal_rating("2026-11-10", "Lunch", "good")
sheets.get_meal_ratings()
with sheets._cache_lock:
    sheets._tab_cache[sheets.MEAL_RATINGS_TAB]["loaded_at"] -= timedelta(minutes=31)
BOOK.mode = "raise"
stale = sheets.get_meal_ratings()
check("a failed refresh serves the older copy", len(stale) == 1, stale)
BOOK.mode = "ok"
BOOK.reset()
BOOK.mode = "raise"
check("with nothing cached, an outage still reads as empty",
      sheets.get_meal_ratings() == [])
BOOK.mode = "ok"

passed = sum(results)
print(f"\n  {passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
