"""
Seed script — restores backed-up project data into a fresh database.
Run once after connecting a new database:
    python seed_data.py

Reads all project_*.json files from data_backup/ and saves them into
whichever database DATABASE_URL points to (Postgres or SQLite).
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'seed-temp-key')
os.environ.setdefault('DATA_DIR', os.environ.get('DATA_DIR', '/tmp'))

BACKUP_DIR = Path(__file__).parent / 'data_backup'

if not BACKUP_DIR.exists():
    print("ERROR: data_backup/ folder not found. Run from the project root.")
    sys.exit(1)

from pnl.utils.storage import (
    save_project_record, save_project_version,
    save_global_settings, list_projects
)

# Check if DB already has data
existing = list_projects()
if existing:
    print(f"Database already has {len(existing)} projects. Skipping seed.")
    sys.exit(0)

print("Seeding database from data_backup/...")

# ── Global settings (rate card, role catalog, BUs) ──────────────
settings_file = BACKUP_DIR / 'global_data.json'
if settings_file.exists():
    data = json.loads(settings_file.read_text(encoding='utf-8'))
    settings = {k: data[k] for k in ('rate_card', 'role_catalog', 'business_units') if k in data}
    save_global_settings(settings)
    print(f"  Settings restored: {len(settings.get('rate_card', []))} rate card rows, "
          f"{len(settings.get('role_catalog', []))} catalog groups")

# ── Projects ────────────────────────────────────────────────────
project_files = sorted(BACKUP_DIR.glob('project_*.json'))
restored = 0
for f in project_files:
    try:
        payload = json.loads(f.read_text(encoding='utf-8'))
        meta = payload.get('_meta', {})
        project_id = meta.get('id') or f.stem.replace('project_', '')
        if not project_id:
            continue
        save_project_record(project_id, payload)
        save_project_version(project_id, f'seed_{project_id}', payload, label='Seeded from backup')
        customer = payload.get('project', {}).get('customer', project_id)
        print(f"  Restored: {project_id} ({customer})")
        restored += 1
    except Exception as e:
        print(f"  SKIP {f.name}: {e}")

print(f"\nDone — {restored} project(s) restored.")
