"""Logical backup: copy every table to JSON files in a folder outside the repo (read-only).

This is the second backup copy that sits alongside the Render backup and pg_dump.
It works for both SQLite and Postgres and can be restored with restore_snapshot.py.

Writes:
  <out>/<table>.json         every row of the table
  <out>/rate_card.json       the global rate card (from app_state.global_settings)
  <out>/role_catalog.json    the global role catalog and business units
  <out>/manifest.json        source, time, row counts and SHA-256 of each file

Usage:
  .venv/bin/python scripts/backup_snapshot.py --sqlite /path/to/pnl.sqlite3 --out ~/pnl-backups/snap_20261127
  DATABASE_URL=postgresql://... .venv/bin/python scripts/backup_snapshot.py --out ~/pnl-backups/prod_20261127
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from _pnl_db import ReadOnlyDB, add_source_args, ensure_outside_repo, load_payload


def _default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (bytes, bytearray, memoryview)):
        return bytes(o).hex()
    raise TypeError(f"Unserialisable value of type {type(o).__name__}")


def _write(path: Path, obj) -> str:
    data = json.dumps(obj, indent=1, ensure_ascii=False, default=_default).encode('utf-8')
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(parser)
    parser.add_argument('--out', required=True, help='Empty or new folder outside the repo')
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    ensure_outside_repo(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty. Use a new folder so no earlier backup is overwritten.")
    out.mkdir(parents=True, exist_ok=True)

    db = ReadOnlyDB(args)
    manifest = {
        'source': db.label,
        'kind': db.kind,
        'taken_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'tables': {},
    }
    try:
        for table in db.tables():
            rows = db.rows(table)
            sha = _write(out / f"{table}.json", rows)
            manifest['tables'][table] = {'rows': len(rows), 'sha256': sha,
                                         'columns': [c['name'] for c in db.columns(table)]}
            print(f"  {table}: {len(rows)} rows")
            if table == 'app_state':
                settings = next((load_payload(r['json_value']) for r in rows if r['key'] == 'global_settings'), {})
                _write(out / 'rate_card.json', settings.get('rate_card', []))
                _write(out / 'role_catalog.json', {
                    'role_catalog': settings.get('role_catalog', []),
                    'business_units': settings.get('business_units', []),
                })
    finally:
        db.close()

    _write(out / 'manifest.json', manifest)
    print(f"Snapshot written to {out}")


if __name__ == '__main__':
    main()
