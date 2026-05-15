"""
Migrate all data from PostgreSQL → local SQLite backup.

Usage (run locally or in a Render one-off job):
    DATABASE_URL=<your-render-postgres-url> python migrate_postgres_to_sqlite.py

The script reads every table from Postgres and writes a full backup to:
    backup_<timestamp>/
        projects.json
        versions.json
        state.json          (working_data + global_settings)
        users.json
        bookings.json
        funnel.json

These files are also the format the SQLite storage layer can auto-migrate
from on first boot, so you can drop them into DATA_DIR and restart the app
pointing at SQLite.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERROR: Set DATABASE_URL environment variable first.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = Path(f"backup_{timestamp}")
out_dir.mkdir()
print(f"Backing up to {out_dir}/")


def dump(conn, table, out_file):
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        data = [dict(r) for r in rows]
        (out_dir / out_file).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"  {table}: {len(data)} rows → {out_file}")
        return data
    except Exception as e:
        print(f"  {table}: SKIP ({e})")
        return []


with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
    print("\n── Raw table dumps ──────────────────────────────")
    dump(conn, "projects", "projects_raw.json")
    dump(conn, "project_versions", "versions_raw.json")
    dump(conn, "app_state", "state_raw.json")
    dump(conn, "users", "users_raw.json")
    dump(conn, "bookings", "bookings_raw.json")
    dump(conn, "funnel_entries", "funnel_raw.json")

    print("\n── SQLite-compatible migration files ────────────")

    # projects → individual project JSON files (storage migration format)
    try:
        projects = conn.execute("SELECT pid, payload FROM projects").fetchall()
        project_dir = out_dir / "projects"
        project_dir.mkdir()
        for row in projects:
            pid = row["pid"]
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            (project_dir / f"{pid}.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        print(f"  projects: {len(projects)} files → projects/")
    except Exception as e:
        print(f"  projects migration: SKIP ({e})")

    # versions → versions/<pid>/<vid>.json
    try:
        versions = conn.execute("SELECT pid, vid, payload, label FROM project_versions").fetchall()
        ver_dir = out_dir / "versions"
        for row in versions:
            pid, vid = row["pid"], row["vid"]
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            d = ver_dir / pid
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{vid}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  versions: {len(versions)} files → versions/")
    except Exception as e:
        print(f"  versions migration: SKIP ({e})")

    # app_state → data.json + settings.json
    try:
        rows = conn.execute("SELECT key, payload FROM app_state").fetchall()
        state = {r["key"]: r["payload"] for r in rows}
        for key, filename in [("working_data", "data.json"), ("global_settings", "settings.json")]:
            if key in state:
                payload = state[key]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                (out_dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
                print(f"  {key} → {filename}")
    except Exception as e:
        print(f"  app_state migration: SKIP ({e})")

    # users → users.json (storage migration format)
    try:
        rows = conn.execute("SELECT username, payload FROM users").fetchall()
        users = {}
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            users[row["username"]] = payload
        (out_dir / "users.json").write_text(json.dumps(users, indent=2), encoding="utf-8")
        print(f"  users: {len(users)} → users.json")
    except Exception as e:
        print(f"  users migration: SKIP ({e})")

print(f"""
✓ Backup complete → {out_dir}/

To switch the app to SQLite:
  1. Copy everything inside {out_dir}/ into your DATA_DIR folder
  2. On Render: remove the DATABASE_URL environment variable
  3. On Render: add a Persistent Disk, set DATA_DIR to its mount path (e.g. /data)
  4. Deploy — the app will auto-migrate from the JSON files into SQLite on first boot
""")
