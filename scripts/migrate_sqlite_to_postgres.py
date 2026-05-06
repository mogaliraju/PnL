import os
import sqlite3
from typing import Iterable

import psycopg
from psycopg.rows import dict_row


TABLE_KEYS = {
    "app_state": ["key"],
    "users": ["username"],
    "projects": ["pid"],
    "project_versions": ["pid", "vid"],
    "funnel_entries": ["id"],
    "order_bookings": ["id"],
}


def _db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _fetch_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(r) for r in rows]


def _upsert_sql(table: str, columns: Iterable[str], keys: list[str]) -> str:
    cols = list(columns)
    col_sql = ", ".join(cols)
    val_sql = ", ".join(["%s"] * len(cols))
    key_sql = ", ".join(keys)
    update_cols = [c for c in cols if c not in keys]
    update_sql = ", ".join([f"{c}=excluded.{c}" for c in update_cols])
    return (
        f"INSERT INTO {table}({col_sql}) VALUES ({val_sql}) "
        f"ON CONFLICT({key_sql}) DO UPDATE SET {update_sql}"
    )


def main() -> None:
    pg_url = (os.environ.get("DATABASE_URL") or "").strip()
    sqlite_file = os.environ.get("SQLITE_FILE", "pnl.sqlite3")
    if not pg_url:
        raise SystemExit("DATABASE_URL is required")
    if not os.path.exists(sqlite_file):
        raise SystemExit(f"SQLite file not found: {sqlite_file}")

    sq = sqlite3.connect(sqlite_file)
    pg = psycopg.connect(_db_url(pg_url), row_factory=dict_row)
    try:
        with pg:
            for table, keys in TABLE_KEYS.items():
                cols = _columns(sq, table)
                rows = _fetch_rows(sq, table)
                if not rows:
                    print(f"{table}: 0 rows (skipped)")
                    continue
                sql = _upsert_sql(table, cols, keys)
                with pg.cursor() as cur:
                    for row in rows:
                        cur.execute(sql, tuple(row[c] for c in cols))
                print(f"{table}: migrated {len(rows)} rows")
    finally:
        sq.close()
        pg.close()


if __name__ == "__main__":
    main()
