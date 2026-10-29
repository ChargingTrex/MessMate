<!-- converted from MessMate_PRD.docx -->

MessMate
College Food Review & Feedback Platform
Product Requirements Document (PRD)
Version 1.0  |  Prototype Release  |  March 2026
| Field | Details |
| --- | --- |
| Document Title | MessMate — PRD v1.0 |
| Author | Solo Developer (Student) |
| Status | Draft — For VC Presentation |
| Target Institution | College Campus (Chennai, Tamil Nadu) |
| Prototype Scope | Lunch Feedback — Phase 1 |
| Last Updated | March 2026 |

# 1.  Problem Statement
Currently, there is no structured, data-driven mechanism for students to provide feedback on mess food quality. Complaints are informal, untracked, and rarely acted upon by administration. Mess caterers lack objective performance data, and institutional decision-makers — Deans, the Chancellor, and Vice Chancellor — have no visibility into day-to-day food quality trends.

This gap leads to:
- Repeated quality issues going unaddressed due to lack of evidence
- Student frustration with no actionable feedback channel
- Caterer accountability remaining entirely informal
- Administration unable to make data-driven mess management decisions

# 2.  Project Goals
## 2.1  Primary Goals
- Provide students a fast, mobile-friendly (QR-accessible) way to rate and review daily mess food
- Generate structured, aggregated feedback data for institutional stakeholders
- Give caterers and administration a live dashboard to monitor food quality trends
- Create a channel for students to suggest new dishes to the mess menu

## 2.2  Prototype Goals (Phase 1)
- Demonstrate the core feedback loop: student rates → data lands in Google Sheets → dashboard reflects it
- Cover lunch meal only (widest audience across the college)
- Deployable via QR code, accessible on any smartphone browser
- Presentable to Vice Chancellor with seeded data to show full product vision

# 3.  Scope
| Feature | In Scope (Prototype) | Future Phase |
| --- | --- | --- |
| Overall meal rating (emoji) | Yes |  |
| Per-item ratings — standardised menu | Yes |  |
| Rice dropdown (Curry / Rasam / Both) | Yes |  |
| Text review (optional, 150 chars) | Yes |  |
| Anonymous dish suggestion box | Yes |  |
| Admin dashboard — averages & trends | Yes |  |
| Suggested dishes list on dashboard | Yes |  |
| Breakfast & Dinner modules |  | Phase 2 |
| User authentication (college email/roll no.) |  | Phase 2 |
| Time-locked submission window |  | Phase 2 |
| Admin menu management UI |  | Phase 2 |
| Weekly summary / shareable scorecard |  | Phase 3 |
| Suggestion acknowledgement workflow |  | Phase 3 |

# 4.  User Personas
## 4.1  Student (Primary User)
- Goal: Rate today's lunch quickly, at the mess table, from their phone
- Context: Scans QR code on mess notice board; fills form in under 60 seconds
- Audience: All college students (lunch), hostel students (future: breakfast/dinner)
- Device: Mobile phone browser

## 4.2  Mess Caterer
- Goal: See daily ratings and per-dish feedback to understand what students like/dislike
- Access: Dashboard URL (read-only)
- Key metric: Daily average score, item-level scores

## 4.3  Dean / Chancellor / Vice Chancellor
- Goal: Monitor overall food quality trends; use data for caterer accountability
- Access: Dashboard URL (read-only)
- Key metric: Weekly trend, response volume, suggested dishes

# 5.  Functional Requirements
## 5.1  Student Feedback Form
### Section 1 — Overall Rating (Required)
Five emoji buttons displayed prominently. Student taps one to submit overall meal quality.

| Emoji | Label | Score Stored |
| --- | --- | --- |
| 😡 | Terrible | 1 |
| 😕 | Bad | 2 |
| 😐 | Okay | 3 |
| 🙂 | Good | 4 |
| 😄 | Excellent | 5 |

### Section 2 — Per-Item Ratings (Optional)
Standardised menu items displayed as tappable cards. Each item has an emoji rating (1–5 scale).

| Menu Item | Behaviour |
| --- | --- |
| 🍚 Rice | Dropdown: Curry / Rasam / Both. Rate appears per selection. Up to 2 ratings. |
| 🫓 Chapati | Emoji rating (1–5) |
| 🫓 Chapati + Gravy / Sabzi | Emoji rating (1–5) |
| 🥬 Poriyal | Emoji rating (1–5) |
| 🍮 Sweet / Fruits | Emoji rating (1–5) |
| 🥗 Salad | Emoji rating (1–5) |
| 🥛 Curd | Emoji rating (1–5) |
| 🫓 Papad | Emoji rating (1–5) |
| 🫙 Pickle / Thogayal | Emoji rating (1–5) |

### Section 3 — Text Review (Optional)
- Free text input, maximum 150 characters
- Placeholder: 'Any comments about today's lunch?'

### Section 4 — Suggest a Dish (Optional)
- Free text input for dish name / description
- Anonymous — no user identity stored
- Feeds directly to dashboard suggestion list

# 6.  Dashboard Requirements
The dashboard is a separate, read-only page accessible to the caterer, Deans, Chancellor, and Vice Chancellor. It auto-refreshes data from Google Sheets.

| Widget | Description | Data Source |
| --- | --- | --- |
| Today's Average Score | Large number, colour-coded red/yellow/green | Google Sheets — today's rows |
| Response Count | Number of submissions today displayed alongside average | Google Sheets — count of rows |
| 7-Day Trend Line | Line chart of daily average scores over past 7 days | Google Sheets — aggregated by date |
| Per-Item Average Scores | Horizontal bar chart — one bar per menu item | Google Sheets — per-column averages |
| Suggested Dishes List | Scrollable list of all dish suggestions, timestamped | Google Sheets — Suggestion column |

# 7.  Non-Functional Requirements
| Requirement | Target |
| --- | --- |
| Load time (form page) | < 2 seconds on a 4G connection |
| Mobile compatibility | Works on all modern smartphone browsers (Chrome, Safari) |
| Form completion time | < 60 seconds for full form |
| Data visibility lag | Dashboard reflects new submission within 30 seconds |
| Uptime (prototype) | Best-effort; free-tier hosting acceptable for demo |
| Spam protection (prototype) | 1 submission per IP per day via server-side check |
| Anonymity | No student identity data stored; suggestions anonymous |
| Accessibility | Tappable targets min 44x44px; readable font sizes |

# 8.  Success Metrics
| Metric | Target (Demo) | Target (Post-Launch) |
| --- | --- | --- |
| Form submission rate | 50–80 seeded demo entries | > 30% of lunch headcount daily |
| Dashboard load without error | 100% during VC demo | 99% uptime |
| Avg. form completion time | < 60 seconds | < 45 seconds |
| Stakeholder comprehension | VC understands product in < 2 min | — |
| Dish suggestions received | 10+ in demo data | 5+ per week |

# 9.  Constraints & Assumptions
## 9.1  Constraints
- Solo developer — scope kept tight for prototype delivery
- No institutional IT support or server infrastructure available
- No formal student committee backing yet (elections pending)
- Free-tier hosting and Google Sheets API limits apply

## 9.2  Assumptions
- Students have smartphone access at the mess and can scan a QR code
- The daily lunch menu follows the standardised 10-item structure defined in Section 5
- Google Sheets API quota is sufficient for prototype-level traffic
- Caterer and administration will be provided the dashboard URL directly by the developer

# 10.  Out of Scope (Phase 1)
- Breakfast and dinner meal feedback
- User login or authentication
- Admin panel for menu management
- Push notifications or email digests
- Native mobile app
- Data export or report generation from the dashboard