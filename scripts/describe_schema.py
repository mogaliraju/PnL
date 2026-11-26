"""Describe the live schema and the shape of stored JSON (read-only), as Markdown.

Paste the output into design/CURRENT_SCHEMA.md under "Live schema" after running it
against the restored copy of production.

Usage:
  .venv/bin/python scripts/describe_schema.py --database-url postgresql://localhost/pnl_dev
"""
from __future__ import annotations

import argparse
from collections import Counter

from _pnl_db import ReadOnlyDB, add_source_args, load_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(parser)
    args = parser.parse_args()
    db = ReadOnlyDB(args)
    try:
        print(f"Source: `{db.label}`\n")
        tables = db.tables()
        for t in tables:
            print(f"### `{t}` ({db.count(t)} rows)\n")
            print("| Column | Type | Nullable | Default | PK |\n|---|---|---|---|---|")
            for c in db.columns(t):
                print(f"| {c['name']} | {c['type']} | {'yes' if c['nullable'] else 'no'} | {c['default'] or ''} | {'yes' if c['pk'] else ''} |")
            print()

        if 'projects' in tables:
            keys, proj_keys, rc_formats, levels, groups, roles = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
            margin_modes = Counter()
            payloads = [load_payload(r['payload']) for r in db.rows('projects')]
            if 'project_versions' in tables:
                payloads += [load_payload(r['payload']) for r in db.rows('project_versions')]
            for p in payloads:
                keys.update(p.keys())
                proj_keys.update((p.get('project') or {}).keys())
                for rc in p.get('rate_card') or []:
                    rc_formats['rates-by-category' if isinstance(rc.get('rates'), dict) else 'flat rate'] += 1
                    levels[str(rc.get('level'))] += 1
                for r in p.get('resources') or []:
                    groups[str(r.get('group'))] += 1
                    roles[str(r.get('role'))] += 1
                has_split = p.get('cloud4c_margin') is not None or p.get('ax_margin') is not None
                margin_modes['cloud4c+ax' if has_split else 'legacy target_margin only'] += 1
            n = len(payloads)
            print(f"### Stored project JSON ({n} payloads: projects + versions)\n")
            print("Top-level keys: " + ', '.join(f"`{k}` ({v})" for k, v in keys.most_common()) + "\n")
            print("`project` keys: " + ', '.join(f"`{k}` ({v})" for k, v in proj_keys.most_common()) + "\n")
            print("Rate card entry format: " + ', '.join(f"{k} ({v})" for k, v in rc_formats.items()) + "\n")
            print("Levels seen: " + ', '.join(f"`{k}` ({v})" for k, v in sorted(levels.items())) + "\n")
            print("Margin fields: " + ', '.join(f"{k} ({v})" for k, v in margin_modes.items()) + "\n")
            print(f"Resource categories seen ({len(groups)}): " + ', '.join(f"`{k}`" for k in sorted(groups)) + "\n")
            print(f"Distinct role names on resource lines: {len(roles)}\n")
    finally:
        db.close()


if __name__ == '__main__':
    main()
