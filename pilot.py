"""
MessMate Pilot Accounts (pilot.py)
-----------------------------------
One demo account per role, shown on /signin so a visitor can try every view
without being told a password out of band. Picking a card fills the form;
the sign-in that follows is the real one, so the demo exercises the same
checks a genuine login makes.

Only rendered when PILOT_MODE=true. The cards carry passwords, so pilot
mode must be OFF in production — it is a demo switch, not a feature flag.

Env:
    PILOT_MODE              true to show the cards (default: off)
    PILOT_ADMIN_PASSWORD    the admin password the Admin card fills in; must
                            match ADMIN_PASSWORD_HASH or the sign-in fails,
                            exactly as it should
    PILOT_MEMBER_PASSWORD   the committee members' shared demo password
                            (default: the one seed_demo.py writes)
    VIEWER_PASSWORD         the read-only Dean account's password
                            (default: DASHBOARD_TOKEN)

The member emails match seed_demo.py — run it first, or the cards fill a
form that is correctly refused.
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
    member_pw = os.environ.get("PILOT_MEMBER_PASSWORD", "MessMate@2026")
    admin_pw = os.environ.get("PILOT_ADMIN_PASSWORD", "")
    viewer_pw = os.environ.get("VIEWER_PASSWORD") or os.environ.get("DASHBOARD_TOKEN", "")
    return [
        {"role": "Student", "name": "Any student", "email": "", "password": "",
         "initials": "St", "tone": "student", "href": "/home",
         "caption": "No account — the menu and quick taps are open to everyone, anonymously"},
        {"role": "Committee member", "name": "Arjun Ramesh", "email": "arjun.r@messmate.demo",
         "password": member_pw, "initials": "AR", "tone": "member",
         "caption": "Reviews each meal: every dish on the menu plus five areas, and sees the committee dashboard"},
        {"role": "Committee member", "name": "Priya Natarajan", "email": "priya.n@messmate.demo",
         "password": member_pw, "initials": "PN", "tone": "member",
         "caption": "A second member — sign in as both to watch the meal toggle and participation change"},
        {"role": "Committee member", "name": "Karthik Subramanian", "email": "karthik.s@messmate.demo",
         "password": member_pw, "initials": "KS", "tone": "member",
         "caption": "Committee member"},
        {"role": "Committee member", "name": "Divya Menon", "email": "divya.m@messmate.demo",
         "password": member_pw, "initials": "DM", "tone": "member",
         "caption": "Committee member"},
        {"role": "Committee member", "name": "Faizal Ahmed", "email": "faizal.a@messmate.demo",
         "password": member_pw, "initials": "FA", "tone": "member",
         "caption": "Committee member"},
        {"role": "Dean", "name": "Read-only", "email": VIEWER_EMAIL, "password": viewer_pw,
         "initials": "Dn", "tone": "viewer", "badge": "read-only",
         "caption": "Both dashboards, nothing that changes state — the same view the ?token= link gives"},
        {"role": "Admin", "name": "Mess manager", "email": ADMIN_EMAIL, "password": admin_pw,
         "initials": "Ad", "tone": "admin", "badge": "full access",
         "caption": "Overview, the weekly menu editor, the roster and both dashboards"},
    ]
