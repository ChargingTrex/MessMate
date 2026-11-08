# MessMate MySQL schema

`schema.mysql.sql` defines the tables that will replace the Google Sheet when MessMate is hosted on MySQL 8.0.16 or later. It has been loaded and its constraints checked on MySQL 8.4. The app still reads and writes Google Sheets: `sheets.py` has to be ported before this schema is used.

```sh
mysql -u <user> -p <database> < db/schema.mysql.sql
```

## Sheet tab → table

| Sheet tab | MySQL | Notes |
|---|---|---|
| `responses` | `responses` | Blank item ratings become `NULL`. `Timestamp` becomes `submitted_at` plus `submitted_on`, and a CHECK keeps the two in agreement. |
| `daily_summary` | `daily_summary` (view) | Computed from `responses`, so there is nothing to upsert. Column names are lowercase (`avg_overall`, not `Avg_Overall`). |
| `committee_members` | `committee_members` | `Active` and `Must_Change_Password` become booleans. Emails are lower case only, enforced by a CHECK. |
| `menu` | `menus` + `menu_dishes` | One row per published (date, meal), and one row per dish within it. Splitting the comma-separated cell (`sheets._split_items`) happens once, on write. |
| `committee_reviews` | `committee_reviews` | `Member_Email`/`Member_Name` become `member_id`. One review per member per meal per day is a UNIQUE key. A blank `Meal` imports as `NULL`. |
| `committee_dish_ratings` | `committee_dish_ratings` | Linked to its review by `review_id`. `dish_name` is a snapshot of what the member saw. `menu_dish_id` becomes NULL if staff later remove that dish. |
| `meal_ratings` | `meal_ratings` | Undo can delete by `id`. |

`committee_dish_daily` is an extra view that gives average committee rating per dish, per meal, per day.

## Behaviour that changes when porting `sheets.py`

- **Write a committee review and its dish ratings in one transaction.** Sheets cannot do that, which is why `get_committee_dish_ratings()` filters out orphan dish rows. With a transaction, that filter can go.
- **A duplicate meal review raises an IntegrityError (1062).** Treat it the same as `has_submitted_today(meal=...)` returning True and show the "already reviewed" page. Keep the pre-check as well, so members see that page before they fill in the form.
- **Time zone.** The app writes `datetime.now()`, which is local time. Run the app and MySQL in the same time zone (for example `TZ=Asia/Kolkata`). Otherwise reviews near midnight will land on the wrong day.
