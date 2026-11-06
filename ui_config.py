"""
MessMate Global UI Configuration (ui_config.py)
------------------------------------------------
The ONE place the look and the UI behaviour of every page are configured.

    DESIGN_TOKENS   every CSS custom property the design system uses —
                    colours, type, spacing, radius, elevation, motion, chart
                    palette. Served as /ui/tokens.css (a :root block) and
                    loaded by every page before static/style.css, so the
                    stylesheet, Chart.js (static/charts.js reads the computed
                    values) and any inline style all draw from this dict.

    SCORE_BANDS     where a 1-5 score turns red / amber / green.
    TAP_BANDS       where a "% liked" tally turns poor / mixed / good.
    APP             name, tagline, the institution the committee belongs to.

Templates get it as the Jinja global `ui` (ui.score_band(), ui.tap_band(),
ui.app, ui.json for the <script> handoff); scripts read window.MESSMATE_UI,
which _head.html and home.html emit from ui.json.

Change a value here and it changes everywhere. Nothing below the token layer
of style.css may carry a raw colour or threshold.
"""

from collections import OrderedDict
import json

from flask import Response
from markupsafe import Markup

# ── App identity ──────────────────────────────────────────────────────────────
APP = {
    "name": "MessMate",
    "wordmark": "MESSMATE",
    "tagline": "College mess food review",
    "institution": "SaiU",
}

# ── Score bands ───────────────────────────────────────────────────────────────
# A 1-5 average: below red_below is red, up to amber_upto is amber, above is
# green. The same thresholds colour stat cards (templates), bars (charts) and
# the overview's attention list (app.py).
SCORE_BANDS = {"red_below": 2.5, "amber_upto": 3.5}

# A quick-tap "% liked" (good as a share of good + bad): below poor_below is
# poor, below good_from is mixed, otherwise good.
TAP_BANDS = {"poor_below": 40, "good_from": 70}


def score_band(score):
    """'red' | 'amber' | 'green' for a 1-5 score; '' when there is no score."""
    try:
        score = float(score)
    except (TypeError, ValueError):
        return ""
    if score <= 0:
        return ""
    if score < SCORE_BANDS["red_below"]:
        return "red"
    if score <= SCORE_BANDS["amber_upto"]:
        return "amber"
    return "green"


def score_class(score):
    """The stat-card class for a score: 'score-green' etc., or ''."""
    band = score_band(score)
    return f"score-{band}" if band else ""


def tap_band(percent, rated=True):
    """'poor' | 'mixed' | 'good' for a % liked; '' when nobody rated."""
    if not rated:
        return ""
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        return ""
    if percent < TAP_BANDS["poor_below"]:
        return "poor"
    if percent < TAP_BANDS["good_from"]:
        return "mixed"
    return "good"


# Tap bands map onto the same three colours as score bands
TAP_TO_SCORE = {"poor": "red", "mixed": "amber", "good": "green"}


def tap_class(percent, rated=True):
    band = tap_band(percent, rated)
    return f"score-{TAP_TO_SCORE[band]}" if band else ""


# ── Design tokens ─────────────────────────────────────────────────────────────
# Order matters only for readability. Values are exactly what style.css used
# to declare in its :root block; they are served from here instead so that
# there is one source.
DESIGN_TOKENS = OrderedDict([
    # Surfaces — the dark app shell
    ("--bg-900", "#0f1724"),
    ("--bg-850", "#0f2027"),
    ("--bg-800", "#1a2438"),
    ("--app-gradient", "linear-gradient(160deg, var(--bg-900) 0%, var(--bg-800) 50%, var(--bg-850) 100%)"),
    ("--surface", "rgba(255, 255, 255, 0.04)"),
    ("--surface-hover", "rgba(255, 255, 255, 0.07)"),
    ("--surface-active", "rgba(255, 255, 255, 0.09)"),
    ("--surface-sunken", "rgba(15, 23, 36, 0.60)"),
    ("--border", "rgba(255, 255, 255, 0.08)"),
    ("--border-strong", "rgba(255, 255, 255, 0.14)"),
    ("--border-hover", "rgba(255, 255, 255, 0.24)"),
    ("--chrome-bg", "rgba(15, 23, 36, 0.85)"),
    # Text — on the dark shell, all AA on --surface
    ("--text-strong", "#f1f5f9"),
    ("--text", "#e8eef7"),
    ("--text-2", "#e2e8f0"),
    ("--text-3", "#cbd5e1"),
    ("--text-muted", "#94a3b8"),
    ("--text-faint", "#8b9ab0"),
    # Brand + accent
    ("--brand-from", "#60a5fa"),
    ("--brand-to", "#a78bfa"),
    ("--accent", "#3b82f6"),
    ("--accent-strong", "#2563eb"),
    ("--accent-2", "#6366f1"),
    ("--accent-ink", "#93c5fd"),
    ("--accent-bg", "rgba(59, 130, 246, 0.10)"),
    ("--accent-bg-hover", "rgba(59, 130, 246, 0.18)"),
    ("--accent-border", "rgba(59, 130, 246, 0.25)"),
    ("--accent-gradient", "linear-gradient(135deg, var(--accent), var(--accent-2))"),
    ("--brand-gradient", "linear-gradient(90deg, var(--brand-from), var(--brand-to))"),
    # Semantic
    ("--ok", "#22c55e"),
    ("--ok-strong", "#16a34a"),
    ("--ok-text", "#6ee7a0"),
    ("--ok-text-2", "#86efac"),
    ("--ok-bg", "rgba(34, 197, 94, 0.12)"),
    ("--ok-border", "rgba(34, 197, 94, 0.30)"),
    ("--ok-glow", "rgba(34, 197, 94, 0.55)"),        # the live / serving pulse ring
    ("--warn", "#fbbf24"),
    ("--warn-text", "#fcd34d"),
    ("--warn-bg", "rgba(251, 146, 60, 0.16)"),
    ("--warn-border", "rgba(251, 191, 36, 0.40)"),
    ("--danger", "#f87171"),
    ("--danger-strong", "#ef4444"),
    ("--danger-text", "#fca5a5"),
    ("--danger-bg", "rgba(239, 68, 68, 0.12)"),
    ("--danger-border", "rgba(239, 68, 68, 0.30)"),
    ("--violet-text", "#c4b5fd"),
    ("--violet-bg", "rgba(167, 139, 250, 0.16)"),
    ("--amber-tag", "#f59e0b"),
    ("--amber-tag-bg", "rgba(245, 158, 11, 0.15)"),
    ("--amber-tag-border", "rgba(245, 158, 11, 0.30)"),
    # Legacy light primaries — kept for anything external that references them
    ("--blue-600", "#2E75B6"),
    ("--blue-800", "#1F4E79"),
    # Typography
    ("--font-sans", "'Inter', -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"),
    ("--font-mono", "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"),
    ("--fs-xs", "0.74rem"),
    ("--fs-sm", "0.82rem"),
    ("--fs-md", "0.92rem"),
    ("--fs-base", "1rem"),
    ("--fs-lg", "1.15rem"),
    ("--fs-xl", "1.55rem"),
    ("--fs-stat", "42px"),
    ("--lh", "1.5"),
    # Spacing scale
    ("--sp-1", "4px"),
    ("--sp-2", "8px"),
    ("--sp-3", "12px"),
    ("--sp-4", "16px"),
    ("--sp-5", "20px"),
    ("--sp-6", "24px"),
    ("--sp-7", "30px"),
    ("--sp-8", "40px"),
    # Page rail widths
    ("--w-wide", "1200px"),
    ("--w-mid", "900px"),
    ("--w-narrow", "640px"),
    ("--w-auth", "400px"),
    ("--page-width", "var(--w-wide)"),
    ("--rail-pad", "20px"),
    # Radius
    ("--r-sm", "8px"),
    ("--r-md", "12px"),
    ("--r-lg", "16px"),
    ("--r-xl", "20px"),
    ("--r-pill", "999px"),
    # Elevation — offset plus soft blur, never a zero-offset halo
    ("--shadow-card", "0 10px 34px rgba(0, 0, 0, 0.28)"),
    ("--shadow-raised", "0 24px 70px rgba(0, 0, 0, 0.45)"),
    ("--shadow-accent", "0 6px 20px rgba(59, 130, 246, 0.35)"),
    ("--shadow-ok", "0 4px 16px rgba(34, 197, 94, 0.15)"),
    ("--shadow-danger", "0 4px 16px rgba(239, 68, 68, 0.12)"),
    # Motion
    ("--dur", "180ms"),
    ("--dur-slow", "240ms"),
    ("--ease", "cubic-bezier(0.22, 0.61, 0.36, 1)"),
    # Focus — one ring everywhere
    ("--focus-ring", "0 0 0 3px rgba(96, 165, 250, 0.55)"),
    # Stacking
    ("--z-topbar", "100"),
    ("--z-float", "50"),
    # Minimum tap target
    ("--tap", "44px"),

    # Charts + score bands (read by static/charts.js from the computed style)
    ("--score-red",   "#EF5350"),
    ("--score-amber", "#FFB300"),
    ("--score-green", "#66BB6A"),
    ("--chart-line",  "#60a5fa"),
    ("--chart-fill",  "rgba(96, 165, 250, 0.14)"),
    ("--chart-grid",  "rgba(148, 163, 184, 0.12)"),
    ("--chart-dim-1", "#8E24AA"),
    ("--chart-dim-2", "#00897B"),
    ("--chart-dim-3", "#F4511E"),
    ("--chart-dim-4", "#3949AB"),
    ("--chart-dim-5", "#7CB342"),
])


def tokens_css():
    """The :root block, rendered from DESIGN_TOKENS."""
    lines = ["/* Generated from ui_config.DESIGN_TOKENS — edit that, not this. */", ":root {"]
    for name, value in DESIGN_TOKENS.items():
        lines.append(f"    {name}: {value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def as_dict():
    """What the browser needs: identity and thresholds (not the tokens — CSS
    already has those, and charts.js reads them from the computed style)."""
    return {"app": APP, "scoreBands": SCORE_BANDS, "tapBands": TAP_BANDS}


class _UI:
    """The `ui` Jinja global."""
    app = APP
    score_bands = SCORE_BANDS
    tap_bands = TAP_BANDS
    score_band = staticmethod(score_band)
    score_class = staticmethod(score_class)
    tap_band = staticmethod(tap_band)
    tap_class = staticmethod(tap_class)

    @property
    def json(self):
        return Markup(json.dumps(as_dict()))


def init_app(app):
    """Registers the `ui` template global and the /ui/tokens.css route."""
    app.jinja_env.globals["ui"] = _UI()

    @app.route("/ui/tokens.css")
    def ui_tokens():
        response = Response(tokens_css(), mimetype="text/css")
        response.headers["Cache-Control"] = "public, max-age=300"
        return response
