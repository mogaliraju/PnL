"""Additive-only Postgres migration runner (DESIGN.md 2.2).

Migrations are numbered files in pnl/migrations/, applied in order and recorded in
schema_migrations:
  NNNN_name.sql  schema changes. Rejected if they contain DROP, TRUNCATE, DELETE,
                 UPDATE, RENAME or a column type change.
  NNNN_name.py   data seeding/backfill. Defines BACKFILL = {table: {new columns}} and
                 migrate(db, log). `db.execute` rejects the same statements, except
                 UPDATEs that only SET columns listed in BACKFILL.

Every run, in ONE transaction:
  * fingerprints the content of every existing table (its existing columns only);
  * applies all pending migrations;
  * checks every existing table still has the same rows with the same values in its
    original columns, and no fewer rows. Any difference rolls everything back.
With dry_run=True it rolls back at the end so nothing is kept.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
FORBIDDEN = re.compile(r'\b(DROP|TRUNCATE|DELETE|UPDATE|RENAME)\b|ALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE', re.I)
UPDATE_RE = re.compile(r'^\s*UPDATE\s+"?(\w+)"?\s+(?:AS\s+\w+\s+)?SET\s+(.*?)\s+(?:FROM|WHERE)\b', re.I | re.S)


class MigrationError(RuntimeError):
    pass


def _strip_comments(sql: str) -> str:
    return re.sub(r'--[^\n]*', '', sql)


def migration_files() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob('[0-9][0-9][0-9][0-9]_*') if p.suffix in ('.sql', '.py'))


def check_additive(path: Path) -> None:
    if path.suffix != '.sql':
        return
    body = _strip_comments(path.read_text(encoding='utf-8'))
    m = FORBIDDEN.search(body)
    if m:
        raise MigrationError(f"{path.name} contains '{m.group(0)}'. Migrations must be additive only (DESIGN.md 2.2).")


class GuardedDB:
    """What a .py migration gets: execute() with the additive rules enforced."""

    def __init__(self, conn, backfill: dict[str, set[str]], name: str):
        self.conn, self.backfill, self.name = conn, {t: set(c) for t, c in backfill.items()}, name

    def execute(self, sql: str, params=()):
        body = _strip_comments(sql)
        m = FORBIDDEN.search(body)
        if m and m.group(1) and m.group(1).upper() == 'UPDATE':
            u = UPDATE_RE.match(body)
            if not u:
                raise MigrationError(f"{self.name}: UPDATE must be 'UPDATE table SET ... WHERE/FROM ...'")
            table = u.group(1).lower()
            assigned = {a.split('=')[0].strip().strip('"').lower() for a in _split_assignments(u.group(2))}
            allowed = self.backfill.get(table, set())
            if not assigned or not assigned <= allowed:
                raise MigrationError(f"{self.name}: UPDATE {table} may only set {sorted(allowed)}, got {sorted(assigned)}")
            rest = body[u.end():]
            m2 = re.search(r'\b(DROP|TRUNCATE|DELETE|RENAME)\b', rest, re.I)
            if m2:
                raise MigrationError(f"{self.name} contains '{m2.group(0)}'")
        elif m:
            raise MigrationError(f"{self.name} contains '{m.group(0)}'")
        return self.conn.execute(sql, params)


def _split_assignments(s: str) -> list[str]:
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _tables(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1").fetchall()]


def _columns(conn, table: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,)).fetchall()]


def _counts(conn) -> dict[str, int]:
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in _tables(conn)}


def _fingerprint(conn, table: str, cols: list[str]) -> tuple[int, str]:
    collist = ', '.join(f'"{c}"' for c in cols)
    n, digest = conn.execute(
        f"SELECT COUNT(*), md5(coalesce(string_agg(r::text, '|' ORDER BY r::text), '')) FROM (SELECT {collist} FROM \"{table}\") r"
    ).fetchone()
    return n, digest


def snapshot(conn) -> dict[str, tuple[list[str], int, str]]:
    snap = {}
    for t in _tables(conn):
        cols = _columns(conn, t)
        snap[t] = (cols, *_fingerprint(conn, t, cols))
    return snap


def pending(conn) -> list[Path]:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now(), checksum text NOT NULL)""")
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    return [p for p in migration_files() if p.stem not in done]


def _load_py(path: Path):
    spec = importlib.util.spec_from_file_location(f"pnl_migration_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, 'migrate'):
        raise MigrationError(f"{path.name} has no migrate(db, log)")
    return mod


def run(conn, dry_run: bool = False, log=print) -> list[str]:
    """Apply pending migrations on a psycopg connection (autocommit off). Returns applied versions."""
    for f in migration_files():
        check_additive(f)
    before = snapshot(conn)
    todo = pending(conn)
    if not todo:
        conn.rollback()
        log("No pending migrations.")
        return []
    try:
        for f in todo:
            text = f.read_text(encoding='utf-8')
            log(f"Applying {f.name}")
            if f.suffix == '.sql':
                conn.execute(text)
            else:
                mod = _load_py(f)
                mod.migrate(GuardedDB(conn, getattr(mod, 'BACKFILL', {}), f.name), log)
            conn.execute("INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)",
                         (f.stem, hashlib.sha256(text.encode()).hexdigest()))
        changed = []
        for t, (cols, n, digest) in before.items():
            if t == 'schema_migrations':
                continue
            n2, digest2 = _fingerprint(conn, t, cols)
            if n2 < n:
                changed.append(f"{t}: {n} -> {n2} rows")
            elif digest2 != digest:
                changed.append(f"{t}: existing data changed")
        if changed:
            raise MigrationError("Existing data would change, rolling back: " + '; '.join(changed))
        after = _counts(conn)
        for t in sorted(after):
            log(f"  {t}: {before.get(t, (None, 0))[1]} -> {after[t]} rows")
        log("  Existing columns in every existing table: unchanged (content fingerprint matches).")
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
