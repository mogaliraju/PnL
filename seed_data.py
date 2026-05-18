"""
Seed script — restores backed-up project data into a fresh database.
Always exits 0 so gunicorn starts even if seeding fails.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'seed-temp-key')
os.environ.setdefault('DATA_DIR', os.environ.get('DATA_DIR', '/tmp'))

BACKUP_DIR = Path(__file__).parent / 'data_backup'

try:
    if not BACKUP_DIR.exists():
        print("[seed] No data_backup/ folder found — skipping seed.")
        sys.exit(0)

    from pnl.utils.storage import (
        save_project_record, save_project_version,
        save_global_settings, list_projects
    )

    existing = list_projects()
    if existing:
        print(f"[seed] DB already has {len(existing)} projects — skipping seed.")
        sys.exit(0)

    print("[seed] Fresh database detected — restoring from data_backup/ ...")

    # Global settings
    settings_file = BACKUP_DIR / 'global_data.json'
    if settings_file.exists() and settings_file.stat().st_size > 0:
        data = json.loads(settings_file.read_text(encoding='utf-8'))
        settings = {k: data[k] for k in ('rate_card', 'role_catalog', 'business_units') if k in data}
        save_global_settings(settings)
        print(f"[seed] Settings: {len(settings.get('rate_card', []))} rate card rows, "
              f"{len(settings.get('role_catalog', []))} catalog groups")

    # Projects
    restored = 0
    for f in sorted(BACKUP_DIR.glob('project_*.json')):
        if f.stat().st_size == 0:
            print(f"[seed] SKIP {f.name} (empty file)")
            continue
        try:
            payload = json.loads(f.read_text(encoding='utf-8'))
            meta = payload.get('_meta', {})
            project_id = meta.get('id') or f.stem.replace('project_', '')
            if not project_id:
                continue
            save_project_record(project_id, payload)
            save_project_version(project_id, f'seed_{project_id}', payload, label='Restored from backup')
            customer = payload.get('project', {}).get('customer', project_id)
            print(f"[seed] Restored: {project_id} ({customer})")
            restored += 1
        except Exception as e:
            print(f"[seed] SKIP {f.name}: {e}")

    print(f"[seed] Done — {restored} project(s) restored.")

except Exception as e:
    print(f"[seed] ERROR: {e} — continuing to start app anyway.")

sys.exit(0)
