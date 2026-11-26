"""Print `table,count` for every table in the database (read-only).

Usage:
  .venv/bin/python scripts/count_rows.py --sqlite /path/to/pnl.sqlite3
  DATABASE_URL=postgresql://... .venv/bin/python scripts/count_rows.py --out design/baseline_counts.txt
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _pnl_db import ReadOnlyDB, add_source_args


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(parser)
    parser.add_argument('--out', help='Also write the counts to this file')
    args = parser.parse_args()

    db = ReadOnlyDB(args)
    try:
        lines = [
            f"# Row counts taken {datetime.now(timezone.utc).isoformat(timespec='seconds')} from {db.label}",
            'table,count',
        ]
        for table in db.tables():
            lines.append(f"{table},{db.count(table)}")
    finally:
        db.close()

    text = '\n'.join(lines) + '\n'
    print(text, end='')
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
        print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
