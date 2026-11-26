"""Read-only database access shared by the Phase 0 safety scripts.

Every connection opened here is read-only at the driver level:
  * Postgres: the session runs with default_transaction_read_only=on and the
    psycopg connection is marked read_only, so any INSERT/UPDATE/DELETE/DDL fails.
  * SQLite: the file is opened with a `mode=ro` URI, so the file cannot be written.

Source selection (first match wins):
  --sqlite PATH          a SQLite file (for example a copy of pnl.sqlite3)
  --database-url URL     a Postgres URL
  $DATABASE_URL          a Postgres URL from the environment

These scripts never import the app's storage layer, because that layer runs
CREATE TABLE / migration code on first use.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]

# Tables the app owns today (see design/CURRENT_SCHEMA.md).
APP_TABLES = ['app_state', 'users', 'projects', 'project_versions', 'funnel_entries', 'order_bookings']
# Tables whose counts must stay exactly equal (modules hidden from the UI, data untouched).
FROZEN_TABLES = ['funnel_entries', 'order_bookings']


def add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--sqlite', help='Path to a SQLite database file (opened read-only)')
    parser.add_argument('--database-url', help='Postgres URL (defaults to $DATABASE_URL); opened read-only')


def describe(url: str) -> str:
    """Host/db description without credentials, safe to print."""
    p = urlparse(url)
    return f"postgres://{p.hostname or '?'}:{p.port or 5432}/{(p.path or '/').lstrip('/')}"


class ReadOnlyDB:
    def __init__(self, args: argparse.Namespace):
        self.kind = None
        self.label = None
        if args.sqlite:
            path = Path(args.sqlite).expanduser().resolve()
            if not path.exists():
                sys.exit(f"SQLite file not found: {path}")
            self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            self.conn.row_factory = sqlite3.Row
            self.kind = 'sqlite'
            self.label = f"sqlite:{path}"
            return

        url = (args.database_url or os.environ.get('DATABASE_URL') or '').strip()
        if not url:
            sys.exit("No database given. Pass --sqlite PATH or --database-url URL (or set DATABASE_URL).")
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError:
            sys.exit("psycopg is required for Postgres. Run: .venv/bin/pip install 'psycopg[binary]'")
        self.conn = psycopg.connect(url, row_factory=dict_row,
                                    options='-c default_transaction_read_only=on')
        self.conn.read_only = True
        self.kind = 'postgres'
        self.label = describe(url)

    def tables(self) -> list[str]:
        if self.kind == 'sqlite':
            rows = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return [r['name'] for r in rows]
        rows = self.conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
        ).fetchall()
        return [r['table_name'] for r in rows]

    def columns(self, table: str) -> list[dict]:
        if self.kind == 'sqlite':
            rows = self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            return [{'name': r['name'], 'type': r['type'], 'nullable': not r['notnull'],
                     'default': r['dflt_value'], 'pk': bool(r['pk'])} for r in rows]
        rows = self.conn.execute(
            "SELECT c.column_name, c.data_type, c.is_nullable, c.column_default, "
            "  EXISTS (SELECT 1 FROM information_schema.key_column_usage k "
            "          JOIN information_schema.table_constraints t ON t.constraint_name = k.constraint_name "
            "          WHERE t.constraint_type='PRIMARY KEY' AND k.table_name=c.table_name "
            "            AND k.column_name=c.column_name AND k.table_schema='public') AS pk "
            "FROM information_schema.columns c WHERE c.table_schema='public' AND c.table_name=%s "
            "ORDER BY c.ordinal_position", (table,)
        ).fetchall()
        return [{'name': r['column_name'], 'type': r['data_type'], 'nullable': r['is_nullable'] == 'YES',
                 'default': r['column_default'], 'pk': r['pk']} for r in rows]

    def count(self, table: str) -> int:
        row = self.conn.execute(f'SELECT COUNT(*) AS c FROM "{table}"').fetchone()
        return int(row['c'])

    def rows(self, table: str) -> list[dict]:
        cur = self.conn.execute(f'SELECT * FROM "{table}"')
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def read_counts_file(path: Path) -> dict[str, int]:
    counts = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('table,'):
            continue
        table, _, n = line.partition(',')
        counts[table.strip()] = int(n)
    return counts


def load_payload(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def ensure_outside_repo(path: Path) -> None:
    path = path.expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        sys.exit(f"Refusing to write data inside the repo ({path}). Pick a folder outside {REPO_ROOT}.")


def import_pnl_services():
    """Import the pure calculation and Excel modules without touching any database.

    Importing the `pnl` package loads pnl.config, which creates folders under DATA_DIR
    and a log file. Point DATA_DIR at a throwaway folder first.
    """
    import tempfile
    os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='pnl-verify-')
    os.environ.setdefault('SECRET_KEY', 'verify-script')
    os.environ.pop('DATABASE_URL', None)  # the app modules must never see a real database here
    sys.path.insert(0, str(REPO_ROOT))
    from pnl.services.pnl_service import compute_costs, resolve_margin_inputs
    from pnl.services.excel_service import build_workbook
    return compute_costs, resolve_margin_inputs, build_workbook
