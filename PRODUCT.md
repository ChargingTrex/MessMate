# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three audiences, and the user has confirmed that **no one of them outranks the others**: each surface is designed for its own visitor.

- **Students** (anonymous, no login). On a phone, at or near the mess, before or just after a meal. Job: see what is being served today and say in one tap whether it was good, bad, or skipped; occasionally rate dish by dish or leave a suggestion. Planned reach (confirmed): a QR code at the mess counter and a shared link (WhatsApp group / notice). Not yet in real use.
- **Food committee members** (signed in, attributed). Job: file a five-dimension review (taste, quality, variety, hygiene, menu) and see the committee's own trend. Reviews are not anonymous.
- **Admins, deans and the Vice-Chancellor** (admin password or dashboard token). Job: read today's numbers from all three feedback layers, publish the weekly menu, manage the committee roster, and decide what needs attention.

## Product Purpose

A college mess food review app for Sai University (SaiU). Students give fast, anonymous feedback on mess food; the committee adds an attributed expert review; management sees all three on live dashboards and acts on them. Success, for now, is a convincing pilot: management approves it and it goes live at the mess.

## Positioning

Three deliberately separate feedback layers that are **never averaged together**: a tally of one-tap reactions, a mean of 1–5 per-dish scores, and a five-dimension committee review measure different things from different populations, and the dashboards keep them in separate cards. Everything runs on a Google Sheet that mess staff can also edit directly, so the spreadsheet and the admin UI are equally valid editors of the same rows.

## Operating Context

- **Status (confirmed): prototype / pilot proposal.** Not launched; the user needs to demonstrate it to university management and then implement it. No students, committee members or administrators use it for real today.
- Data store is a Google Sheet (tabs: `responses`, `daily_summary`, `committee_members`, `committee_reviews`, `menu`, `meal_ratings`) read and written through a service account. Menu rows are typed either in the sheet or in the admin weekly editor.
- Intended deployment: Render.com free tier via gunicorn; local dev with `python app.py`. Students on a campus network may share one public IP (hostel NAT), which matters for anything keyed on IP.
- Meal windows shown to students: breakfast 7:30–9:30 am, lunch 12:00–2:30 pm, dinner 7:30–9:30 pm. Display-only; nothing enforces them.
- Rhythm: the menu is planned Monday–Sunday; the committee reviews daily; management reads the overview after sign-in.

## Capabilities and Constraints

- Student home (`/home`): today's menu with day switching across the week, one tap per meal (good / bad / skip) plus an optional suggestion. Dish form (`/`): per-dish 1–5 emoji ratings, a review, a suggestion; rate-limited to one submission per IP per day.
- Committee module: login, forced password change, review form, thank-you page, committee dashboard.
- Admin console: overview with attention list, weekly menu editor (fill from template, copy last week, save a day or all seven), member management with one-time credentials, two dashboards.
- Student anonymity is a hard constraint: no student identity is stored anywhere.
- A day with no published menu shows "Menu not published yet". The built-in weekly template is an editor convenience only and is never shown to students; a fabricated menu that happens to be wrong is worse than an honest blank.
- Sheet header names and column positions are load-bearing (row lookups scan column A of `menu` and `committee_members`).
- Ids, `data-*` attributes and the class names listed in each template's header comment are test API for the Robot and Python suites.
- Score bands (red < 2.5, amber ≤ 3.5, green above; tap share 40 % / 70 %) and all design tokens are declared once in `ui_config.py`.
- **Undecided:** real launch date, final hosting, whether the IP-based rate limit survives a campus NAT, and whether an email allowlist (`COMMITTEE_EMAIL_DOMAIN`) is enforced in production.

## Brand Commitments

- Name **MessMate**, wordmark **MESSMATE**, tagline "College mess food review", institution SaiU. Favicon at `static/favicon.svg`.
- Binding visual constraint volunteered in the changelog: the student home page keeps its own header (clock, gradient Committee button) and its own card, chip, tab and reaction-button treatments by request, while reading the shared tokens. Recorded here as stated; not expanded.
- Voice in existing copy: plain, direct, slightly warm ("Still completely anonymous.").

## Evidence on Hand

- Demo data only: `seed_demo.py` / `seed_data.py` generate sample ratings, reviews and a menu; the current sheet holds menu rows for 16 Sep – 7 Oct 2026 only.
- A WCAG 2.2 findings report, `accessibility-audit.md` (5 Oct 2026, 7 pages, informative score 70/100, does not yet conform to AA).
- No real usage numbers, testimonials, management quotes, photos of the mess or its food, or approval from the university. Future work must not invent any of these.

## Product Principles

1. Three layers, three cards, never one average.
2. Honest absence beats a plausible guess: show "not published yet", "--", or a grey empty state rather than a fabricated value.
3. A student's feedback costs one tap and no identity.
4. The spreadsheet is a first-class editor; the UI never assumes it is the only writer.
5. Every number that carries colour carries meaning, and the thresholds live in one place.

## Accessibility & Inclusion

An audit against WCAG 2.2 Level A + AA exists and currently reports seven failing criteria. Whether AA conformance is a requirement for the pilot has not been confirmed with the user; treat the audit as the working target until it is.
