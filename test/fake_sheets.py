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
        """Used only by the student daily-summary path; a no-op is enough."""
        pass

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
        }
        # "ok" | "unavailable" (get_sheet returns None) | "raise" (simulated outage)
        self.mode = "ok"
        sheets.invalidate_roster_cache()

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

    def seed_student_response(self, date, overall, review="", suggestion=""):
        row = [f"{date} 12:30:00", overall] + [""] * 10 + [review, suggestion]
        self.responses().rows.append(row)


def install():
    """
    Replaces sheets.get_sheet with the fake and returns the FakeBook.
    Every other function in sheets.py runs unmodified.
    """
    book = FakeBook()
    sheets.get_sheet = book.get_sheet
    return book
