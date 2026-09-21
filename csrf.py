"""
MessMate CSRF Protection (csrf.py)
-----------------------------------
Per-session CSRF tokens for authenticated state-changing POSTs.

Why this exists now and not before: until the Food Committee module, the only
POST in MessMate was the anonymous student form. Forging a request to it is
meaningless — there is no session to ride and the submission is anonymous
anyway. Once an admin can create accounts and reset passwords over an
authenticated session, that stops being true, and CSRF becomes exploitable.

Deliberately hand-rolled rather than pulling in Flask-WTF: it is ~25 lines,
adds no dependency, and matches the project's minimal requirements.txt.

Usage:
    csrf.init_app(app)                      # registers the csrf_field() global
    {{ csrf_field() }}                      # inside every protected <form>
    @csrf.protect                           # on every state-changing POST route
"""

import secrets
from functools import wraps
from flask import session, request, abort
from markupsafe import Markup

SESSION_KEY = "_csrf_token"
FORM_FIELD = "csrf_token"


def issue_token():
    """Returns this session's CSRF token, generating one on first use."""
    if SESSION_KEY not in session:
        session[SESSION_KEY] = secrets.token_urlsafe(32)
    return session[SESSION_KEY]


def validate_token(submitted):
    """
    Constant-time comparison of a submitted token against the session's.
    Returns False if either side is missing.
    """
    expected = session.get(SESSION_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(str(expected), str(submitted))


def protect(view):
    """
    Decorator: rejects a POST whose CSRF token is missing or wrong with 403.
    Non-POST methods pass through untouched.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == "POST":
            if not validate_token(request.form.get(FORM_FIELD)):
                abort(403)
        return view(*args, **kwargs)
    return wrapped


def csrf_field():
    """Renders the hidden input. Markup() so Jinja does not escape the tag."""
    return Markup(
        f'<input type="hidden" name="{FORM_FIELD}" value="{issue_token()}">'
    )


def init_app(app):
    """Exposes csrf_field() to all templates."""
    app.jinja_env.globals["csrf_field"] = csrf_field
