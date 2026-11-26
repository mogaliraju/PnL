# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Redesign and data safety (read first)

Before any UI, data model or PnL calculation change, read design/DESIGN.md. Section 2 (data safety) overrides everything else.

- Never run SQL containing DROP, TRUNCATE or DELETE. Never run migrations against the production DATABASE_URL. Ask before any command that writes to a database.
- Develop against the restored local copy `postgresql://localhost/pnl_prod_copy_20261127_020914`, never production. Backups and the figure baseline are in `~/pnl-backups/prod_20261127_020914/`. See design/BACKUP_AND_ROLLBACK.md.
- Migrations are additive only (new tables, nullable or defaulted columns, indexes). Never rename, retype or overwrite existing columns or values.
- Run `scripts/verify_data.py` at the end of every phase. It must print `VERIFY PASSED` before merge.
- Work happens on branch `redesign-2026`, one phase per PR, with approval before each phase. The rollback point is tag `pre-redesign-2026`.
- design/CURRENT_SCHEMA.md lists the existing code paths that delete or overwrite data. Don't add new ones.

## What this is

Flask app for pre-sales Profit & Loss estimation (AutomatonsX / Cloud4C). Users build resource plans per proposal, apply margins, and export a formatted Excel workbook. It also tracks a sales **funnel** and **order bookings**, both with Excel import. Frontend is a single-page shell (`templates/index.html`) driven by one large vanilla-JS file (`static/js/app.js`, Bootstrap 5 + Tom Select).

## Commands

Requires Python 3.10+ (the code uses `str | None` hints). The local virtualenv is `.venv` (Python 3.12). System `python3` here is 3.9 and won't run the app.

```bash
/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python app.py                       # dev server on http://localhost:5000 (debug)
gunicorn app:app                              # production entry (Render)

.venv/bin/python -m pytest                    # all tests (pytest.ini: testpaths=tests, -v --tb=short)
.venv/bin/python -m pytest tests/test_pnl_suite.py
.venv/bin/python -m pytest tests/test_pnl_suite.py::TestAuthentication::test_login_page_loads

# schema changes: numbered additive SQL in pnl/migrations/, applied by the runner (refuses non-local DBs)
.venv/bin/python scripts/migrate.py --database-url postgresql://localhost/pnl_dev [--dry-run]
PNL_TEST_PG_URL=postgresql://localhost/pnl_migtest .venv/bin/python -m pytest tests/test_projects_list.py   # also dry-runs migrations on Postgres

# data safety scripts (read-only; take --sqlite PATH or --database-url / $DATABASE_URL)
.venv/bin/python scripts/count_rows.py
.venv/bin/python scripts/verify_data.py --baseline-figures ~/pnl-backups/baseline_YYYYMMDD/baseline_figures.json
```

Tests are `unittest.TestCase` classes run via pytest. Each test creates an isolated `DATA_DIR` under `test-runtime/` (gitignored) and **reloads `pnl.*` modules** (`MODULES_TO_RELOAD` lists in the test files) because config and storage read env vars at import time. If you add a new `pnl` module that tests touch, add it to that list.

Bootstrapping a first admin on an empty DB: set `PNL_BOOTSTRAP_ADMIN_PASSWORD` (optionally `PNL_BOOTSTRAP_ADMIN_USERNAME`, `PNL_BOOTSTRAP_ADMIN_NAME`) before starting. No default credentials are created otherwise.

## Architecture

### UI shell (redesign Phase 2)

- `templates/base.html` is the AX shell: navy rail, top bar with global search, account menu. Pages extend it. `templates/index.html` still holds the legacy screens as Bootstrap tab panes. On home pages the rail drives them through hidden tab links (`static/js/ax-shell.js`, `axShell.show(route)`), so `app.js` loaders keep working. In the editor (`/projects/<id>`, `/projects/new`) the tabs are visible. The old `/project-editor/...` URLs redirect.
- Colours, type and sizes come from `design/figma-tokens.json`. `scripts/build_tokens.py` generates `static/css/ax-tokens.css`; never edit that file by hand, and a test fails if it's stale. `static/css/ax.css` holds the shell and components and also reskins Bootstrap for screens not yet rebuilt. `style.css` is legacy.
- Schema changes go in `pnl/migrations/NNNN_*.sql`. They must be additive: `pnl/migrate.py` rejects DROP, DELETE, UPDATE, TRUNCATE, RENAME and type changes, runs in one transaction, and rolls back if any row count drops. `storage._features()` checks whether a migration has been applied, so code deployed before its migration degrades gracefully (`FeatureUnavailable` -> HTTP 503). The SQLite test path mirrors simple portable additions in `_create_schema`. New Postgres-only tables (Phase 5+) don't.
- Projects are archived (`archived_at`), never deleted. Saved versions are never deleted. `DELETE /api/projects/<id>` archives, and the version DELETE returns 405.
- Projects list: `static/js/projects.js` (replaces the legacy renderer in `app.js` by reassigning `window.loadAllProjects`). Dialogs, toasts and popovers come from `static/js/ax-ui.js` (`axUI.dialog/toast/popover`); don't use native `confirm`/`prompt` in new code. Per-user list settings: `/api/prefs/projects_list` -> `user_pref` table.
- Components are Jinja macros in `templates/components/ui.html` (`{% import "components/ui.html" as ui %}`). `/design/components` shows them all. Icons come from `icon(name)` in `pnl/ui.py`. Margin health thresholds live in `pnl/config.py` (`AX_MARGIN_GOOD`, `AX_MARGIN_WARN`), never in templates or JS.


- `app.py` → `pnl.create_app()` (app factory in `pnl/__init__.py`), which registers blueprints from `pnl/routes/` (`auth`, `main`, `projects`, `export`, `import_excel`, `funnel`, `bookings`). A global error handler forces JSON error bodies for any `/api/*` path.
- `pnl/config.py` resolves all paths from `DATA_DIR` (defaults to repo root) and enforces `SECRET_KEY` when `PNL_ENV=production`. It runs side effects at import (creates dirs).
- `pnl/utils/storage.py` is the **only** persistence layer, and every route goes through it:
  - Backend is **SQLite** (`$DATA_DIR/pnl.sqlite3`) by default, or **Postgres** when `DATABASE_URL` starts with `postgres://`/`postgresql://` (psycopg). SQL is written with `?` placeholders and `_sql()` rewrites them to `%s` for Postgres, so new queries must go through `_execute()`/`_sql()` and stay portable across both dialects.
  - Schema is created lazily by `_ensure_db()`. On a fresh DB it also migrates legacy JSON files (`data.json`, `settings.json`, `users.json`, `projects/`, `versions/`). Tables: `app_state` (key/JSON blobs: `working_data`, `global_settings`, custom fields, column labels), `users`, `projects`, `project_versions`, `funnel_entries`, `order_bookings`.
  - Projects are stored as whole JSON payloads (`_meta`, `project`, `resources`, `rate_card`, `one_time_costs`, margins, …). Global settings (`rate_card`, `role_catalog`, `business_units`) are injected into each project on load via `merge_settings()`, so editing the global rate card affects every project. `save_working_data()` also writes those keys back to global settings.
  - Every project save creates a version snapshot (`project_versions`). The Compare feature diffs two snapshots.
- `pnl/engine.py` is the only place that computes costs, prices and margins: `calculate(snapshot, mode) -> PnLResult`, Decimal maths, modes `legacy` and `v2` (DESIGN.md section 7). `pnl/services/pnl_service.py` is a thin wrapper (`compute_costs`, `legacy_version_revenue`, `compare_versions`) that runs the engine in legacy mode and returns the old dict shape for existing callers. `pnl/services/excel_service.py` builds the export workbook (`build_workbook`) in the Benline PnL template layout.
- `pnl/routes/import_excel.py`, `funnel.py` and `bookings.py` each have their own fuzzy header-matching parsers for importing user spreadsheets.

### Cost model (the README's formula is out of date)

Every existing project is `legacy` mode. A snapshot without `calc_mode` is legacy, and legacy must reproduce the pre-redesign numbers exactly. `tests/test_engine.py` checks this against 10 anonymised production fixtures, and `scripts/verify_data.py` checks every production project and version. `v2` (add-ons with an Apply margin / Pass through treatment, discount taken off list price, lever limits) is described in DESIGN.md 7.2. Legacy rules:

- Resource cost = `hours × rate`, where the rate comes from the rate card entry matching `level`, using `rates[group]` (or the legacy flat `rate` field).
- `one_time_costs` items are added to the input cost, **except** non-margin items (`exclude_from_margin: true` or `category == 'license'`), which are passed through at cost.
- Margins: `cloud4c_margin + ax_margin` = combined margin, each clamped to [0, 0.99]. Legacy projects that only have `target_margin` treat it as the Cloud4C margin with AX = 0 (`resolve_margin_inputs`).
- `margin_basis_sell_cost = input_cost / (1 − combined_margin)`. Then `sell_cost = margin_basis_sell_cost + non_margin_cost`.

All server-side callers (`storage.py` list and version summaries, `routes/main.py` dashboard, `routes/export.py`, compare) go through the engine. **The live summary in `static/js/app.js` still has its own copy** (around `_isNonMarginCost`) until the Phase 6 workspace replaces it with engine output from the API. Until then, legacy rule changes must be mirrored there, and nothing should be added to it.

## Deployment

- **Render** (`render.yaml`): `gunicorn app:app`, with Postgres via the `DATABASE_URL` set in the dashboard and `DATA_DIR=/tmp`. `seed_data.py` restores `data_backup/*.json` into an empty DB and always exits 0. It is currently **not** part of `startCommand`.
- **PythonAnywhere**: `wsgi.py` hard-codes the path and `DATA_DIR`. The USD→INR rate is fetched client-side because the free tier blocks outbound HTTP.
- DB migration helpers: `scripts/migrate_sqlite_to_postgres.py` and `migrate_postgres_to_sqlite.py`.
- Windows launch scripts: `start.bat`, `setup_and_start.ps1`, `install_startup.bat`.
