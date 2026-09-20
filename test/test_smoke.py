"""
MessMate Smoke Tests (test/test_smoke.py)
-------------------------------------------
One or two assertions per feature — "is this switched on at all" — across
every feature in the app. Not a substitute for the journey suites; this is
the check you run in seconds before a demo, after a deploy, or to decide
whether a longer suite is even worth starting.

Two modes:

  Local (default)   in-process Flask test client over the in-memory sheets
                    backend. No credentials, no server, no network. Runs
                    every check, including the ones that write.

      python test/test_smoke.py

  Live              plain HTTP against a running deployment. Runs only the
                    READ-ONLY checks, so pointing it at production cannot
                    create members, submit feedback, or touch a real
                    spreadsheet.

      python test/test_smoke.py --url https://messmate.onrender.com
      python test/test_smoke.py --url http://localhost:5000 --token vc2026

Exit code 0 = every feature answered.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Results ───────────────────────────────────────────────────────────────────

RESULTS = []
_feature = {"name": None}


def feature(name):
    _feature["name"] = name


def check(description, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((_feature["name"], description, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {_feature['name']:<24} {description}")
    if not ok and detail:
        print(f"         -> {detail}")
    return ok


def skipped(description, why):
    RESULTS.append((_feature["name"], description, None, why))
    print(f"  [SKIP] {_feature['name']:<24} {description}  ({why})")


CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


# ══════════════════════════════════════════════════════════════════════════════
# Transports — both expose .get()/.post() returning (status, text)
# ══════════════════════════════════════════════════════════════════════════════

class LocalTransport:
    """In-process Flask client over the in-memory sheets backend."""

    writes_allowed = True
    label = "in-process (in-memory sheets)"

    def __init__(self):
        os.environ["FLASK_SECRET_KEY"] = "smoke-test-secret-key"
        os.environ["SPREADSHEET_ID"] = "fake-spreadsheet-id"
        os.environ["DASHBOARD_TOKEN"] = "vc2026"

        import auth
        self.admin_password = "smoke-admin-password"
        os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(self.admin_password)

        import fake_sheets
        import app as app_module

        self.app = app_module.app
        self.app.config["TESTING"] = True
        # Flask-Limiter reads RATELIMIT_ENABLED at construction, which already
        # happened at import; the instance attribute is the live switch
        app_module.limiter.enabled = False

        self.book = fake_sheets.install()
        self.token = "vc2026"
        self._seed()

    def _seed(self):
        self.book.reset()
        self.book.seed_member("smoke@sai.edu", "Smoke Member", "smoke-password")
        self.book.seed_student_response(
            __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
            4, "Smoke review", "Smoke suggestion", items=[4] * 10)

    def session(self):
        return self.app.test_client()

    @staticmethod
    def get(client, path):
        response = client.get(path)
        return response.status_code, response.get_data(as_text=True)

    @staticmethod
    def post(client, path, data):
        response = client.post(path, data=data)
        return response.status_code, response.get_data(as_text=True)


class LiveTransport:
    """Plain HTTP against a deployment. Read-only checks only."""

    writes_allowed = False

    def __init__(self, base_url, token):
        import requests
        self.requests = requests
        self.base = base_url.rstrip("/")
        self.token = token
        self.admin_password = None
        self.label = f"live deployment at {self.base}"

    def session(self):
        return self.requests.Session()

    def get(self, client, path):
        response = client.get(self.base + path, timeout=30, allow_redirects=False)
        return response.status_code, response.text

    def post(self, client, path, data):
        response = client.post(self.base + path, data=data, timeout=30,
                               allow_redirects=False)
        return response.status_code, response.text


# ══════════════════════════════════════════════════════════════════════════════
# Feature checks
# ══════════════════════════════════════════════════════════════════════════════

def smoke(t):
    client = t.session()

    # ── Service ───────────────────────────────────────────────────────────
    feature("service")
    status, body = t.get(client, "/health")
    check("health endpoint answers", status == 200 and '"ok"' in body,
          f"status={status}")

    feature("static assets")
    css_status, _ = t.get(client, "/static/style.css")
    js_status, _ = t.get(client, "/static/dashboard.js")
    check("stylesheet and dashboard script are served",
          css_status == 200 and js_status == 200,
          f"css={css_status} js={js_status}")

    # ── Student feedback ──────────────────────────────────────────────────
    feature("student form")
    status, body = t.get(client, "/")
    check("feedback form renders",
          status == 200 and "How was today" in body, f"status={status}")
    check("emoji rating widget is present", 'class="emoji-btn"' in body)

    feature("student submit")
    if t.writes_allowed:
        status, _ = t.post(t.session(), "/submit",
                           {"overall": "4", "review": "smoke test",
                            "suggestion": "smoke suggestion"})
        check("a valid submission is accepted", status == 302,
              f"status={status}")
        status, _ = t.post(t.session(), "/submit", {"review": "no score"})
        check("a submission with no overall score is refused", status == 200)
    else:
        skipped("submission accepted", "write check, live mode is read-only")

    feature("thank-you page")
    status, body = t.get(client, "/thanks")
    check("renders after submission", status == 200 and "Thanks" in body,
          f"status={status}")

    # ── Student dashboard ─────────────────────────────────────────────────
    feature("student dashboard")
    status, _ = t.get(client, "/dashboard")
    check("is refused without a token", status == 403, f"status={status}")
    status, body = t.get(client, f"/dashboard?token={t.token}")
    check("opens with the token", status == 200, f"status={status}")
    check("renders its stat cards and charts",
          'class="stat-cards"' in body and 'id="trendChart"' in body)

    # ── Committee auth ────────────────────────────────────────────────────
    feature("committee login")
    status, body = t.get(client, "/committee/login")
    check("login page renders",
          status == 200 and 'id="email"' in body, f"status={status}")
    check("states that reviews are attributed", "not anonymous" in body)

    feature("committee auth")
    status, _ = t.get(client, "/committee")
    check("rating page is closed to anonymous visitors", status == 302,
          f"status={status}")
    if t.writes_allowed:
        member = t.session()
        _, page = t.get(member, "/committee/login")
        token = CSRF_RE.search(page).group(1)
        status, _ = t.post(member, "/committee/login",
                           {"email": "smoke@sai.edu", "password": "smoke-password",
                            "csrf_token": token})
        check("a valid member can sign in", status == 302, f"status={status}")

        status, body = t.get(member, "/committee")
        check("the rating page offers all five dimensions",
              status == 200 and all(f'name="{d}"' in body for d in
                                    ("taste", "quality", "variety",
                                     "hygiene", "menu")),
              f"status={status}")

        feature("committee submit")
        token = CSRF_RE.search(body).group(1)
        status, _ = t.post(member, "/committee/submit",
                           {"taste": "4", "quality": "4", "variety": "4",
                            "hygiene": "4", "menu": "4",
                            "review": "smoke review", "csrf_token": token})
        check("a complete review is accepted", status == 302, f"status={status}")
    else:
        skipped("member sign-in", "write check, live mode is read-only")
        skipped("review submission", "write check, live mode is read-only")

    # ── Admin ─────────────────────────────────────────────────────────────
    feature("admin login")
    status, body = t.get(client, "/admin/login")
    check("admin login page renders",
          status == 200 and 'id="password"' in body, f"status={status}")

    feature("admin roster")
    status, _ = t.get(client, "/admin/members")
    check("roster is closed without an admin session", status == 302,
          f"status={status}")
    if t.writes_allowed:
        admin = t.session()
        _, page = t.get(admin, "/admin/login")
        token = CSRF_RE.search(page).group(1)
        t.post(admin, "/admin/login",
               {"password": t.admin_password, "csrf_token": token})
        status, body = t.get(admin, "/admin/members")
        check("roster opens with an admin session",
              status == 200 and 'id="members-table"' in body, f"status={status}")
        check("add and bulk-add forms are present",
              'id="add-member-form"' in body and 'id="bulk-add-form"' in body)

        feature("member management")
        token = CSRF_RE.search(body).group(1)
        status, body = t.post(admin, "/admin/members/add",
                              {"name": "Smoke Added", "email": "smoke-added@sai.edu",
                               "csrf_token": token})
        check("adding a member reveals a one-time password",
              status == 200 and "credential-banner" in body, f"status={status}")
    else:
        skipped("roster opens for admin", "write check, live mode is read-only")
        skipped("member management", "write check, live mode is read-only")

    # ── Committee dashboard ───────────────────────────────────────────────
    feature("committee dashboard")
    status, _ = t.get(client, "/dashboard/committee")
    check("is refused without a credential", status == 403, f"status={status}")
    status, body = t.get(client, f"/dashboard/committee?token={t.token}")
    check("opens with the token", status == 200, f"status={status}")
    check("renders its stat cards and charts",
          'class="stat-cards"' in body and 'id="dimensionChart"' in body)

    # ── Security posture ──────────────────────────────────────────────────
    feature("privilege split")
    status, _ = t.get(client, f"/admin/members?token={t.token}")
    check("the dashboard token cannot open the roster", status == 302,
          f"status={status} — a read-only token must not reach member management")

    feature("csrf")
    status, _ = t.post(t.session(), "/committee/login",
                       {"email": "smoke@sai.edu", "password": "smoke-password"})
    check("a POST with no CSRF token is rejected", status == 403,
          f"status={status}")


# ══════════════════════════════════════════════════════════════════════════════

def report(label):
    print(f"\n{'=' * 72}")
    passed = [r for r in RESULTS if r[2] is True]
    failed = [r for r in RESULTS if r[2] is False]
    skips = [r for r in RESULTS if r[2] is None]

    features = sorted({r[0] for r in RESULTS})
    broken = sorted({r[0] for r in failed})

    print(f"SMOKE — {label}")
    print(f"{'=' * 72}")
    print(f"  {len(passed)} passed, {len(failed)} failed, {len(skips)} skipped "
          f"across {len(features)} features")

    if broken:
        print(f"\n  FEATURES DOWN: {', '.join(broken)}")
        for name, description, _, detail in failed:
            print(f"    {name}: {description}")
            if detail:
                print(f"      {detail}")
    else:
        print(f"\n  All {len(features)} features responded: {', '.join(features)}")

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="MessMate smoke tests — one or two checks per feature.")
    parser.add_argument("--url", help="Run read-only checks against a live "
                                      "deployment instead of in-process.")
    parser.add_argument("--token", default=os.environ.get("DASHBOARD_TOKEN", "vc2026"),
                        help="Dashboard token for the live deployment.")
    args = parser.parse_args()

    if args.url:
        try:
            import requests  # noqa: F401
        except ImportError:
            print("Live mode needs requests: pip install requests")
            return 2
        transport = LiveTransport(args.url, args.token)
        print(f"MessMate smoke tests — {transport.label}")
        print("Read-only: nothing is submitted, created, or written.\n")
    else:
        transport = LocalTransport()
        print(f"MessMate smoke tests — {transport.label}")
        print("No Google credentials required.\n")

    smoke(transport)
    return report(transport.label)


if __name__ == "__main__":
    sys.exit(main())
