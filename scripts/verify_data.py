"""Data verification. Must pass at the end of every redesign phase (DESIGN.md 2.6). Read-only.

Checks:
  1. Row counts: every table in the baseline counts file has the same or more rows now.
     Bookings and Funnel tables (hidden from the UI) must match exactly.
  2. Nothing went missing: every project and every saved version in the baseline still exists.
  3. Every project and version payload still parses and has its core sections.
  4. Calculation parity: pnl/engine.py in legacy mode matches the baseline within USD 1.
  5. Excel parity: the sample workbooks contain the same values as the baseline.

Usage:
  .venv/bin/python scripts/verify_data.py --sqlite ~/pnl-dev/pnl.sqlite3 \
      --baseline-figures ~/pnl-backups/baseline_20261127/baseline_figures.json
  (--baseline-counts defaults to design/baseline_counts.txt)
Exit code 0 means every check passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import json

from _pnl_db import (FROZEN_TABLES, REPO_ROOT, ReadOnlyDB, add_source_args, import_pnl_services,
                     load_payload, read_counts_file)
from _pnl_figures import compare, compare_cells, figures_from_engine, workbook_cells


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, name: str, problems: list[str], limit: int = 15):
        if problems:
            self.failures += 1
            print(f"FAIL  {name} ({len(problems)} problem{'s' if len(problems) != 1 else ''})")
            for p in problems[:limit]:
                print(f"        {p}")
            if len(problems) > limit:
                print(f"        ... and {len(problems) - limit} more")
        else:
            print(f"PASS  {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(parser)
    parser.add_argument('--baseline-counts', default=str(REPO_ROOT / 'design' / 'baseline_counts.txt'))
    parser.add_argument('--baseline-figures', help='baseline_figures.json from capture_baseline.py')
    parser.add_argument('--counts-only', action='store_true', help='Only run checks 1 and 3')
    args = parser.parse_args()

    counts_path = Path(args.baseline_counts)
    if not counts_path.exists():
        sys.exit(f"Baseline counts file not found: {counts_path}")
    if not args.counts_only and not args.baseline_figures:
        sys.exit("Pass --baseline-figures (or --counts-only).")

    baseline_counts = read_counts_file(counts_path)
    report = Report()
    db = ReadOnlyDB(args)
    print(f"Verifying {db.label}")
    try:
        tables = set(db.tables())
        now_counts = {t: db.count(t) for t in tables}

        # 1. counts
        problems = []
        for t, n in baseline_counts.items():
            have = now_counts.get(t)
            if have is None:
                problems.append(f"table {t} is missing (baseline {n} rows)")
            elif t in FROZEN_TABLES and have != n:
                problems.append(f"{t}: {have} rows, must stay exactly {n}")
            elif have < n:
                problems.append(f"{t}: {have} rows, baseline {n}")
        report.check('Row counts are equal or higher', problems)

        projects = {r['pid']: r['payload'] for r in db.rows('projects')} if 'projects' in tables else {}
        versions = ({f"{r['pid']}|{r['vid']}": r['payload'] for r in db.rows('project_versions')}
                    if 'project_versions' in tables else {})
    finally:
        db.close()

    # 3. payloads load
    parsed_p, parsed_v, problems = {}, {}, []
    for pid, raw in projects.items():
        try:
            p = load_payload(raw)
            missing = [k for k in ('project', 'resources') if k not in p]
            if missing:
                problems.append(f"project {pid}: missing {', '.join(missing)}")
            parsed_p[pid] = p
        except Exception as e:
            problems.append(f"project {pid}: {e}")
    for key, raw in versions.items():
        try:
            parsed_v[key] = load_payload(raw)
        except Exception as e:
            problems.append(f"version {key}: {e}")
    report.check(f'Every project ({len(parsed_p)}) and version ({len(parsed_v)}) payload loads', problems)

    if not args.counts_only:
        base = json.loads(Path(args.baseline_figures).expanduser().read_text(encoding='utf-8'))
        compute_costs, resolve_margin_inputs, build_workbook = import_pnl_services()
        from pnl import engine

        # 2. nothing missing
        problems = [f"project {pid} is gone" for pid in base['projects'] if pid not in projects]
        problems += [f"version {k} is gone" for k in base['versions'] if k not in versions]
        report.check('Every baseline project and version still exists', problems)

        # 4. calc parity
        problems = []
        for kind, items, parsed in (('project', base['projects'], parsed_p), ('version', base['versions'], parsed_v)):
            for key, b in items.items():
                if key not in parsed or 'error' in b:
                    continue
                try:
                    now = figures_from_engine(parsed[key], engine)
                except Exception as e:
                    problems.append(f"{kind} {key}: {e}")
                    continue
                problems += [f"{kind} {key}: {p}" for p in compare(b, now)]
        report.check('Calculation parity within USD 1 (pnl/engine.py, legacy mode)', problems)

        # 5. excel parity
        problems = []
        ignore = {base['meta'].get('capture_date')}
        for pid, cells in base.get('excel', {}).items():
            if pid not in parsed_p:
                problems.append(f"sample project {pid} is gone")
                continue
            p = parsed_p[pid]
            c4c, ax = resolve_margin_inputs(p)
            costs = compute_costs(p.get('resources', []), p.get('rate_card', []),
                                  cloud4c_margin=c4c, ax_margin=ax, one_time_costs=p.get('one_time_costs', []))
            problems += [f"{pid}: {x}" for x in compare_cells(cells, workbook_cells(build_workbook(p, costs)), ignore)]
        report.check(f"Excel parity for {len(base.get('excel', {}))} sample projects", problems)

    print()
    if report.failures:
        print(f"VERIFY FAILED: {report.failures} check(s) failed. Do not merge.")
        sys.exit(1)
    print("VERIFY PASSED")


if __name__ == '__main__':
    main()
