"""
MessMate In-Memory Sheets Fake (test/fake_sheets.py)
------------------------------------------------------
An in-memory stand-in for the gspread worksheet API, so the app can be tested
without Google credentials.

Only the surface sheets.py actually uses is implemented, which means the real
sheets.py logic runs against it: the roster TTL cache, row construction, the
col_values row lookup, update_cell, and get_all_records all execute for real.
The only thing replaced is the network.

Shared by:
    test/test_committee.py      — per-item checklist verification
    test/test_e2e_committee.py  — full user journeys
    test/fake_server.py         — a live server for the Robot UI suites
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sheets  # noqa: E402

STUDENT_HEADERS = [
    "Timestamp", "Overall", "Rice_Curry", "Rice_Rasam", "Chapati",
    "Chapati_Gravy", "Poriyal", "Sweet", "Salad", "Curd", "Papad",
    "Pickle", "Review", "Suggestion"
]

SUMMARY_HEADERS = [
    "Date", "Avg_Overall", "Response_Count", "Avg_Rice_Curry",
    "Avg_Rice_Rasam", "Avg_Chapati", "Avg_Chapati_Gravy", "Avg_Poriyal",
    "Avg_Sweet", "Avg_Salad", "Avg_Curd", "Avg_Papad", "Avg_Pickle"
]


class FakeWorksheet:
    """Implements only the gspread methods sheets.py calls."""

    def __init__(self, headers):
        self.headers = list(headers)
        self.rows = []              # data rows, header excluded
        self.read_count = 0         # lets tests prove the roster cache works
        self.append_row_calls = 0
        self.append_rows_calls = 0

    def get_all_records(self):
        self.read_count += 1
        return [dict(zip(self.headers, row)) for row in self.rows]

    def append_row(self, row, value_input_option=None):
        self.append_row_calls += 1
        self.rows.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.append_rows_calls += 1
        for row in rows:
            self.rows.append(list(row))

    def col_values(self, index):
        # gspread is 1-indexed and includes the header cell
        values = [self.headers[index - 1]]
        for row in self.rows:
            values.append(row[index - 1] if index - 1 < len(row) else "")
        return values

    def update_cell(self, row_index, col_index, value):
        # Row 1 is the header, so data starts at row 2
        self.rows[row_index - 2][col_index - 1] = value

    def update(self, cell_range, values):
        """
        Writes a block of values into an A1-style range, e.g. "A5:M5".

        This was a no-op stub, which silently disabled the one path that uses
        it: update_daily_summary_for_today() calls update() when today's row
        already exists, so the upsert branch appeared to work while writing
        nothing. A fake that quietly accepts writes is worse than no fake —
        it makes a suite green without testing anything.
        """
        match = re.match(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$", cell_range.strip())
        if not match:
            raise ValueError(f"unsupported range for the fake: {cell_range!r}")

        start_col, start_row, _, _ = match.groups()
        first_col = self._col_index(start_col)
        first_row = int(start_row)

        for offset, row_values in enumerate(values):
            target = first_row + offset - 2   # row 1 is the header
            if target < 0 or target >= len(self.rows):
                raise IndexError(f"range {cell_range} is outside the fake sheet")
            for i, value in enumerate(row_values):
                self.rows[target][first_col + i] = value

    @staticmethod
    def _col_index(letters):
        """'A' -> 0, 'M' -> 12, 'AA' -> 26."""
        index = 0
        for char in letters:
            index = index * 26 + (ord(char) - ord("A") + 1)
        return index - 1

    def all_cell_text(self):
        """Every stored value as one string — proves no plaintext leaks."""
        return " ".join(str(cell) for row in self.rows for cell in row)


class FakeBook:
    """Registry of tab name -> FakeWorksheet, standing in for the spreadsheet."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.tabs = {
            sheets.COMMITTEE_MEMBERS_TAB: FakeWorksheet(sheets.MEMBER_HEADERS),
            sheets.COMMITTEE_REVIEWS_TAB: FakeWorksheet(sheets.REVIEW_HEADERS),
            "responses": FakeWorksheet(STUDENT_HEADERS),
            "daily_summary": FakeWorksheet(SUMMARY_HEADERS),
            sheets.MENU_TAB: FakeWorksheet(sheets.MENU_HEADERS),
            sheets.MEAL_RATINGS_TAB: FakeWorksheet(sheets.MEAL_RATING_HEADERS),
        }
        # "ok" | "unavailable" (get_sheet returns None) | "raise" (simulated outage)
        self.mode = "ok"
        sheets.invalidate_roster_cache()
        sheets.invalidate_menu_cache()

    def get_sheet(self, tab_name):
        if self.mode == "raise":
            raise RuntimeError("simulated Google Sheets outage")
        if self.mode == "unavailable":
            return None
        return self.tabs.get(tab_name)

    def members(self):
        return self.tabs[sheets.COMMITTEE_MEMBERS_TAB]

    def reviews(self):
        return self.tabs[sheets.COMMITTEE_REVIEWS_TAB]

    def responses(self):
        return self.tabs["responses"]

    # ── Seeding helpers ───────────────────────────────────────────────────

    def seed_member(self, email, name, password, active=True,
                    must_change=False, term_start="2026-01-01", term_end=""):
        """Writes a member directly, bypassing the admin UI."""
        import auth
        self.members().rows.append([
            email.lower(), name, auth.hash_password(password),
            "TRUE" if active else "FALSE",
            "TRUE" if must_change else "FALSE",
            term_start, term_end, "2026-01-01 09:00:00"
        ])
        sheets.invalidate_roster_cache()

    def seed_review(self, email, name, date, scores, review=""):
        """scores is [taste, quality, variety, hygiene, menu]."""
        self.reviews().rows.append(
            [f"{date} 13:00:00", date, email.lower(), name] + list(scores) + [review])

    def seed_student_response(self, date, overall, review="", suggestion="",
                              items=None):
        """
        Seeds one student response.

        `items` is the ten per-item scores in column order (Rice_Curry,
        Rice_Rasam, Chapati, Chapati_Gravy, Poriyal, Sweet, Salad, Curd,
        Papad, Pickle); blanks are allowed and mean "not rated".

        Defaulting these to blank makes the student dashboard take its
        empty-state path, where dashboard.js REPLACES the #itemChart canvas
        with a message — so a fixture with no item scores removes an element
        the dashboard normally has. Pass real scores unless the empty state is
        what you are testing.
        """
        scores = list(items) if items else [""] * 10
        if len(scores) != 10:
            raise ValueError(f"items must have 10 values, got {len(scores)}")
        row = [f"{date} 12:30:00", overall] + scores + [review, suggestion]
        self.responses().rows.append(row)


    def menu(self):
        return self.tabs[sheets.MENU_TAB]

    def meal_ratings(self):
        return self.tabs[sheets.MEAL_RATINGS_TAB]

    def seed_menu(self, date, breakfast="", lunch="", dinner=""):
        """Publishes one day's menu. Items are comma-separated, as staff type them."""
        self.menu().rows.append([date, breakfast, lunch, dinner])
        sheets.invalidate_menu_cache()

    def seed_meal_rating(self, date, meal, rating, suggestion=""):
        self.meal_ratings().rows.append(
            [f"{date} 13:00:00", date, meal, rating, suggestion])


def install():
    """
    Replaces sheets.get_sheet with the fake and returns the FakeBook.
    Every other function in sheets.py runs unmodified.
    """
    book = FakeBook()
    sheets.get_sheet = book.get_sheet
    return book
