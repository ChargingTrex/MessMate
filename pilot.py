"""
MessMate Pilot Accounts (pilot.py)
-----------------------------------
One demo account per role, shown on /signin so a visitor can see every role
the pilot offers. Picking a card fills in the EMAIL only: every account has
its own password, handed out privately, so the page never carries a secret
and a student who opens the sign-in page cannot step into another role.

Only rendered when PILOT_MODE=true.

Env:
    PILOT_MODE              true to show the cards (default: off)

The member emails match seed_demo.py.
"""

import os

ADMIN_EMAIL = "admin@messmate.demo"
VIEWER_EMAIL = "dean@messmate.demo"

# Emails that are not committee members and sign in through another check
SPECIAL_EMAILS = {ADMIN_EMAIL: "admin", VIEWER_EMAIL: "viewer"}


def enabled():
    return os.environ.get("PILOT_MODE", "").strip().lower() in ("true", "1", "yes")


def accounts():
    """The pilot cards, in display order. Empty unless pilot mode is on."""
    if not enabled():
        return []
    return [
        {"role": "Student", "name": "Any student", "email": "",
         "initials": "St", "tone": "student", "href": "/home",
         "caption": "No account — the menu and quick taps are open to everyone, anonymously"},
        {"role": "Committee member", "name": "Arjun Ramesh", "email": "arjun.r@messmate.demo",
         "initials": "AR", "tone": "member",
         "caption": "Reviews each meal: every dish on the menu plus five areas, and sees the committee dashboard"},
        {"role": "Committee member", "name": "Priya Natarajan", "email": "priya.n@messmate.demo",
         "initials": "PN", "tone": "member",
         "caption": "A second member — sign in as both to watch the meal toggle and participation change"},
        {"role": "Committee member", "name": "Karthik Subramanian", "email": "karthik.s@messmate.demo",
         "initials": "KS", "tone": "member",
         "caption": "Committee member"},
        {"role": "Committee member", "name": "Divya Menon", "email": "divya.m@messmate.demo",
         "initials": "DM", "tone": "member",
         "caption": "Committee member"},
        {"role": "Committee member", "name": "Faizal Ahmed", "email": "faizal.a@messmate.demo",
         "initials": "FA", "tone": "member",
         "caption": "Committee member"},
        {"role": "Dean", "name": "Read-only", "email": VIEWER_EMAIL,
         "initials": "Dn", "tone": "viewer", "badge": "read-only",
         "caption": "Both dashboards, nothing that changes state — the same view the ?token= link gives"},
        {"role": "Admin", "name": "Mess manager", "email": ADMIN_EMAIL,
         "initials": "Ad", "tone": "admin", "badge": "full access",
         "caption": "Overview, the weekly menu editor, the roster and both dashboards"},
    ]
