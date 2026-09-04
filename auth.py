"""
MessMate Authentication (auth.py)
----------------------------------
Session auth for the Food Committee module, plus the admin gate.

Two distinct privilege levels, deliberately separated:

  admin_view_required  — accepts an admin session OR the legacy ?token=
                         query string. Read-only pages only.
  admin_required       — admin SESSION only. Every state-changing route.

The split exists because a query-string secret leaks into browser history,
Referer headers on outbound links, and the hosting platform's access logs.
That is an acceptable risk for a read-only dashboard (and keeps existing
bookmarks and the Robot suite working), but not for a page that can mint
committee accounts. Anyone who recovered DASHBOARD_TOKEN from a log must not
be able to create themselves a login.

Passwords use werkzeug.security (scrypt by default) — already a Flask
dependency, so no new package.
"""

import os
import re
import secrets
from functools import wraps

from flask import session, request, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

import sheets

# ── Session keys ──────────────────────────────────────────────────────────────
MEMBER_KEY = "member_email"
MEMBER_NAME_KEY = "member_name"
ADMIN_KEY = "is_admin"

# Password generation alphabet — 0/O and 1/l/I removed. These passwords get
# read off a screen and typed by hand or relayed over chat, where lookalike
# characters cause support requests.
_PW_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
_PW_GROUPS = 3
_PW_GROUP_LEN = 4

MIN_PASSWORD_LENGTH = 8

# Intentionally permissive: catches typos and obvious junk without rejecting
# the legitimately strange addresses a stricter pattern would.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Password helpers ──────────────────────────────────────────────────────────

def generate_password():
    """
    Returns a readable one-time password, e.g. 'mesa-7kfp-q3xr'.
    ~60 bits of entropy — fine for a credential that must be changed at first
    login and only has to survive being read off a screen.
    """
    groups = [
        "".join(secrets.choice(_PW_ALPHABET) for _ in range(_PW_GROUP_LEN))
        for _ in range(_PW_GROUPS)
    ]
    return "-".join(groups)


def hash_password(password):
    """Hashes a password for storage. The only thing ever written to the sheet."""
    return generate_password_hash(password)


# ── Email normalisation ───────────────────────────────────────────────────────

def normalize_email(raw):
    """
    Normalises and validates an email address.

    Returns (email, None) on success or (None, error_message) on failure.
    Enforces COMMITTEE_EMAIL_DOMAIN when that env var is set; any domain is
    accepted when it is unset.
    """
    email = str(raw or "").strip().lower()

    if not email:
        return None, "Email is required."
    if not _EMAIL_RE.match(email):
        return None, f"'{email}' is not a valid email address."

    allowed_domain = os.environ.get("COMMITTEE_EMAIL_DOMAIN", "").strip().lower()
    if allowed_domain and not email.endswith("@" + allowed_domain):
        return None, f"Email must be on the @{allowed_domain} domain."

    return email, None


# ── Member authentication ─────────────────────────────────────────────────────

def verify_member(email, password):
    """
    Verifies committee member credentials.
    Returns the member dict on success, None on any failure.

    Deliberately returns None identically for an unknown email, a wrong
    password, and a deactivated member — the login page must not reveal which
    addresses are on the committee.
    """
    if not email or not password:
        return None

    member = sheets.get_committee_member(email)
    if not member:
        return None
    if not member.get("is_active"):
        return None

    stored_hash = str(member.get("Password_Hash", ""))
    if not stored_hash:
        return None

    try:
        if not check_password_hash(stored_hash, password):
            return None
    except Exception as e:
        print(f"Error checking password hash: {e}")
        return None

    return member


def login_member(member):
    """Establishes a member session."""
    session.permanent = True
    session[MEMBER_KEY] = str(member.get("Email", "")).strip().lower()
    session[MEMBER_NAME_KEY] = member.get("Name", "")


def current_member():
    """
    Returns the logged-in member's CURRENT roster record, or None.

    Re-reads the roster (cached) rather than trusting the session, so a member
    deactivated mid-session loses access on their next request instead of
    keeping it until the cookie expires.
    """
    email = session.get(MEMBER_KEY)
    if not email:
        return None

    member = sheets.get_committee_member(email)
    if not member or not member.get("is_active"):
        return None
    return member


def logout_member():
    """Clears member session keys."""
    session.pop(MEMBER_KEY, None)
    session.pop(MEMBER_NAME_KEY, None)


# ── Admin authentication ──────────────────────────────────────────────────────

def verify_admin(password):
    """
    Verifies the admin password against ADMIN_PASSWORD_HASH.

    Generate the hash with:  python manage_committee.py hash-admin-password
    Returns False when the env var is unset, so a misconfigured deployment
    fails closed rather than admitting everyone.
    """
    stored_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    if not stored_hash or not password:
        return False
    try:
        return check_password_hash(stored_hash, password)
    except Exception as e:
        print(f"Error checking admin password hash: {e}")
        return False


def login_admin():
    session.permanent = True
    session[ADMIN_KEY] = True


def logout_admin():
    session.pop(ADMIN_KEY, None)


def is_admin_session():
    return bool(session.get(ADMIN_KEY))


def has_valid_token():
    """
    True if the request carries the legacy ?token=DASHBOARD_TOKEN credential.
    Read-only access only — never sufficient for a mutation.
    """
    expected = os.environ.get("DASHBOARD_TOKEN", "")
    supplied = request.args.get("token", "")
    if not expected or not supplied:
        return False
    return secrets.compare_digest(str(expected), str(supplied))


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(view):
    """Requires an active committee member session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_member() is None:
            logout_member()  # clear a session whose member was deactivated
            return redirect(url_for("committee_login"))
        return view(*args, **kwargs)
    return wrapped


def password_change_required(view):
    """
    Blocks a member carrying Must_Change_Password from anything except the
    change-password page. Applied after login_required.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        member = current_member()
        if member and member.get("must_change_password"):
            return redirect(url_for("committee_password"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """
    Admin SESSION only — for every state-changing admin route.
    A ?token= request is refused here by design.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_session():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_view_required(view):
    """
    Admin session OR ?token= — for read-only dashboards.
    Preserves the existing /dashboard?token= behaviour, including its 403 text.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if is_admin_session() or has_valid_token():
            return view(*args, **kwargs)
        return "Access denied. Add ?token=YOUR_TOKEN to the URL.", 403
    return wrapped
