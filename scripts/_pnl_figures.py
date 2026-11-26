"""The figures the app shows today for a saved payload, and Excel cell extraction.

Mirrors the server-side call sites in the current code (pre-redesign):
  * All Projects list  -> pnl/utils/storage.py list_projects(summary=True)
  * Version History    -> pnl/utils/storage.py list_project_versions (revenue after discount)
  * Excel export       -> pnl/routes/export.py + pnl/services/excel_service.build_workbook
All of them use the payload's own stored rate_card.

Phase 1 replaces `compute` with pnl/engine.calculate(..., mode='legacy') and the
parity check in verify_data.py compares that against the baseline captured here.
"""
from __future__ import annotations

from datetime import date, datetime

# Monetary fields compared within USD 1, ratio fields within 0.0005.
MONEY_FIELDS = ['input_cost', 'total_cost', 'resource_input_cost', 'one_time_input_cost', 'non_margin_cost',
                'margin_basis_sell_cost', 'sell_cost', 'markup', 'revenue_after_discount', 'add_on_cost']
RATIO_FIELDS = ['cloud4c_margin', 'ax_margin', 'gross_margin']


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def figures(payload: dict, compute_costs, resolve_margin_inputs) -> dict:
    project = payload.get('project', {}) or {}
    resources = payload.get('resources', []) or []
    c4c, ax = resolve_margin_inputs(payload)
    costs = compute_costs(resources, payload.get('rate_card', []) or [],
                          cloud4c_margin=c4c, ax_margin=ax,
                          one_time_costs=payload.get('one_time_costs', []) or [])
    discount_pct = _f(project.get('discount_pct'))
    sell = costs.get('sell_cost', 0)
    out = {k: costs.get(k) for k in MONEY_FIELDS + RATIO_FIELDS if k in costs}
    out.update({
        'revenue_after_discount': round(sell * (1 - discount_pct / 100) if discount_pct else sell, 2),
        'discount_pct': discount_pct,
        'add_on_cost': _f(project.get('travel_cost')) + _f(project.get('infra_cost')) + _f(project.get('third_party_cost')),
        'total_hours': sum(_f(r.get('hours')) for r in resources),
        'resource_count': len(resources),
    })
    return out


def compare(base: dict, now: dict) -> list[str]:
    problems = []
    for k in MONEY_FIELDS:
        if k in base and abs(_f(base[k]) - _f(now.get(k))) > 1.0:
            problems.append(f"{k}: baseline {base[k]} now {now.get(k)}")
    for k in RATIO_FIELDS:
        if k in base and abs(_f(base[k]) - _f(now.get(k))) > 0.0005:
            problems.append(f"{k}: baseline {base[k]} now {now.get(k)}")
    for k in ('total_hours', 'resource_count'):
        if k in base and abs(_f(base[k]) - _f(now.get(k))) > 0.001:
            problems.append(f"{k}: baseline {base[k]} now {now.get(k)}")
    return problems


def workbook_cells(wb) -> dict:
    """{sheet: {cell: value}} for every non-empty cell, values made JSON-safe."""
    out = {}
    for ws in wb.worksheets:
        cells = {}
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if v is None or v == '':
                    continue
                if isinstance(v, (datetime, date)):
                    v = v.isoformat()
                elif not isinstance(v, (int, float, str, bool)):
                    v = str(v)
                cells[c.coordinate] = v
        out[ws.title] = cells
    return out


def compare_cells(base: dict, now: dict, ignore_values: set) -> list[str]:
    problems = []
    for sheet, cells in base.items():
        if sheet not in now:
            problems.append(f"sheet '{sheet}' missing")
            continue
        for ref, bv in cells.items():
            nv = now[sheet].get(ref)
            if bv in ignore_values:
                continue
            if isinstance(bv, (int, float)) and isinstance(nv, (int, float)):
                if abs(bv - nv) > 1.0:
                    problems.append(f"{sheet}!{ref}: baseline {bv} now {nv}")
            elif bv != nv:
                problems.append(f"{sheet}!{ref}: baseline {bv!r} now {nv!r}")
    return problems


def figures_from_engine(payload: dict, engine) -> dict:
    """The same figures, computed by pnl/engine.py in legacy mode (Phase 1 onwards)."""
    r = engine.calculate(payload, engine.LEGACY)
    d = engine.legacy_costs_dict(r)
    project = payload.get('project', {}) or {}
    out = {k: d.get(k) for k in MONEY_FIELDS + RATIO_FIELDS if k in d}
    out.update({
        'revenue_after_discount': round(float(r.legacy_discounted_revenue), 2),
        'discount_pct': _f(project.get('discount_pct')),
        'add_on_cost': _f(project.get('travel_cost')) + _f(project.get('infra_cost')) + _f(project.get('third_party_cost')),
        'total_hours': float(r.hours),
        'resource_count': len(payload.get('resources', []) or []),
    })
    return out
