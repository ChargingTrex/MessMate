# Implementation Plan: Ticker Banner, Home UI Elements, Dummy Menu & Day-Wise Selector

Bring the modern aesthetics and interactive features of [mess-schedular.vercel.app](https://mess-schedular.vercel.app) to MessMate, along with complete 7-day dummy menu data and day-wise menu navigation.

## User Review Required

> [!NOTE]
> All existing Robot Framework and E2E test selectors (`.meal-card[data-meal="..."]`, `.rate-btn[data-rating="..."]`, `id="menu-..."`, `href="/"`) are preserved, ensuring all existing tests pass 100%.

## Proposed Changes

### 1. Data & Seeding Layer

#### [MODIFY] [sheets.py](file:///Users/fi-it/Documents/projects/MessMate/sheets.py)
- In `get_menu_for_date()`: ensure safe fallback for dates and day-of-week indexing if a sheet row is blank.
- Provide built-in weekly template defaults if Google Sheets is disconnected or empty.

#### [MODIFY] [seed_data.py](file:///Users/fi-it/Documents/projects/MessMate/seed_data.py)
- Add menu seeding function `seed_weekly_menu()` to populate 7+ days of realistic South Indian / Indian mess menu items (Idli, Medu Vada, Poori Masala, Veg Biryani, Chapati, Paneer Butter Masala, Sambar, Rasam, etc.).

---

### 2. Backend Routing

#### [MODIFY] [app.py](file:///Users/fi-it/Documents/projects/MessMate/app.py)
- Update `/home`:
  - Fetch `week = sheets.get_menu_week()` (7-day schedule).
  - Accept optional `date` query parameter (`?date=YYYY-MM-DD`, defaulting to today).
  - Pass `week` and JSON-serialized `week_menu_json` to `home.html` for instantaneous client-side day switching.

---

### 3. Frontend Templates & Components

#### [MODIFY] [templates/home.html](file:///Users/fi-it/Documents/projects/MessMate/templates/home.html)
- **Modern Header Bar**:
  - Live dot indicator (`.dot`), brand logo (`MESSMATE`), and digital live clock (`#currentTime`).
  - Quick action links (Detailed Review `/`, Food Committee `/committee`).
- **Right-to-Left Moving Ticker Banner** (`.ticker-section`):
  - Continuous marquee showing live meal serving status, today's dishes, and student tips.
  - Left and right gradient fade masks; pauses on hover.
- **Day-Wise Option / Week Selector Strip** (`.day-selector-section`):
  - Interactive day tabs for the current week: `[ Mon 21 Sep (Today) ]  [ Tue 22 Sep ]  [ Wed 23 Sep ] ... [ Sun 27 Sep ]`.
  - Instant client-side switching between days with clear visual indicator.
- **Meal Filter Pills**:
  - Quick buttons (`All`, `Breakfast`, `Lunch`, `Dinner`) to isolate or jump to any meal.
- **Spotlight & Community Feedback Widget** (`.specials-container`):
  - Left: "Today's Highlights & Active Meal" card with `🟢 SERVING NOW` badge.
  - Right: Community satisfaction progress bars (Good %, Bad %, Skip %) inspired by mess-schedular.
- **Enhanced Meal Cards**:
  - Auto-detected active meal highlight (`.active-meal`).
  - Dishes styled as modern badge chips.
  - Floating scroll-to-top button (`#scrollTopBtn`).

---

### 4. Styling & JavaScript

#### [MODIFY] [static/style.css](file:///Users/fi-it/Documents/projects/MessMate/static/style.css)
- Ticker banner marquee animation and container masks.
- Day-wise selector tabs and active status badges.
- Community feedback percentage bars (`.result-bar`, `.result-fill.good`, `.result-fill.bad`, `.result-fill.skip`).
- Active meal glowing pulse effects and responsive layouts.

#### [MODIFY] [static/home.js](file:///Users/fi-it/Documents/projects/MessMate/static/home.js)
- Real-time digital clock updater (`#currentTime`).
- Instant day-wise menu switcher using embedded weekly schedule data.
- Active meal detector (`Breakfast` 07:30–09:30, `Lunch` 12:30–14:30, `Dinner` 19:30–21:30).
- Meal filter buttons handler.
- Scroll-to-top smooth scroll logic.

## Verification Plan

### Automated Tests
Run smoke and E2E test suites to guarantee zero regression:
```bash
./venv/bin/python test/test_smoke.py
./venv/bin/python test/test_e2e_home.py
```

### Manual Verification
1. Open `http://127.0.0.1:5000/home`:
   - Verify right-to-left moving ticker banner is animated smoothly and pauses on hover.
   - Verify day-wise tabs allow switching between Monday through Sunday menus smoothly.
   - Verify dummy menu dishes are displayed for all 7 days.
   - Verify live clock updates every second.
   - Verify one-tap ratings (`Good`, `Bad`, `Skip`) function properly on today's meals.
   - Verify mobile responsiveness.
