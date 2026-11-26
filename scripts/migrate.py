"""Apply pending additive migrations to a Postgres database.

  .venv/bin/python scripts/migrate.py --database-url postgresql://localhost/pnl_dev [--dry-run]

Non-local databases are refused unless you pass --production AND set
PNL_MIGRATE_CONFIRM to the database name, so production is only ever migrated on purpose.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--database-url', required=True)
    ap.add_argument('--dry-run', action='store_true', help='Apply and roll back')
    ap.add_argument('--production', action='store_true', help='Allow a non-local database')
    args = ap.parse_args()

    url = args.database_url.replace('postgres://', 'postgresql://', 1)
    p = urlparse(url)
    dbname = (p.path or '/').lstrip('/')
    local = p.hostname in (None, '', 'localhost', '127.0.0.1', '::1')
    if not local and not (args.production and os.environ.get('PNL_MIGRATE_CONFIRM') == dbname):
        sys.exit(f"{p.hostname}/{dbname} is not a local database. To migrate it on purpose, pass --production "
                 f"and set PNL_MIGRATE_CONFIRM={dbname}.")

    import psycopg
    from pnl.migrate import MigrationError, run
    with psycopg.connect(url) as conn:
        try:
            run(conn, dry_run=args.dry_run)
        except MigrationError as e:
            sys.exit(f"Stopped: {e}")


if __name__ == '__main__':
    main()
