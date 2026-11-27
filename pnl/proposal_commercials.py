"""Commercials for a generated proposal, built from a saved PnL version (design/PROPOSALS.md 5.1).

Every amount comes from pnl/engine.py. The model never sees these amounts: it only gets the
duration and the team (pnl_context) so its timeline matches the plan.

The one-time cost lines always add up to the engine's contract value for the version:
  - one line per resource category (workstream), carrying its share of the price after margins
    and discount,
  - one line per margin-bearing one-time cost and add-on, priced the same way,
  - one line per pass-through item (licenses, add-ons passed through) at cost.
Whole-currency rounding is spread so the lines still sum to the rounded contract value.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from pnl import engine

PAYMENT_PLANS = {
    'automatonsx': [('Advance on PO', 30), ('Completion of data integration', 30), ('UAT sign off', 30),
                    ('Project closure and handover', 10)],
    'cloud4c': [('Advance on PO', 20), ('Design and plan sign off', 20), ('Build completed in UAT', 40),
                ('Go-live and closure', 20)],
}
ADDON_LABELS = {'travel': 'Travel and expenses', 'infra': 'Infrastructure', 'third_party': 'Third-party services'}
HOURS_PER_WEEK = 40


def default_terms(brand: str, client_short: str) -> dict:
    return {
        'payment_plan': [{'milestone': m, 'percent': p} for m, p in PAYMENT_PLANS[brand]],
        'payment_terms': ['Invoices are payable within 30 days of the invoice date.'],
        'consumption_note': f'Cloud consumption and licences (for example Fabric capacity, Power BI and Purview) '
                            f'are procured and borne by {client_short}.',
        'tax_note': 'All figures are in USD and exclude applicable local taxes.',
    }


def _weeks(project: dict, lines) -> int:
    try:
        months = float(project.get('duration_months') or 0)
    except (TypeError, ValueError):
        months = 0
    if months > 0:
        return max(1, round(months * 52 / 12))
    try:
        start, end = date.fromisoformat(str(project.get('expected_start_date'))[:10]), \
            date.fromisoformat(str(project.get('expected_end_date'))[:10])
        if end > start:
            return max(1, math.ceil((end - start).days / 7))
    except ValueError:
        pass
    longest = max((float(l.hours) for l in lines), default=0)          # nothing else to go on: full time
    return max(1, math.ceil(longest / HOURS_PER_WEEK))


def _team(lines, weeks: int) -> list[dict]:
    by_role: dict[str, list] = {}
    for l in lines:
        if l.hours > 0:
            by_role.setdefault(l.role or l.category or 'Consultant', []).append(float(l.hours))
    team = []
    for role, hours in by_role.items():
        alloc = sum(hours) / (len(hours) * weeks * HOURS_PER_WEEK) * 100
        alloc = min(100, max(10, round(alloc / 10) * 10))
        team.append({'role': role, 'count': len(hours), 'allocation': f'{alloc}%'})
    return team


def _spread(parts: list[tuple[str, str, Decimal]], total: Decimal) -> list[dict]:
    """Round each line to whole units so the rounded lines add up to the rounded total."""
    target = int(total.quantize(Decimal('1')))
    floors = [math.floor(float(a)) for _, _, a in parts]
    rest = target - sum(floors)
    order = sorted(range(len(parts)), key=lambda i: float(parts[i][2]) - floors[i], reverse=True)
    for i in order[:max(0, rest)]:
        floors[i] += 1
    return [{'component': c, 'cost_type': t, 'amount': floors[i]}
            for i, (c, t, _) in enumerate(parts) if floors[i] or len(parts) == 1]


def commercials_from_payload(payload: dict, brand: str, *, project_name: str, version_no: int,
                             client_short: str = '', overrides: dict | None = None) -> dict:
    """The commercials dict (shape of proposals/samples/*/commercials.json) for one saved version."""
    r = engine.calculate(payload)                          # raises EngineInputError for bad levers
    project = payload.get('project') or {}
    weeks = _weeks(project, r.lines)

    # Price factor for everything that takes margin: what the customer pays per unit of cost.
    factor = (r.list_price - r.discount) / r.cost_basis if r.cost_basis > 0 else Decimal(0)
    parts: list[tuple[str, str, Decimal]] = []
    by_cat: dict[str, Decimal] = {}
    for l in r.lines:                                      # one line per workstream (resource category)
        key = l.category or 'Project Implementation Cost'
        by_cat[key] = by_cat.get(key, Decimal(0)) + l.cost
    for cat, cost in by_cat.items():
        if cost > 0:
            parts.append((cat, 'OTC', cost * factor))
    items = [x for x in (payload.get('one_time_costs') or []) if isinstance(x, dict)]
    for x in items:
        amt = engine.D(x.get('amount'))
        if amt <= 0:
            continue
        if engine.is_pass_through_item(x):
            parts.append((x.get('label') or 'Licences', 'License', amt))
        else:
            parts.append((x.get('label') or 'Other one-time costs', 'OTC', amt * factor))
    if r.mode == engine.V2:
        treatment = engine.addon_treatment(payload)
        for k in engine.ADDON_KEYS:
            amt = engine.D(project.get(engine.ADDON_FIELDS[k]))
            if amt > 0:
                margin = treatment[k] == 'margin'
                parts.append((ADDON_LABELS[k], 'OTC' if margin else 'Pass-through', amt * factor if margin else amt))
    if not parts and r.contract_value > 0:
        parts.append(('Project Implementation Cost', 'OTC', r.contract_value))

    o = dict(default_terms(brand, client_short or project.get('customer') or 'the client'))
    o.update({k: v for k, v in (overrides or {}).items() if v not in (None, '', [])})
    if project.get('payment_terms') and not (overrides or {}).get('payment_terms'):
        o['payment_terms'] = [str(project['payment_terms'])]

    funding = []
    f = (overrides or {}).get('funding') or {}
    if f.get('amount'):
        funding.append({'label': f.get('label') or 'Microsoft Partner Funding (indicative, subject to approval)',
                        'amount': int(round(float(f['amount'])))})
    ms = (overrides or {}).get('managed_services') or None
    if ms and ms.get('monthly') and ms.get('months'):
        ms = {'label': ms.get('label') or 'Managed Data Platform Services (optional)',
              'monthly': int(round(float(ms['monthly']))), 'months': int(ms['months'])}
    else:
        ms = None

    return {
        'currency': 'USD',
        'source': {'project': project_name, 'version_no': version_no,
                   'rate_card': f"v{payload['rate_card_version']}" if payload.get('rate_card_version') else 'stored with the project',
                   'calc_mode': r.mode},
        'contract_value': float(r.contract_value.quantize(Decimal('0.01'))),
        'duration_weeks': weeks,
        'team': _team(r.lines, weeks),
        'otc_items': _spread(parts, r.contract_value),
        'funding': funding,
        'managed_services': ms,
        'consumption_note': o['consumption_note'],
        'payment_plan': o['payment_plan'],
        'payment_terms': o['payment_terms'],
        'tax_note': o['tax_note'],
    }


def pnl_context(commercials: dict) -> dict:
    """What the model may see: duration and team, no amounts."""
    return {'duration_weeks': commercials['duration_weeks'], 'team': commercials['team']}
