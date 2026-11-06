"""
Anonymous per-device memory (device.py)
----------------------------------------
Two signed cookies and nothing else. Nothing here reaches the spreadsheet, so
the promise the student pages make — no identity stored — still holds: the
sheet never sees a device id, and the id is random, not derived from anything.

    mm_device   a random id. The rate limiters key on it ("3 quick taps per
                device per day", "one dish review per device every 4 hours")
                instead of the IP, which on a hostel network is shared by the
                whole building.
    mm_rated    {"date": "YYYY-MM-DD", "taps": {"Lunch": {"rating": "good",
                "ts": "YYYY-MM-DD HH:MM:SS"}}} — what this device said today,
                so the home page can show it back, refuse a second tap on the
                same meal, and offer Undo for a few minutes.

Both are signed with the app secret (tampering invalidates them) and are
httponly + SameSite=Lax, like the session cookie. Clearing cookies forgets
everything, which is the honest limit of "per device" without a login.
"""

import json
import uuid
from datetime import datetime, timedelta

from flask import current_app, g, request
from itsdangerous import BadSignature, URLSafeSerializer

DEVICE_COOKIE = "mm_device"
RATED_COOKIE = "mm_rated"

DEVICE_MAX_AGE = 365 * 24 * 3600      # a year; refreshed on every visit
RATED_MAX_AGE = 36 * 3600             # outlives the day it describes, then expires
UNDO_WINDOW = timedelta(minutes=10)   # how long after a tap Undo is offered

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _serializer():
    return URLSafeSerializer(current_app.secret_key, salt="messmate-device")


def _load(cookie_name):
    raw = request.cookies.get(cookie_name)
    if not raw:
        return None
    try:
        return _serializer().loads(raw)
    except BadSignature:
        return None


# ── Device id ─────────────────────────────────────────────────────────────────

def device_id():
    """
    This device's id, minted on first sight. Safe to call from a rate-limiter
    key function: it only reads the request and marks g; the cookie itself is
    written by the after_request hook.
    """
    if "mm_device" in g:
        return g.mm_device
    value = _load(DEVICE_COOKIE)
    if not isinstance(value, str) or len(value) != 32:
        value = uuid.uuid4().hex
        g.mm_device_new = True
    g.mm_device = value
    return value


# ── What this device rated today ──────────────────────────────────────────────

def _today():
    return datetime.now().strftime("%Y-%m-%d")


def rated_today():
    """{meal: {"rating": ..., "ts": ...}} for today; {} for any other day."""
    if "mm_rated" in g:
        return g.mm_rated
    data = _load(RATED_COOKIE)
    taps = {}
    if isinstance(data, dict) and data.get("date") == _today():
        candidate = data.get("taps")
        if isinstance(candidate, dict):
            taps = {str(meal): entry for meal, entry in candidate.items()
                    if isinstance(entry, dict) and "rating" in entry and "ts" in entry}
    g.mm_rated = taps
    return taps


def remember(meal, rating, ts):
    """Records a tap for today. `ts` is the sheet row's Timestamp string."""
    taps = dict(rated_today())
    taps[meal] = {"rating": rating, "ts": ts}
    g.mm_rated = taps
    g.mm_rated_dirty = True


def forget(meal):
    taps = dict(rated_today())
    taps.pop(meal, None)
    g.mm_rated = taps
    g.mm_rated_dirty = True


def can_undo(entry, now=None):
    """True while the tap is recent enough to take back."""
    try:
        tapped_at = datetime.strptime(entry["ts"], TS_FORMAT)
    except (KeyError, TypeError, ValueError):
        return False
    return (now or datetime.now()) - tapped_at <= UNDO_WINDOW


# ── Cookie writing ────────────────────────────────────────────────────────────

def init_app(app):
    @app.after_request
    def _write_device_cookies(response):
        secure = bool(app.config.get("SESSION_COOKIE_SECURE"))
        if g.get("mm_device_new"):
            response.set_cookie(
                DEVICE_COOKIE, _serializer().dumps(g.mm_device),
                max_age=DEVICE_MAX_AGE, httponly=True, samesite="Lax", secure=secure)
        if g.get("mm_rated_dirty"):
            payload = {"date": _today(), "taps": g.get("mm_rated", {})}
            response.set_cookie(
                RATED_COOKIE, _serializer().dumps(payload),
                max_age=RATED_MAX_AGE, httponly=True, samesite="Lax", secure=secure)
        return response
