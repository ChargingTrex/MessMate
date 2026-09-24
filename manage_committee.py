"""
MessMate Committee Admin CLI (manage_committee.py)
---------------------------------------------------
Break-glass tooling for the Food Committee roster.

Day-to-day member management belongs in the admin UI at /admin/members. This
script exists for the two cases that UI cannot serve:

  1. Generating ADMIN_PASSWORD_HASH in the first place (chicken and egg — you
     cannot sign in to the admin UI before this value exists).
  2. Recovering when the admin password is lost.

Usage:
  python manage_committee.py hash-admin-password
  python manage_committee.py add --email a@sai.edu --name "A B"
  python manage_committee.py list
  python manage_committee.py sheet-template
"""

import argparse
import csv
import getpass
import os
import sys

from dotenv import load_dotenv

# Load .env before importing sheets — it needs SPREADSHEET_ID at call time
load_dotenv()

import auth
import sheets


def cmd_hash_admin_password(args):
    """Generates the ADMIN_PASSWORD_HASH value for .env / Render."""
    password = getpass.getpass("New admin password: ")
    if len(password) < auth.MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {auth.MIN_PASSWORD_LENGTH} characters.")
        return 1

    if password != getpass.getpass("Confirm admin password: "):
        print("Passwords do not match.")
        return 1

    print("\nAdd this to your .env file (or Render environment variables):\n")
    print(f"ADMIN_PASSWORD_HASH={auth.hash_password(password)}\n")
    print("The password itself is not stored anywhere — keep it in a password manager.")
    return 0


def cmd_add(args):
    """Adds one member and prints the generated one-time password."""
    email, error = auth.normalize_email(args.email)
    if error:
        print(f"Error: {error}")
        return 1

    if sheets.get_committee_member(email):
        print(f"Error: {email} is already on the roster.")
        return 1

    password = auth.generate_password()
    if not sheets.add_committee_member(email, args.name, auth.hash_password(password)):
        print("Error: could not write to the sheet. Check SPREADSHEET_ID and credentials.")
        return 1

    print(f"\nAdded {args.name} <{email}>")
    print(f"One-time password: {password}")
    print("They must change it at first sign-in. It cannot be shown again.\n")
    return 0


def cmd_list(args):
    """
    Prints the roster and validates the tab headers.
    A header mismatch is the most likely silent failure mode, since
    get_all_records() maps row 1 to dict keys.
    """
    roster = sheets.get_committee_roster(force_refresh=True)

    if not roster:
        print("Roster is empty, or the committee_members tab is unreachable.")
        return 1

    found = list(roster[0].keys())
    missing = [h for h in sheets.MEMBER_HEADERS if h not in found]
    if missing:
        print(f"WARNING: committee_members is missing headers: {', '.join(missing)}")
        print(f"Expected exactly: {', '.join(sheets.MEMBER_HEADERS)}")
        print(f"Found:            {', '.join(found)}\n")

    print(f"{'Name':<24} {'Email':<34} {'Status':<10} Term")
    print("-" * 88)
    for record in roster:
        status = "active" if sheets._is_true(record.get("Active")) else "inactive"
        term = str(record.get("Term_Start", ""))
        if record.get("Term_End"):
            term += f" -> {record.get('Term_End')}"
        print(f"{str(record.get('Name','')):<24} {str(record.get('Email','')):<34} "
              f"{status:<10} {term}")

    active = sum(1 for r in roster if sheets._is_true(r.get("Active")))
    print(f"\n{active} active of {len(roster)} total.")
    return 0




# ── Sheet templates ───────────────────────────────────────────────────────────

TEMPLATE_CSV = "template.csv"
TEMPLATE_DIR = "sheet_templates"

TEMPLATE_COLUMNS = ["Tab", "Column", "Cell", "Format", "Notes"]


def _column_letter(index):
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _guess_format(column):
    """
    The format a column needs in Google Sheets.

    Plain Text matters for anything date-shaped: Sheets reformats those cells to
    the viewer's locale, which is what forced the six-format fallback parser in
    get_today_responses(). Storing them as text keeps a literal YYYY-MM-DD.
    """
    if column in ("Date", "Term_Start", "Term_End"):
        return "Plain text (YYYY-MM-DD)"
    if column in ("Timestamp", "Created_At"):
        return "Plain text (YYYY-MM-DD HH:MM:SS)"
    if column in ("Active", "Must_Change_Password"):
        return "Plain text (TRUE / FALSE)"
    if column.startswith("Avg_") or column == "Response_Count":
        return "Number"
    return "Plain text"


def build_template_rows():
    """Rows for template.csv, derived from sheets.SHEET_TEMPLATES."""
    rows = []
    for spec in sheets.SHEET_TEMPLATES:
        for index, column in enumerate(spec["headers"]):
            note = spec["notes"].get(column, "")
            if index == 0 and spec.get("written_by"):
                note = (f"Written by: {spec['written_by']}. " + note).strip()
            rows.append({
                "Tab": spec["tab"],
                "Column": column,
                "Cell": f"{_column_letter(index)}1",
                "Format": _guess_format(column),
                "Notes": note,
            })
    return rows


def write_templates(directory="."):
    """
    Writes template.csv and sheet_templates/<tab>.csv.
    Returns the list of paths written.
    """
    written = []

    master = os.path.join(directory, TEMPLATE_CSV)
    with open(master, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerows(build_template_rows())
    written.append(master)

    per_tab = os.path.join(directory, TEMPLATE_DIR)
    os.makedirs(per_tab, exist_ok=True)
    for spec in sheets.SHEET_TEMPLATES:
        path = os.path.join(per_tab, f"{spec['tab']}.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            # Header row only. Importing this into Google Sheets creates the tab
            # with the right columns and no rows to delete afterwards.
            csv.writer(handle).writerow(spec["headers"])
        written.append(path)

    return written


def cmd_sheet_template(args):
    """Regenerates the CSV templates from the schema in sheets.py."""
    written = write_templates()
    print("Wrote:")
    for path in written:
        print(f"  {path}")
    print(f"\n{len(sheets.SHEET_TEMPLATES)} tabs, "
          f"{sum(len(s['headers']) for s in sheets.SHEET_TEMPLATES)} columns.")
    print("\nTo build the spreadsheet: File > Import > upload one "
          f"{TEMPLATE_DIR}/*.csv per tab, choosing 'Insert new sheet(s)', then")
    print("rename each tab to match the file name and set the date columns to "
          "Plain Text.")
    return 0

def main():
    parser = argparse.ArgumentParser(description="MessMate committee roster tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("hash-admin-password",
                          help="Generate ADMIN_PASSWORD_HASH for .env")

    add_parser = subparsers.add_parser("add", help="Add one committee member")
    add_parser.add_argument("--email", required=True)
    add_parser.add_argument("--name", required=True)

    subparsers.add_parser("list", help="Print the roster and validate headers")

    subparsers.add_parser("sheet-template",
                          help="Regenerate template.csv and sheet_templates/*.csv")

    args = parser.parse_args()

    handlers = {
        "hash-admin-password": cmd_hash_admin_password,
        "add": cmd_add,
        "list": cmd_list,
        "sheet-template": cmd_sheet_template,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
