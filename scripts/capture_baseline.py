"""Capture today's numbers for every project and version (read-only).

Run once in Phase 0, with the pre-redesign code, against the restored copy of production.
Output (keep it outside the repo: it contains customer figures):
  <out>/baseline_figures.json   figures per project and per saved version, plus Excel cells
  <out>/excel/<pid>.xlsx         the three sample workbooks exactly as exported today

Usage:
  .venv/bin/python scripts/capture_baseline.py --sqlite ~/pnl-dev/pnl.sqlite3 --out ~/pnl-backups/baseline_20261127
  .venv/bin/python scripts/capture_baseline.py --database-url postgresql://localhost/pnl_dev --out ...
Options:
  --samples PID PID PID   projects to use for Excel parity (default: the 3 with the most resource lines)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from _pnl_db import REPO_ROOT, ReadOnlyDB, add_source_args, ensure_outside_repo, import_pnl_services, load_payload
from _pnl_figures import figures, workbook_cells


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(parser)
    parser.add_argument('--out', required=True, help='New folder outside the repo')
    parser.add_argument('--samples', nargs='*', help='Project ids for Excel parity')
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    ensure_outside_repo(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty. Use a new folder so an earlier baseline is never overwritten.")
    (out / 'excel').mkdir(parents=True, exist_ok=True)

    compute_costs, resolve_margin_inputs, build_workbook = import_pnl_services()
    commit = subprocess.run(['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True).stdout.strip()

    db = ReadOnlyDB(args)
    try:
        projects = {r['pid']: load_payload(r['payload']) for r in db.rows('projects')}
        versions = [(r['pid'], r['vid'], load_payload(r['payload'])) for r in db.rows('project_versions')]
        source = db.label
    finally:
        db.close()

    result = {
        'meta': {
            'taken_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'capture_date': date.today().isoformat(),
            'source': source,
            'code_commit': commit,
            'note': 'Figures as the pre-redesign code computes them from each stored payload.',
        },
        'projects': {},
        'versions': {},
        'excel': {},
    }
    errors = []
    for pid, payload in projects.items():
        try:
            result['projects'][pid] = figures(payload, compute_costs, resolve_margin_inputs)
        except Exception as e:  # recorded, not fatal: the baseline must show what is broken today
            errors.append(f"project {pid}: {e}")
            result['projects'][pid] = {'error': str(e)}
    for pid, vid, payload in versions:
        key = f"{pid}|{vid}"
        try:
            result['versions'][key] = figures(payload, compute_costs, resolve_margin_inputs)
        except Exception as e:
            errors.append(f"version {key}: {e}")
            result['versions'][key] = {'error': str(e)}

    samples = args.samples or sorted(
        projects, key=lambda p: (-len(projects[p].get('resources') or []), p))[:3]
    for pid in samples:
        payload = projects[pid]
        c4c, ax = resolve_margin_inputs(payload)
        costs = compute_costs(payload.get('resources', []), payload.get('rate_card', []),
                              cloud4c_margin=c4c, ax_margin=ax,
                              one_time_costs=payload.get('one_time_costs', []))
        wb = build_workbook(payload, costs)
        wb.save(out / 'excel' / f"{pid}.xlsx")
        result['excel'][pid] = workbook_cells(wb)

    (out / 'baseline_figures.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(f"Projects: {len(result['projects'])}  Versions: {len(result['versions'])}  Excel samples: {', '.join(samples)}")
    if errors:
        print("Payloads the current code can't calculate (recorded in the baseline):")
        for e in errors:
            print("  " + e)
    print(f"Baseline written to {out}")


if __name__ == '__main__':
    main()
