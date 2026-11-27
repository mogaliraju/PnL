# Deprecated storage

Tables, columns and JSON keys the redesigned UI stops reading. They stay in place, unchanged, as a frozen record (DESIGN.md 2.2.4). Removing anything listed here is a separate, later decision and is never part of the redesign.

| Item | Replaced by | Since phase | Notes |
|---|---|---|---|
| `app_state.global_settings` → `rate_card`, `role_catalog` | Tables `rate_card`, `rate_card_rate`, `level`, `role_category`, `role` | 5 | Read by nothing once migration 0003 has run; the app never writes these keys again. `business_units` in the same blob is still live. |

| Legacy editor, All Projects, Dashboard, Rate Card, Role Catalog, Export Settings, Open/Compare/Users/Change-password modals in `templates/index.html` and their code in `static/js/app.js` | `workspace.html`/`workspace.js`, `projects.js`, `dashboard.js`, `rates.js`, `users.html`, the account-menu dialog | 2–8 | No route renders the legacy editor any more and the home page hides the old panes. `index.html` + `app.js` stay because Order Bookings and Funnel Report (behind `FEATURE_BOOKINGS_FUNNEL`) still use them. Remove them together with those modules if that decision is made. |
| `/api/dashboard`, `/api/compare`, `/api/settings` | `/api/projects?summary=true`, `/api/projects/<id>/compare`, `/api/rate-cards`, `/api/roles` | 5–7 | Kept for their tests and any old client. |

Candidates once their phases land: `app_state.working_data` (Phase 6); payload keys `approvals`, `attachments`, `funding`, `releases`, `pnl_roles`, `export_path` (already unused by the UI).
