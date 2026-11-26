"""Prepare an EMPTY local Postgres database for the Postgres test suite (run once).

  /opt/homebrew/opt/postgresql@17/bin/createdb pnl_test
  .venv/bin/python scripts/setup_test_db.py --database-url postgresql://localhost/pnl_test
  PNL_TEST_PG_URL=postgresql://localhost/pnl_test .venv/bin/python -m pytest

Creates the app's base tables and applies every migration. Tests then run inside
transactions that are rolled back, so the database stays empty.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--database-url', required=True)
    url = ap.parse_args().database_url
    if urlparse(url).hostname not in (None, '', 'localhost', '127.0.0.1', '::1'):
        sys.exit('Test databases must be local.')
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, row_factory=dict_row) as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema='public' AND table_name='projects'").fetchone()['n']
        if n and conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()['n']:
            sys.exit('That database has projects in it. Use an empty database for tests.')
    os.environ.update(DATABASE_URL=url, DATA_DIR=tempfile.mkdtemp(), SECRET_KEY='setup')
    from pnl.utils import storage
    from pnl.migrate import run
    with psycopg.connect(url, row_factory=dict_row) as conn:
        storage._create_schema(conn)
        conn.commit()
    with psycopg.connect(url) as conn:
        run(conn)


if __name__ == '__main__':
    main()
