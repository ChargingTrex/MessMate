"""
MessMate Menu Categories — Unit Tests (test/test_menu_categories.py)
---------------------------------------------------------------------
Pure-function checks for categorised menus and the two CSV upload layouts.
No routes, no browser: the parsers are called directly, and the few tests
that touch storage use the in-memory sheets fake.

  UT-PARSE  sheets.menu_entries / _split_items      a cell -> (category, dish)
  UT-GROUP  sheets.menu_groups                      dishes -> display lines
  UT-NORM   sheets.normalise_menu_text / _menu_text the stored form of a cell
  UT-CAT    sheets.MENU_CATEGORIES                  the mess's row names
  UT-WEEK   sheets.WEEKLY_MENU_DEFAULTS             the Sai University week
  UT-STORE  save_menu_week / get_menu_*_for_date    round trip through storage
  UT-DATE   app._grid_date                          grid date headers
  UT-GRID   app._parse_menu_grid                    the template layout
  UT-MEAL   app._parse_menu_by_meal                 the older layout

Test IDs match docs/MENU_CATEGORIES_TEST_PLAN.md.

Runs with NO Google credentials.

Usage:
    python test/test_menu_categories.py          # verbose
    python -m unittest test.test_menu_categories

Exit code 0 = all tests passed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("FLASK_SECRET_KEY", "unit-menu-categories")
os.environ.setdefault("SPREADSHEET_ID", "fake-spreadsheet-id")

import sheets             # noqa: E402
import fake_sheets        # noqa: E402

BOOK = fake_sheets.install()

import app as app_module  # noqa: E402

D1, D2 = "2026-11-09", "2026-11-10"


def grid(*lines):
    """CSV text -> the row lists the importer hands to a parser."""
    import csv
    import io
    return list(csv.reader(io.StringIO("\n".join(lines))))


# ══════════════════════════════════════════════════════════════════════════════
# UT-PARSE — a meal cell into (category, dish) pairs
# ══════════════════════════════════════════════════════════════════════════════

class ParseEntries(unittest.TestCase):

    def test_ut_parse_01_category_and_dish(self):
        self.assertEqual(sheets.menu_entries("Main Item: Pongal"),
                         [("Main Item", "Pongal")])

    def test_ut_parse_02_bare_dish_has_no_category(self):
        self.assertEqual(sheets.menu_entries("Tea"), [("", "Tea")])

    def test_ut_parse_03_newlines_and_commas_both_separate(self):
        self.assertEqual(
            sheets.menu_entries("Rice: Steamed Rice\nCurd: Curd, Pickle"),
            [("Rice", "Steamed Rice"), ("Curd", "Curd"), ("", "Pickle")])

    def test_ut_parse_04_whitespace_trimmed(self):
        self.assertEqual(sheets.menu_entries("  Rasam :   Mysore Rasam  "),
                         [("Rasam", "Mysore Rasam")])

    def test_ut_parse_05_category_without_dish_dropped(self):
        self.assertEqual(sheets.menu_entries("Egg:\nMain Item: Idly\nPickle:   "),
                         [("Main Item", "Idly")])

    def test_ut_parse_06_empty_and_none(self):
        for raw in ("", None, " , \n ,", "\n\n"):
            with self.subTest(raw=raw):
                self.assertEqual(sheets.menu_entries(raw), [])

    def test_ut_parse_07_only_first_colon_splits(self):
        self.assertEqual(sheets.menu_entries("Note: Ratio 1:2"),
                         [("Note", "Ratio 1:2")])

    def test_ut_parse_08_overlong_prefix_is_not_a_category(self):
        long_prefix = "x" * 41
        self.assertEqual(sheets.menu_entries(f"{long_prefix}: Rice"),
                         [("", f"{long_prefix}: Rice")])

    def test_ut_parse_09_slashes_and_ampersands_survive(self):
        self.assertEqual(
            sheets.menu_entries("Podi / Oil & Thogayal: Pickle / Podi & Oil"),
            [("Podi / Oil & Thogayal", "Pickle / Podi & Oil")])

    def test_ut_parse_10_split_items_drops_categories(self):
        self.assertEqual(
            sheets._split_items("Main Item: Pongal\nChutney: Coconut Chutney\nTea"),
            ["Pongal", "Coconut Chutney", "Tea"])

    def test_ut_parse_11_split_items_keeps_old_behaviour(self):
        self.assertEqual(sheets._split_items("Rice\nDal\nCurd"), ["Rice", "Dal", "Curd"])
        self.assertEqual(sheets._split_items("Rice,, Dal , "), ["Rice", "Dal"])


# ══════════════════════════════════════════════════════════════════════════════
# UT-GROUP — display lines
# ══════════════════════════════════════════════════════════════════════════════

class Groups(unittest.TestCase):

    def test_ut_group_01_consecutive_same_category_merge(self):
        self.assertEqual(sheets.menu_groups("Spread: Butter\nSpread: Jam"),
                         [{"category": "Spread", "dishes": ["Butter", "Jam"]}])

    def test_ut_group_02_non_consecutive_same_category_stay_apart(self):
        groups = sheets.menu_groups("Rice: A\nCurd: B\nRice: C")
        self.assertEqual([g["category"] for g in groups], ["Rice", "Curd", "Rice"])

    def test_ut_group_03_uncategorised_dishes_are_one_group_each(self):
        self.assertEqual(sheets.menu_groups("Idli, Sambar"),
                         [{"category": "", "dishes": ["Idli"]},
                          {"category": "", "dishes": ["Sambar"]}])

    def test_ut_group_04_bare_dish_breaks_a_run(self):
        groups = sheets.menu_groups("Spread: Butter\nTea\nSpread: Jam")
        self.assertEqual(len(groups), 3)

    def test_ut_group_05_order_preserved(self):
        raw = sheets.WEEKLY_MENU_DEFAULTS[0]["Breakfast"]
        cats = [g["category"] for g in sheets.menu_groups(raw)]
        expected = []
        for c in sheets.MENU_CATEGORIES["Breakfast"]:
            if not expected or expected[-1] != c:
                expected.append(c)
        self.assertEqual(cats, expected)

    def test_ut_group_06_empty(self):
        self.assertEqual(sheets.menu_groups(""), [])


# ══════════════════════════════════════════════════════════════════════════════
# UT-NORM — the stored form
# ══════════════════════════════════════════════════════════════════════════════

class Normalise(unittest.TestCase):

    def test_ut_norm_01_one_entry_per_line(self):
        self.assertEqual(sheets.normalise_menu_text("Rice: A, Curd: B, Tea"),
                         "Rice: A\nCurd: B\nTea")

    def test_ut_norm_02_blank_template_rows_dropped(self):
        self.assertEqual(sheets.normalise_menu_text("Main Item: Idly\nEgg:\nBread:"),
                         "Main Item: Idly")

    def test_ut_norm_03_only_blank_rows_is_unpublished(self):
        self.assertEqual(sheets.normalise_menu_text("Egg:\nBread:\n"), "")

    def test_ut_norm_04_idempotent(self):
        once = sheets.normalise_menu_text(" Rice :A ,\n\nCurd: B ")
        self.assertEqual(sheets.normalise_menu_text(once), once)

    def test_ut_norm_05_menu_text_skips_empty_dishes(self):
        self.assertEqual(sheets._menu_text([("Rice", "A"), ("Egg", ""), ("", "Tea")]),
                         "Rice: A\nTea")


# ══════════════════════════════════════════════════════════════════════════════
# UT-CAT — the category list
# ══════════════════════════════════════════════════════════════════════════════

class Categories(unittest.TestCase):

    def test_ut_cat_01_one_list_per_meal_no_snacks(self):
        self.assertEqual(list(sheets.MENU_CATEGORIES), sheets.MEALS)
        self.assertNotIn("Snacks", sheets.MENU_CATEGORIES)

    def test_ut_cat_02_mess_sheet_names_in_order(self):
        self.assertEqual(sheets.MENU_CATEGORIES["Breakfast"][:3],
                         ["Main Item", "Side Dish", "Chutney"])
        self.assertEqual(sheets.MENU_CATEGORIES["Lunch"][-1], "Sweet / Fruits")
        self.assertEqual(sheets.MENU_CATEGORIES["Dinner"][-1], "Milk / Tea / Coffee")

    def test_ut_cat_03_sheet_typos_fixed(self):
        every = [c for cats in sheets.MENU_CATEGORIES.values() for c in cats]
        self.assertIn("Poriyal / Kootu", every)
        self.assertIn("Podi / Oil & Thogayal", every)
        for typo in ("kottu", "&n", "Spread 1", "Spread 2"):
            self.assertFalse(any(typo in c for c in every), typo)

    def test_ut_cat_04_only_spread_repeats(self):
        for meal, cats in sheets.MENU_CATEGORIES.items():
            repeats = {c for c in cats if cats.count(c) > 1}
            self.assertEqual(repeats, {"Spread"} if meal == "Breakfast" else set(), meal)

    def test_ut_cat_05_names_parse_as_categories(self):
        for cats in sheets.MENU_CATEGORIES.values():
            for c in cats:
                self.assertEqual(sheets.menu_entries(f"{c}: X"), [(c, "X")])


# ══════════════════════════════════════════════════════════════════════════════
# UT-WEEK — the Sai University week in the template
# ══════════════════════════════════════════════════════════════════════════════

class Week(unittest.TestCase):

    def test_ut_week_01_seven_days_three_meals(self):
        self.assertEqual(sorted(sheets.WEEKLY_MENU_DEFAULTS), list(range(7)))
        for day in sheets.WEEKLY_MENU_DEFAULTS.values():
            self.assertEqual(set(day), set(sheets.MEALS))

    def test_ut_week_02_categories_follow_the_list_in_order(self):
        for weekday, day in sheets.WEEKLY_MENU_DEFAULTS.items():
            for meal in sheets.MEALS:
                cats = [c for c, _ in sheets.menu_entries(day[meal])]
                allowed = sheets.MENU_CATEGORIES[meal]
                positions = [allowed.index(c) for c in cats]
                with self.subTest(weekday=weekday, meal=meal):
                    self.assertTrue(all(c for c in cats), "every dish has a category")
                    self.assertEqual(positions, sorted(positions))

    def test_ut_week_03_spot_checks_against_the_sheet(self):
        def dishes(weekday, meal):
            return dict(sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[weekday][meal]))
        self.assertEqual(dishes(0, "Breakfast")["Main Item"], "Mix Veg Sevai")
        self.assertEqual(dishes(1, "Breakfast")["Main Item"], "Idly")
        self.assertEqual(dishes(2, "Dinner")["Korma"], "Karaikudi Chicken Curry")
        self.assertEqual(dishes(6, "Lunch")["Sweet / Fruits"], "Ice Cream")

    def test_ut_week_04_blank_cells_left_out(self):
        friday = dict(sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[4]["Breakfast"]))
        saturday = dict(sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[5]["Breakfast"]))
        sunday = dict(sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[6]["Lunch"]))
        self.assertNotIn("Egg", friday)
        self.assertNotIn("Vada / Banana", saturday)
        self.assertNotIn("Bread", sunday)
        self.assertNotIn("Podi / Oil & Thogayal", sunday)

    def test_ut_week_05_no_snacks(self):
        for day in sheets.WEEKLY_MENU_DEFAULTS.values():
            text = " ".join(day.values())
            for snack in ("Aloo Samosa", "Veg Puff", "Tea cake", "Keerai Bonda"):
                self.assertNotIn(snack, text)

    def test_ut_week_06_template_for_date_uses_weekday(self):
        self.assertEqual(sheets.menu_template_for_date("2026-11-09"),
                         sheets.WEEKLY_MENU_DEFAULTS[0])   # a Monday
        self.assertEqual(sheets.menu_template_for_date("not-a-date"),
                         {m: "" for m in sheets.MEALS})


# ══════════════════════════════════════════════════════════════════════════════
# UT-STORE — through save_menu_week and back
# ══════════════════════════════════════════════════════════════════════════════

class Store(unittest.TestCase):

    def setUp(self):
        BOOK.reset()

    def test_ut_store_01_save_normalises(self):
        self.assertTrue(sheets.save_menu_week(
            [(D1, "Main Item: Idly, Egg:", "Tea", "")]))
        self.assertEqual(BOOK.menu().rows, [[D1, "Main Item: Idly", "Tea", ""]])

    def test_ut_store_02_groups_for_date(self):
        BOOK.seed_menu(D1, breakfast="Spread: Butter\nSpread: Jam")
        groups = sheets.get_menu_groups_for_date(D1)
        self.assertEqual(groups["Breakfast"],
                         [{"category": "Spread", "dishes": ["Butter", "Jam"]}])
        self.assertEqual(groups["Lunch"], [])

    def test_ut_store_03_dish_names_for_ratings(self):
        BOOK.seed_menu(D1, lunch="Rice: Steamed Rice\nCurd: Curd")
        self.assertEqual(sheets.get_menu_for_date(D1)["Lunch"], ["Steamed Rice", "Curd"])

    def test_ut_store_04_blank_rows_only_reads_as_unpublished(self):
        sheets.save_menu_week([(D1, "Egg:\nBread:", "", "")])
        week = sheets.get_menu_week(D1, days=1)
        self.assertFalse(week[0]["published"]["Breakfast"])


# ══════════════════════════════════════════════════════════════════════════════
# UT-DATE — grid date headers
# ══════════════════════════════════════════════════════════════════════════════

class GridDate(unittest.TestCase):

    def test_ut_date_01_accepted_formats(self):
        for text in ("2026-11-09", "09-11-2026", "09/11/2026", "09.11.2026",
                     " 9-11-2026 "):
            with self.subTest(text=text):
                self.assertEqual(app_module._grid_date(text), "2026-11-09")

    def test_ut_date_02_rejected(self):
        for text in ("", "Monday", "Meal", "2026-13-01", "31-02-2026", "11/9/26"):
            with self.subTest(text=text):
                self.assertIsNone(app_module._grid_date(text))


# ══════════════════════════════════════════════════════════════════════════════
# UT-GRID — the template layout (Meal, Category, <date>...)
# ══════════════════════════════════════════════════════════════════════════════

class GridParser(unittest.TestCase):

    def parse(self, *lines):
        return app_module._parse_menu_grid(grid(*lines))

    def test_ut_grid_01_basic(self):
        by_date, skipped, error = self.parse(
            f"Meal,Category,{D1}",
            "Breakfast,Main Item,Pongal",
            "Lunch,Rice,Steamed Rice",
            "Dinner,Rasam,Mysore Rasam")
        self.assertIsNone(error)
        self.assertEqual(skipped, [])
        self.assertEqual(by_date, {D1: (D1, "Main Item: Pongal",
                                        "Rice: Steamed Rice", "Rasam: Mysore Rasam")})

    def test_ut_grid_02_weekday_row_skipped(self):
        by_date, _, _ = self.parse(
            f"Meal,Category,{D1}", ",,Monday", "Breakfast,Main Item,Pongal")
        self.assertEqual(by_date[D1][1], "Main Item: Pongal")

    def test_ut_grid_03_meal_carries_down(self):
        by_date, _, _ = self.parse(
            f"Meal,Category,{D1}",
            "Breakfast,Main Item,Pongal",
            ",Spread,Butter",
            ",Spread,Jam")
        self.assertEqual(by_date[D1][1], "Main Item: Pongal\nSpread: Butter\nSpread: Jam")

    def test_ut_grid_04_snacks_skipped_with_note(self):
        by_date, skipped, _ = self.parse(
            f"Meal,Category,{D1}",
            "Snacks,Snack 1 ( Fried ),Aloo Samosa",
            ",Tea,Tea",
            "Dinner,Rice,Steamed Rice")
        self.assertNotIn("Samosa", " ".join(by_date[D1]))
        self.assertEqual(by_date[D1][3], "Rice: Steamed Rice")
        self.assertTrue(any("Skipped Snacks" in s for s in skipped), skipped)

    def test_ut_grid_05_meal_name_case_insensitive(self):
        by_date, skipped, _ = self.parse(f"Meal,Category,{D1}", "LUNCH,Rice,Rice")
        self.assertEqual(by_date[D1][2], "Rice: Rice")
        self.assertEqual(skipped, [])

    def test_ut_grid_06_header_case_and_column_order(self):
        by_date, _, error = self.parse(f"{D1},CATEGORY,meal", "Pongal,Main Item,Breakfast")
        self.assertIsNone(error)
        self.assertEqual(by_date[D1][1], "Main Item: Pongal")

    def test_ut_grid_07_comma_cell_is_several_dishes(self):
        by_date, _, _ = self.parse(f"Meal,Category,{D1}",
                                   'Dinner,Rice,"Mint Pulao, Steamed Rice"')
        self.assertEqual(by_date[D1][3], "Rice: Mint Pulao\nRice: Steamed Rice")

    def test_ut_grid_08_blank_category_gives_bare_dish(self):
        by_date, _, _ = self.parse(f"Meal,Category,{D1}", "Breakfast,,Tea")
        self.assertEqual(by_date[D1][1], "Tea")

    def test_ut_grid_09_empty_date_column_left_alone(self):
        by_date, skipped, _ = self.parse(f"Meal,Category,{D1},{D2}",
                                         "Breakfast,Main Item,Pongal,")
        self.assertEqual(list(by_date), [D1])
        self.assertTrue(any("Left 1 empty day unchanged" in s for s in skipped), skipped)

    def test_ut_grid_10_blank_meal_in_a_filled_day_is_blank(self):
        by_date, _, _ = self.parse(f"Meal,Category,{D1}", "Breakfast,Main Item,Pongal")
        self.assertEqual(by_date[D1][2:], ("", ""))

    def test_ut_grid_11_non_date_columns_ignored(self):
        by_date, _, error = self.parse(f"Meal,Category,{D1},Notes",
                                       "Breakfast,Main Item,Pongal,ask the cook")
        self.assertIsNone(error)
        self.assertNotIn("cook", by_date[D1][1])

    def test_ut_grid_12_no_date_columns_is_an_error(self):
        by_date, _, error = self.parse("Meal,Category,Monday", "Breakfast,Main Item,Pongal")
        self.assertEqual(by_date, {})
        self.assertIn("No date columns", error)

    def test_ut_grid_13_ragged_rows(self):
        by_date, _, _ = self.parse(f"Meal,Category,{D1},{D2}", "Breakfast,Main Item,Pongal")
        self.assertEqual(list(by_date), [D1])

    def test_ut_grid_14_all_empty(self):
        by_date, skipped, error = self.parse(f"Meal,Category,{D1}", "Breakfast,Main Item,")
        self.assertEqual((by_date, skipped, error), ({}, [], None))

    def test_ut_grid_15_round_trips_the_sai_week(self):
        # The template's rows, filled with the Sai week the way the mess fills
        # its sheet, parse back to exactly the stored week.
        dates = ["2026-11-%02d" % d for d in range(9, 16)]
        rows = [["Meal", "Category"] + dates]
        for meal in sheets.MEALS:
            # Each day's dishes in category order; a "Spread" row takes the
            # next Spread dish, so the two Spread rows get Butter then Jam.
            queues = [list(sheets.menu_entries(sheets.WEEKLY_MENU_DEFAULTS[wd][meal]))
                      for wd in range(7)]
            for category in sheets.MENU_CATEGORIES[meal]:
                row = [meal, category]
                for queue in queues:
                    if queue and queue[0][0] == category:
                        row.append(queue.pop(0)[1])
                    else:
                        row.append("")
                rows.append(row)
            self.assertTrue(all(not q for q in queues), f"{meal}: dishes left over")

        by_date, skipped, error = app_module._parse_menu_grid(rows)
        self.assertIsNone(error)
        self.assertEqual(skipped, [])
        for weekday, date in enumerate(dates):
            for i, meal in enumerate(sheets.MEALS, start=1):
                with self.subTest(date=date, meal=meal):
                    self.assertEqual(by_date[date][i],
                                     sheets.WEEKLY_MENU_DEFAULTS[weekday][meal])


# ══════════════════════════════════════════════════════════════════════════════
# UT-MEAL — the older layout (Date, Breakfast, Lunch, Dinner)
# ══════════════════════════════════════════════════════════════════════════════

class ByMealParser(unittest.TestCase):

    def parse(self, *lines):
        return app_module._parse_menu_by_meal(grid(*lines))

    def test_ut_meal_01_basic(self):
        by_date, skipped, error = self.parse("Date,Breakfast,Lunch,Dinner",
                                             f'{D1},"Idli, Sambar",Rice,')
        self.assertIsNone(error)
        self.assertEqual(skipped, [])
        self.assertEqual(by_date[D1], (D1, "Idli, Sambar", "Rice", ""))

    def test_ut_meal_02_header_any_order_and_case(self):
        by_date, _, _ = self.parse("dinner,DATE,Lunch,breakfast", f"Chapati,{D1},Rice,Idli")
        self.assertEqual(by_date[D1], (D1, "Idli", "Rice", "Chapati"))

    def test_ut_meal_03_categories_allowed_in_cells(self):
        by_date, _, _ = self.parse("Date,Breakfast,Lunch,Dinner",
                                   f'{D1},"Main Item: Idly, Chutney: Peanut Chutney",,')
        self.assertEqual(sheets.menu_entries(by_date[D1][1]),
                         [("Main Item", "Idly"), ("Chutney", "Peanut Chutney")])

    def test_ut_meal_04_bad_dates_reported_by_line(self):
        by_date, skipped, _ = self.parse("Date,Breakfast,Lunch,Dinner",
                                         f"{D1},Idli,,", "09-11-2026,Idli,,", "soon,x,,")
        self.assertEqual(list(by_date), [D1])
        self.assertEqual(skipped, ["Skipped lines 3, 4 (bad date)."])

    def test_ut_meal_05_last_row_for_a_date_wins(self):
        by_date, _, _ = self.parse("Date,Breakfast,Lunch,Dinner",
                                   f"{D1},Idli,,", f"{D1},Dosa,,")
        self.assertEqual(by_date[D1][1], "Dosa")

    def test_ut_meal_06_blank_lines_skipped(self):
        by_date, skipped, _ = self.parse("Date,Breakfast,Lunch,Dinner", ",,,", f"{D1},Idli,,")
        self.assertEqual(list(by_date), [D1])
        self.assertEqual(skipped, [])

    def test_ut_meal_07_missing_columns_is_an_error(self):
        for header in ("Date,Breakfast,Lunch", "Day,Breakfast,Lunch,Dinner", ""):
            with self.subTest(header=header):
                _, _, error = self.parse(header, f"{D1},Idli,Rice")
                self.assertIn("CSV needs a header row", error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
