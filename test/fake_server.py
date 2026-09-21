"""
MessMate UI Test Server (test/fake_server.py)
----------------------------------------------
Runs the real Flask app against the in-memory sheets fake, so the Robot
Framework UI suites can drive a real browser without Google credentials or a
live spreadsheet.

Everything except the network layer is the production code path: the same
routes, templates, session handling, CSRF, and aggregation.

It also registers one route that does NOT exist in the real app —
POST /__test__/reset — which restores the seeded fixture. Suites call it in
setup so they are order-independent and can freely mutate the roster. Keeping
it here rather than in app.py means no test-only route ever ships.

Usage:
    python test/fake_server.py [port]

Seeded fixture:
    admin password                    admin-test-password
    robot-test-member@sai.edu         robot-test-password    (ready to rate)
    robot-test-newbie@sai.edu         robot-test-newbie      (must change password)
    robot-test-retired@sai.edu        robot-test-retired     (deactivated)
    robot-test-rated@sai.edu          robot-test-rated       (already rated today)
    plus six days of review history for the trend chart, and today's menu
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin-test-password")

os.environ.setdefault("FLASK_SECRET_KEY", "ui-test-secret-key")
os.environ.setdefault("SPREADSHEET_ID", "fake-spreadsheet-id")
os.environ.setdefault("DASHBOARD_TOKEN", "vc2026")

import auth  # noqa: E402

os.environ["ADMIN_PASSWORD_HASH"] = auth.hash_password(ADMIN_PASSWORD)

import fake_sheets  # noqa: E402
import app as app_module  # noqa: E402

app = app_module.app
BOOK = fake_sheets.install()

# The UI suites sign in repeatedly; the production caps would trip mid-suite
app_module.limiter.enabled = False


def seed():
    """Restores the fixture. Called at boot and by /__test__/reset."""
    BOOK.reset()

    BOOK.seed_member("robot-test-member@sai.edu", "Robot Test Member",
                     "robot-test-password")
    BOOK.seed_member("robot-test-newbie@sai.edu", "Robot Test Newbie",
                     "robot-test-newbie", must_change=True)
    BOOK.seed_member("robot-test-retired@sai.edu", "Robot Test Retired",
                     "robot-test-retired", active=False, term_end="2026-06-30")
    BOOK.seed_member("robot-test-rated@sai.edu", "Robot Test Rated",
                     "robot-test-rated")

    today = datetime.now().strftime("%Y-%m-%d")

    # One member has already rated today, so the already-reviewed path is
    # reachable without a test having to submit first
    BOOK.seed_review("robot-test-rated@sai.edu", "Robot Test Rated", today,
                     [4, 4, 3, 5, 4], "Already reviewed earlier today")

    # Six days of history so the trend chart and its 7/30 toggle have data
    for offset in range(1, 7):
        date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        score = 3 + (offset % 3)
        BOOK.seed_review("robot-test-member@sai.edu", "Robot Test Member",
                         date, [score] * 5, f"Historic review from day -{offset}")

    # Today's menu, so the home page has something to show. Comma-separated
    # exactly as mess staff would type it into the sheet or the editor.
    BOOK.seed_menu(today,
                   breakfast="Idli, Sambar, Coconut Chutney",
                   lunch="Rice, Sambar, Poriyal, Curd, Papad",
                   dinner="Chapati, Paneer Gravy, Salad")

    # Student-side data so the student dashboard has something to render.
    # The per-item scores matter: with all ten blank, dashboard.js takes its
    # empty-state path and replaces the #itemChart canvas with a message, so
    # the dashboard renders without an element it normally has.
    student_items = [4, 3, 5, 4, 4, 3, 5, 4, 3, 4]
    for offset in range(0, 3):
        date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        BOOK.seed_student_response(date, 4, "Student review",
                                   "Student suggestion", items=student_items)


def reset_endpoint():
    """Test-only fixture reset. Never registered on the production app."""
    seed()
    return {"status": "reset"}, 200


app.add_url_rule("/__test__/reset", "test_reset", reset_endpoint,
                 methods=["POST", "GET"])


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    seed()
    print(f"MessMate UI test server on http://localhost:{port}")
    print(f"  admin password: {ADMIN_PASSWORD}")
    print("  fixture reset:  POST /__test__/reset")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
