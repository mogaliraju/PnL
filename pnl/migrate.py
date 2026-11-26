"""Additive-only Postgres migration runner (DESIGN.md 2.2).

Migrations are the numbered files in pnl/migrations/*.sql, applied in order and
recorded in schema_migrations. A run:
  * rejects any file containing DROP, TRUNCATE, DELETE, UPDATE, RENAME or a column
    type change before touching the database;
  * applies every pending file in ONE transaction;
  * counts rows in every table before and after, inside that transaction, and rolls
    everything back if any existing table lost a row;
  * with dry_run, rolls back at the end so nothing is kept.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
FORBIDDEN = re.compile(r'\b(DROP|TRUNCATE|DELETE|UPDATE|RENAME)\b|ALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE', re.I)


class MigrationError(RuntimeError):
    pass


def _strip_comments(sql: str) -> str:
    return re.sub(r'--[^\n]*', '', sql)


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob('[0-9][0-9][0-9][0-9]_*.sql'))


def check_additive(path: Path) -> None:
    body = _strip_comments(path.read_text(encoding='utf-8'))
    m = FORBIDDEN.search(body)
    if m:
        raise MigrationError(f"{path.name} contains '{m.group(0)}'. Migrations must be additive only (DESIGN.md 2.2).")


def _counts(conn) -> dict[str, int]:
    tables = [r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'").fetchall()]
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


def pending(conn) -> list[Path]:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now(), checksum text NOT NULL)""")
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    return [p for p in migration_files() if p.stem not in done]


def run(conn, dry_run: bool = False, log=print) -> list[str]:
    """Apply pending migrations on a psycopg connection (autocommit off). Returns applied versions."""
    files = migration_files()
    for f in files:
        check_additive(f)
    before = _counts(conn)
    todo = pending(conn)
    if not todo:
        conn.rollback()
        log("No pending migrations.")
        return []
    try:
        for f in todo:
            sql = f.read_text(encoding='utf-8')
            log(f"Applying {f.name}")
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)",
                         (f.stem, hashlib.sha256(sql.encode()).hexdigest()))
        after = _counts(conn)
        lost = {t: (n, after.get(t)) for t, n in before.items() if after.get(t, -1) < n}
        if lost:
            raise MigrationError(f"Row counts dropped, rolling back: {lost}")
        for t in sorted(after):
            log(f"  {t}: {before.get(t, 0)} -> {after[t]} rows")
        if dry_run:
            conn.rollback()
            log("Dry run: rolled back, nothing kept.")
        else:
            conn.commit()
            log(f"Committed {len(todo)} migration(s).")
        return [f.stem for f in todo]
    except Exception:
        conn.rollback()
        raise
