# Deprecated storage

Tables, columns and JSON keys the redesigned UI stops reading. They stay in place, unchanged, as a frozen record (DESIGN.md 2.2.4). Removing anything listed here is a separate, later decision and is never part of the redesign.

| Item | Replaced by | Since phase | Notes |
|---|---|---|---|
| `app_state.global_settings` → `rate_card`, `role_catalog` | Tables `rate_card`, `rate_card_rate`, `level`, `role_category`, `role` | 5 | Read by nothing once migration 0003 has run; the app never writes these keys again. `business_units` in the same blob is still live. |

Candidates once their phases land: `app_state.working_data` (Phase 6); payload keys `approvals`, `attachments`, `funding`, `releases`, `pnl_roles`, `export_path` (already unused by the UI).
