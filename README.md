# PnL Application

A web-based Profit & Loss estimation tool for project proposals. Built with Flask and Bootstrap 5, it lets you build resource plans, compute costs with configurable margins, and export formatted Excel workbooks in the AutomatonsX Benline PnL format.

---

## Features

- **All Projects Dashboard** — tabular view of all saved proposals with key metrics (total cost, sell cost, margin). Click any row to open that project.
- **Project Tab** — merged project info and resources in one page. Three-column summary (company details, proposal metadata, live cost summary). Editable gross margin % and USD→INR override.
- **Rate Card** — manage level-based USD rates with a live INR column. Inline exchange rate input at the top of the table; auto-fetched from open.er-api.com on page load.
- **Role Catalog** — define role groups (e.g. Data Engineering, DevOps) and their associated roles. Drives the resource allocation dropdowns.
- **Export Settings** — configure project-level export metadata (contract type, funding approvals, etc.) before generating the Excel workbook.
- **Excel Export** — one-click export to a formatted `.xlsx` file matching the Benline PnL template.
- **Version Snapshots** — every save creates a timestamped snapshot. Compare any two versions via the Compare modal.
- **Session Auth** — username/password login backed by `users.json` with werkzeug-hashed passwords.

---

## Architecture

```
PnL Application/
├── app.py                     # Entry point (thin wrapper)
├── pnl/
│   ├── __init__.py            # App factory (create_app)
│   ├── config.py              # Centralized path constants
│   ├── routes/
│   │   ├── auth.py            # /login /logout
│   │   ├── main.py            # / /api/data /api/settings /api/exchange-rate
│   │   ├── projects.py        # /api/projects CRUD + versions + compare
│   │   └── export.py          # /api/export (Excel generation)
│   ├── services/
│   │   ├── pnl_service.py     # compute_costs(), compare_versions()
│   │   └── excel_service.py   # build_workbook()
│   └── utils/
│       ├── auth.py            # login_required decorator
│       ├── storage.py         # load/save data, settings, users; merge_settings()
│       ├── validators.py      # validate_payload()
│       └── logger.py          # get_logger()
├── templates/
│   └── index.html             # Single-page app shell
├── static/
│   └── js/
│       └── app.js             # All frontend logic
└── data/
    ├── data.json              # Active session state
    ├── settings.json          # Global rate card + role catalog
    ├── users.json             # User accounts (hashed passwords)
    ├── projects/              # Saved project files (<pid>.json)
    └── versions/              # Version snapshots (<pid>/<vid>.json)
```

---

## Running Locally

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
git clone <repo-url>
cd "PnL Application"
pip install -r requirements.txt
python app.py
```

The app runs at `http://localhost:5000`.

### Default Login

| Username | Password |
|----------|----------|
| admin    | admin123 |

> Change this immediately in production by updating `data/users.json` via the Admin panel.

---

## Deployment (PythonAnywhere)

1. Upload all files to your PythonAnywhere account (e.g. via the Files tab or API).
2. In the **Web** tab, set:
   - **Source code**: `/home/<username>/PnL Application`
   - **WSGI file**: point to `app.py` (or configure manually — see below)
3. In the WSGI configuration file, add:
   ```python
   import sys
   sys.path.insert(0, '/home/<username>/PnL Application')
   from app import app as application
   ```
4. Install dependencies in a Bash console:
   ```bash
   pip install flask openpyxl werkzeug requests
   ```
5. Click **Reload** in the Web tab.

> **Note:** PythonAnywhere free tier blocks outbound HTTP from the server. The USD→INR exchange rate is therefore fetched **client-side** (browser → open.er-api.com) rather than server-side.

---

## Key Concepts

### Cost Calculation

```
Input Cost  = sum of (hours × daily_rate / 8) for all resources
Sell Cost   = Input Cost / (1 - Gross Margin %)
Gross Profit = Sell Cost - Input Cost
```

The default gross margin is **40%**, editable per project via the pencil button in the Cost Summary panel.

### Global Settings

`settings.json` holds the master **Rate Card** (level → USD rate) and **Role Catalog** (group → roles list). These are injected into every project on load via `merge_settings()`, so changes to the global catalog propagate to all future project opens.

### Version Comparison

Every project save creates a snapshot under `data/versions/<pid>/`. The Compare modal lets you pick any two snapshots (or the current project file) and shows a side-by-side diff of costs and resource counts.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects (`?summary=true` includes costs) |
| POST | `/api/projects` | Save new project |
| GET | `/api/projects/<pid>` | Load project |
| DELETE | `/api/projects/<pid>` | Delete project |
| POST | `/api/projects/<pid>/rename` | Rename project |
| GET | `/api/projects/<pid>/versions` | List version snapshots |
| POST | `/api/compare` | Compare two versions |
| POST | `/api/export` | Generate and download Excel file |
| GET | `/api/data` | Get current session data |
| POST | `/api/data` | Save current session data |
| POST | `/api/settings` | Update global settings |
| GET | `/api/exchange-rate` | Get cached USD→INR rate (server-side) |
| GET | `/login` | Login page |
| POST | `/login` | Authenticate |
| GET | `/logout` | Log out |

---

## Tech Stack

- **Backend**: Flask, openpyxl, werkzeug
- **Frontend**: Bootstrap 5, Tom Select
- **Storage**: JSON files (no database required)
- **Auth**: Session-based with hashed passwords
