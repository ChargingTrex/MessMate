"""
MessMate Global UI Configuration (ui_config.py)
------------------------------------------------
The ONE place the look and the UI behaviour of every page are configured.

    SHARED_TOKENS   the tokens both themes share: type sizes, spacing,
                    radius, motion, rail widths.
    THEMES          the two colour themes, dark (the original glass shell)
                    and light (Ilai: banana leaf and spice). Same token
                    names, different values. DEFAULT_THEME picks which one a
                    visitor starts on; the top-bar switch overrides it.
    FONTS_URL       every web font either theme loads.

                    All of it is served as /ui/tokens.css and loaded by every
                    page before static/style.css, so the stylesheet, Chart.js
                    (static/charts.js reads the computed values) and any
                    inline style draw from here.

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


# ── Themes ────────────────────────────────────────────────────────────────────
# Two themes share every token name; only the values differ.
#   dark    the original glass shell
#   light   "Ilai" v2: banana leaf, rice and the side dishes, on Material 3 roles
#           (docs/ilai-design-system.html is its reference sheet)
#
# DEFAULT_THEME decides what a visitor sees before choosing:
#   "system"  follow the device's light / dark setting (the default)
#   "dark"    always start dark
#   "light"   always start light
# Whatever the visitor picks with the top-bar switch is remembered in their
# browser (localStorage key THEME_STORAGE_KEY) and wins over the default.
DEFAULT_THEME = "system"
THEME_STORAGE_KEY = "messmate-theme"

# Every font either theme uses, in one stylesheet request.
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
             "&family=Arima:wght@600;700&family=Hind+Madurai:wght@400;500;600;700&display=swap")

# ── Shared tokens: the same in both themes ────────────────────────────────────
SHARED_TOKENS = OrderedDict([
    # Typography
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
    # Motion
    ("--dur", "180ms"),
    ("--dur-slow", "240ms"),
    ("--ease", "cubic-bezier(0.22, 0.61, 0.36, 1)"),
    # Stacking
    ("--z-topbar", "100"),
    ("--z-float", "50"),
    # Minimum tap target
    ("--tap", "44px"),
    # Legacy light primaries — kept for anything external that references them
    ("--blue-600", "#2E75B6"),
    ("--blue-800", "#1F4E79"),
])

# ── Theme tokens: one value per theme ─────────────────────────────────────────
# Each row is (token, dark value, light value). Keeping both values on one
# line means a token can never exist in one theme and be missing in the other.
_THEME_ROWS = [
    # Surfaces
    ("--bg-900",          "#0f1724",                    "#f6f2e4"),   # rice
    ("--bg-850",          "#0f2027",                    "#f1efdd"),
    ("--bg-800",          "#1a2438",                    "#ebecd4"),
    ("--app-gradient",    "linear-gradient(160deg, var(--bg-900) 0%, var(--bg-800) 50%, var(--bg-850) 100%)",
                          "var(--bg-900)"),
    ("--surface",         "rgba(255, 255, 255, 0.04)",  "#e1e9c9"),   # leaf tint
    ("--surface-hover",   "rgba(255, 255, 255, 0.07)",  "#d6e0b8"),
    ("--surface-active",  "rgba(255, 255, 255, 0.09)",  "#cbd8a8"),
    ("--surface-sunken",  "rgba(15, 23, 36, 0.60)",     "#fffcf2"),
    ("--surface-faint",   "rgba(255, 255, 255, 0.015)", "#ebecd4"),
    ("--surface-deep",    "rgba(0, 0, 0, 0.22)",        "#f1efdd"),
    ("--border",          "rgba(255, 255, 255, 0.08)",  "#c5cfa5"),
    ("--border-strong",   "rgba(255, 255, 255, 0.14)",  "#8a7660"),   # 3.9:1 on rice: control borders
    ("--border-hover",    "rgba(255, 255, 255, 0.24)",  "#5c4834"),
    ("--chrome-bg",       "rgba(15, 23, 36, 0.85)",     "rgba(246, 242, 228, 0.92)"),
    # Text — AA on --surface in both themes
    ("--text-strong",     "#f1f5f9",                    "#1d4620"),   # leaf-deep
    ("--text",            "#e8eef7",                    "#211a12"),   # mustard-seed ink
    ("--text-2",          "#e2e8f0",                    "#2b2219"),
    ("--text-3",          "#cbd5e1",                    "#3a2e22"),
    ("--text-muted",      "#94a3b8",                    "#5c4834"),   # tamarind
    ("--text-faint",      "#8b9ab0",                    "#6b5640"),
    ("--on-accent",       "#ffffff",                    "#f6f2e4"),   # text on an accent fill
    # Brand + accent
    ("--brand-from",      "#60a5fa",                    "#1d4620"),
    ("--brand-to",        "#a78bfa",                    "#2f6b2a"),
    ("--accent",          "#3b82f6",                    "#2f6b2a"),   # banana leaf
    ("--accent-strong",   "#2563eb",                    "#1d4620"),
    ("--accent-2",        "#6366f1",                    "#24561f"),
    ("--accent-ink",      "#93c5fd",                    "#245a20"),
    ("--accent-bg",       "rgba(59, 130, 246, 0.10)",   "#cdeab6"),
    ("--accent-bg-hover", "rgba(59, 130, 246, 0.18)",   "#bfe0a5"),
    ("--accent-border",   "rgba(59, 130, 246, 0.25)",   "#9cc985"),
    ("--accent-border-strong", "rgba(59, 130, 246, 0.5)", "#2f6b2a"),
    ("--accent-gradient", "linear-gradient(135deg, var(--accent), var(--accent-2))",
                          "var(--accent)"),
    ("--brand-gradient",  "linear-gradient(90deg, var(--brand-from), var(--brand-to))",
                          "linear-gradient(90deg, var(--brand-from), var(--brand-to))"),
    # Semantic
    ("--ok",              "#22c55e",                    "#2f6b2a"),
    ("--ok-strong",       "#16a34a",                    "#1d4620"),
    ("--ok-text",         "#6ee7a0",                    "#1d4620"),
    ("--ok-text-2",       "#86efac",                    "#13361a"),
    ("--ok-bg",           "rgba(34, 197, 94, 0.12)",    "#cdeab6"),
    ("--ok-border",       "rgba(34, 197, 94, 0.30)",    "#8fbf78"),
    ("--ok-glow",         "rgba(34, 197, 94, 0.55)",    "rgba(47, 107, 42, 0.45)"),   # the live / serving pulse ring
    ("--warn",            "#fbbf24",                    "#8a5a00"),   # turmeric, darkened to read as text
    ("--warn-text",       "#fcd34d",                    "#5c3f00"),
    ("--warn-bg",         "rgba(251, 146, 60, 0.16)",   "#fbedc4"),
    ("--warn-border",     "rgba(251, 191, 36, 0.40)",   "#e2a320"),
    ("--danger",          "#f87171",                    "#b02a1c"),   # Kashmiri chilli
    ("--danger-strong",   "#ef4444",                    "#b02a1c"),
    ("--danger-deep",     "#dc2626",                    "#8f2016"),
    ("--danger-text",     "#fca5a5",                    "#7d1b10"),
    ("--danger-bg",       "rgba(239, 68, 68, 0.12)",    "#fadcd5"),
    ("--danger-border",   "rgba(239, 68, 68, 0.30)",    "#e8a596"),
    ("--violet-text",     "#c4b5fd",                    "#6e1a3d"),   # kokum
    ("--violet-bg",       "rgba(167, 139, 250, 0.16)",  "#f7dfe8"),
    ("--amber-tag",       "#f59e0b",                    "#5c3f00"),
    ("--amber-tag-bg",    "rgba(245, 158, 11, 0.15)",   "#fbedc4"),
    ("--amber-tag-border", "rgba(245, 158, 11, 0.30)",  "#e2a320"),
    ("--neutral-bg",      "rgba(148, 163, 184, 0.16)",  "rgba(92, 72, 52, 0.12)"),
    ("--skip-deep",       "#475569",                    "#9c8b73"),
    # Typography: Inter in dark; Ilai's Hind Madurai text and Arima headings in light
    ("--font-sans",       "'Inter', -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif",
                          "'Hind Madurai', -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"),
    ("--font-display",    "var(--font-sans)",           "'Arima', Georgia, serif"),
    # Elevation — offset plus soft blur, never a zero-offset halo
    ("--shadow-card",     "0 10px 34px rgba(0, 0, 0, 0.28)",       "none"),
    ("--shadow-raised",   "0 24px 70px rgba(0, 0, 0, 0.45)",       "0 18px 48px rgba(33, 26, 18, 0.16)"),
    ("--shadow-accent",   "0 6px 20px rgba(59, 130, 246, 0.35)",   "none"),
    ("--shadow-ok",       "0 4px 16px rgba(34, 197, 94, 0.15)",    "none"),
    ("--shadow-danger",   "0 4px 16px rgba(239, 68, 68, 0.12)",    "none"),
    ("--shadow-today",    "0 10px 34px rgba(59, 130, 246, 0.18)",  "0 8px 24px rgba(47, 107, 42, 0.18)"),
    # Focus — one ring everywhere. Light: Ilai's solid ink ring with a rice gap.
    ("--focus-ring",      "0 0 0 3px rgba(96, 165, 250, 0.55)",    "0 0 0 2px #f6f2e4, 0 0 0 4px #211a12"),
    # Charts + score bands (read by static/charts.js from the computed style)
    ("--score-red",       "#EF5350",                    "#b02a1c"),
    ("--score-amber",     "#FFB300",                    "#b07a0c"),
    ("--score-green",     "#66BB6A",                    "#2f6b2a"),
    ("--chart-line",      "#60a5fa",                    "#2f6b2a"),
    ("--chart-fill",      "rgba(96, 165, 250, 0.14)",   "rgba(47, 107, 42, 0.14)"),
    ("--chart-grid",      "rgba(148, 163, 184, 0.12)",  "rgba(33, 26, 18, 0.10)"),
    ("--chart-muted",     "rgba(148, 163, 184, 0.35)",  "rgba(92, 72, 52, 0.35)"),
    ("--tooltip-bg",      "rgba(15, 23, 36, 0.95)",     "rgba(255, 253, 246, 0.97)"),
    ("--tooltip-border",  "rgba(255, 255, 255, 0.14)",  "rgba(92, 72, 52, 0.30)"),
    ("--chart-dim-1",     "#8E24AA",                    "#2f6b2a"),   # curry leaf
    ("--chart-dim-2",     "#00897B",                    "#b02a1c"),   # chilli
    ("--chart-dim-3",     "#F4511E",                    "#b07a0c"),   # turmeric
    ("--chart-dim-4",     "#3949AB",                    "#8e2450"),   # tamarind
    ("--chart-dim-5",     "#7CB342",                    "#6b4a2b"),   # kokum
    # Ilai shapes, states and chrome. Each dark value is exactly what the
    # stylesheet used before these tokens existed, so dark never changes.
    ("--shape-btn-lg",    "var(--r-md)",                "999px"),     # full-width primary
    ("--shape-btn",       "var(--r-sm)",                "999px"),     # inline + secondary buttons
    ("--shape-field",     "var(--r-sm)",                "4px"),       # text fields (M3 xs)
    ("--shape-seg",       "var(--r-sm)",                "999px"),     # segmented control
    ("--shape-seg-item",  "6px",                        "999px"),
    ("--shape-alert",     "10px",                       "12px"),      # M3 m
    ("--btn-lift",        "translateY(-1px)",           "none"),
    ("--btn-hover-opacity", "0.9",                      "1"),
    ("--state-hover",     "0",                          "0.08"),      # M3 state layers
    ("--state-press",     "0",                          "0.10"),
    ("--caps",            "uppercase",                  "none"),      # Ilai: no tracked capitals
    ("--caps-track",      "0.06em",                     "0"),
    ("--caps-track-wide", "0.08em",                     "0"),
    # Top bar: the leaf's midrib in light
    ("--topbar-bg",       "var(--chrome-bg)",           "#1d4620"),
    ("--topbar-border",   "1px solid var(--border)",    "3px solid #e2a320"),
    ("--topbar-blur",     "blur(12px)",                 "none"),
    ("--topbar-text",     "var(--text-muted)",          "#e1e9c9"),
    ("--topbar-text-hover", "var(--text-2)",            "#f6f2e4"),
    ("--topbar-hover-bg", "var(--surface-hover)",       "rgba(246, 242, 228, 0.12)"),
    ("--topbar-current-text", "var(--text-strong)",     "#1d4620"),
    ("--topbar-current-bg", "var(--surface)",           "#cdeab6"),
    ("--topbar-current-border", "var(--border)",        "#cdeab6"),
    ("--topbar-brand",    "var(--brand-gradient)",      "linear-gradient(#f6f2e4, #f6f2e4)"),
    ("--topbar-ctrl-bg",  "var(--surface)",             "transparent"),
    ("--topbar-ctrl-border", "var(--border-strong)",    "rgba(246, 242, 228, 0.55)"),
    ("--topbar-ctrl-hover-border", "var(--border-hover)", "#f6f2e4"),
    ("--topbar-btn-text", "var(--text-3)",              "#f6f2e4"),
    ("--topbar-btn-hover-bg", "var(--surface-active)",  "rgba(246, 242, 228, 0.12)"),
    ("--topbar-btn-hover-text", "var(--text-strong)",   "#f6f2e4"),
    ("--topbar-toggle-text", "var(--text-2)",           "#f6f2e4"),
    ("--topbar-toggle-hover-bg", "var(--surface-hover)", "rgba(246, 242, 228, 0.12)"),
    ("--topbar-cta-bg",   "none",                       "#e2a320"),   # dark: .nav-link already overrode the CTA fill
    ("--topbar-cta-text", "var(--text-muted)",         "#211a12"),
    ("--topbar-cta-hover-bg", "var(--surface-hover)",  "#cf9418"),
    ("--topbar-cta-hover-text", "var(--text-2)",       "#211a12"),
    # Logo: the banana-leaf mark replaces the live dot in light
    ("--brand-mark-display", "none",                    "block"),
    ("--live-dot-display", "inline-block",              "none"),
    # Sign-in brand panel: a leaf-deep band in light
    ("--panel-bg",        "var(--surface-deep)",        "#1d4620"),
    ("--panel-border",    "var(--border)",              "#1d4620"),
    ("--panel-text",      "var(--text-2)",              "#f6f2e4"),
    ("--panel-text-muted", "var(--text-muted)",         "#e1e9c9"),
    ("--panel-brand",     "var(--brand-gradient)",      "linear-gradient(#f6f2e4, #f6f2e4)"),
    ("--panel-icon-bg",   "var(--accent-bg)",           "#2f6b2a"),
    ("--panel-icon-border", "var(--accent-border)",     "#2f6b2a"),
    ("--panel-link",      "var(--accent-ink)",          "#e2a320"),
    ("--panel-link-hover", "var(--text-strong)",       "#f6f2e4"),
]

THEMES = OrderedDict([
    ("dark",  {"label": "Dark",  "tokens": OrderedDict((n, d) for n, d, _ in _THEME_ROWS)}),
    ("light", {"label": "Light", "tokens": OrderedDict((n, l) for n, _, l in _THEME_ROWS)}),
])

# Kept for anything that reads the old name: the shared tokens plus the
# dark values.
DESIGN_TOKENS = OrderedDict(list(SHARED_TOKENS.items()) + list(THEMES["dark"]["tokens"].items()))


def _block(selector, tokens, scheme, indent=""):
    lines = [f"{indent}{selector} {{", f"{indent}    color-scheme: {scheme};"]
    lines += [f"{indent}    {name}: {value};" for name, value in tokens.items()]
    lines.append(f"{indent}}}")
    return lines


def tokens_css():
    """Every token as CSS: the shared values, the starting theme on :root,
    the other theme under [data-theme], and, when DEFAULT_THEME is "system",
    a prefers-color-scheme block so the device setting applies until the
    visitor picks one."""
    base = "light" if DEFAULT_THEME == "light" else "dark"
    other = "dark" if base == "light" else "light"
    lines = ["/* Generated from ui_config.py (SHARED_TOKENS, THEMES) — edit that, not this. */"]
    lines += _block(":root", SHARED_TOKENS, base)[0:1] + [
        f"    {n}: {v};" for n, v in SHARED_TOKENS.items()] + ["}"]
    lines += _block(":root", THEMES[base]["tokens"], base)
    lines += _block(f':root[data-theme="{other}"]', THEMES[other]["tokens"], other)
    if DEFAULT_THEME == "system":
        lines.append("@media (prefers-color-scheme: light) {")
        lines += _block(':root:not([data-theme="dark"])', THEMES["light"]["tokens"], "light", "    ")
        lines.append("}")
    return "\n".join(lines) + "\n"


def as_dict():
    """What the browser needs: identity and thresholds (not the tokens — CSS
    already has those, and charts.js reads them from the computed style)."""
    return {"app": APP, "scoreBands": SCORE_BANDS, "tapBands": TAP_BANDS,
            "theme": {"default": DEFAULT_THEME, "storageKey": THEME_STORAGE_KEY}}


class _UI:
    """The `ui` Jinja global."""
    app = APP
    score_bands = SCORE_BANDS
    tap_bands = TAP_BANDS
    score_band = staticmethod(score_band)
    score_class = staticmethod(score_class)
    tap_band = staticmethod(tap_band)
    tap_class = staticmethod(tap_class)
    fonts_url = FONTS_URL
    default_theme = DEFAULT_THEME
    theme_storage_key = THEME_STORAGE_KEY

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
