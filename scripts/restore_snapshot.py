"""Restore a backup_snapshot.py folder into a NEW, EMPTY database.

This is the way back if the JSON snapshot is the copy you need. It never writes into a
database that already has rows in any table: it stops before inserting anything.
For a pg_dump file use pg_restore instead (see design/BACKUP_AND_ROLLBACK.md).

Tables are created with the app's own schema (pnl.utils.storage._create_schema),
then every row from the snapshot is inserted in one transaction. Row counts are checked
against manifest.json at the end; any mismatch rolls the whole restore back.

Usage:
  .venv/bin/python scripts/restore_snapshot.py --snapshot ~/pnl-backups/prod_20261127 --sqlite ~/pnl-dev/pnl.sqlite3
  .venv/bin/python scripts/restore_snapshot.py --snapshot ~/pnl-backups/prod_20261127 --database-url postgresql://localhost/pnl_dev
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--snapshot', required=True, help='Folder written by backup_snapshot.py')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--sqlite', help='New SQLite file to create (must not exist yet)')
    target.add_argument('--database-url', help='Empty Postgres database to restore into')
    args = parser.parse_args()

    snap = Path(args.snapshot).expanduser().resolve()
    manifest = json.loads((snap / 'manifest.json').read_text(encoding='utf-8'))

    if args.sqlite:
        path = Path(args.sqlite).expanduser().resolve()
        if path.exists():
            sys.exit(f"{path} already exists. Restore only creates new files.")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        ph = '?'
        is_pg = False
    else:
        url = args.database_url
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, row_factory=dict_row)
        ph = '%s'
        is_pg = True
        os.environ['DATABASE_URL'] = url

    # Build the app's schema without running its JSON-file migration.
    os.environ.setdefault('SECRET_KEY', 'restore-script')
    import tempfile
    os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='pnl-restore-')
    if not is_pg:
        os.environ.pop('DATABASE_URL', None)
    sys.path.insert(0, str(REPO_ROOT))
    from pnl.utils import storage

    def existing_tables():
        if is_pg:
            return {r['table_name'] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'").fetchall()}
        return {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # Refuse if any table already has rows.
    for t in existing_tables():
        n = conn.execute(f'SELECT COUNT(*) AS c FROM "{t}"').fetchone()['c']
        if n:
            conn.close()
            sys.exit(f"Target table {t} already has {n} rows. Restore only goes into an empty database.")

    try:
        storage._create_schema(conn)
        have = existing_tables()
        for table, info in manifest['tables'].items():
            if table not in have:
                cols = ', '.join(f'"{c}" TEXT' for c in info['columns'])
                conn.execute(f'CREATE TABLE "{table}" ({cols})')
            rows = json.loads((snap / f"{table}.json").read_text(encoding='utf-8'))
            for row in rows:
                cols = list(row.keys())
                sql = (f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '
                       f'VALUES ({", ".join([ph] * len(cols))})')
                conn.execute(sql, [row[c] for c in cols])
        for table, info in manifest['tables'].items():
            n = conn.execute(f'SELECT COUNT(*) AS c FROM "{table}"').fetchone()['c']
            if n != info['rows']:
                raise RuntimeError(f"{table}: restored {n} rows, snapshot has {info['rows']}")
            print(f"  {table}: {n} rows")
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        if args.sqlite:
            Path(args.sqlite).expanduser().resolve().unlink(missing_ok=True)
        sys.exit(f"Restore failed and was rolled back: {e}")
    conn.close()
    print("Restore complete.")


if __name__ == '__main__':
    main()
