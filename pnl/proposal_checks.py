"""Checks run on every generated proposal before anyone sends it (the verification step).

Each check returns {id, label, ok, detail}. They are deterministic: they read the model's
content, the commercials built from the PnL and the form, and never call a model.
"""
from __future__ import annotations

import json
import re

MONEY = re.compile(r'(\$|USD|INR|EUR|GBP|AED|SGD|₹|€|£)\s?\d|\d[\d,.]*\s?(USD|dollars|k USD)\b', re.I)
PLACEHOLDER = re.compile(r'\bCUSTOMER\b|<\s*Client\s*>|\[\s*(Client|Customer|Name)[^\]]*\]|\bXXX+\b|\bTBD\b|lorem ipsum', re.I)
WEEKS = re.compile(r'weeks?\s+(\d+)(?:\s*(?:to|-|and)\s*(\d+))?', re.I)
DASHES = re.compile('[–—]')
OTHER_BRAND = {'automatonsx': re.compile(r'cloud\s?4c', re.I), 'cloud4c': re.compile(r'automatons\s?x', re.I)}


def _texts(content: dict) -> list[str]:
    """Every string the model wrote, except the open questions (never printed)."""
    out = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k != 'open_questions':
                    walk(x)
    walk(content)
    return out


def _check(id_, label, ok, detail=''):
    return {'id': id_, 'label': label, 'ok': bool(ok), 'detail': detail}


def run_checks(intake: dict, content: dict, commercials: dict) -> list[dict]:
    texts = _texts(content)
    blob = '\n'.join(texts)
    results = []

    # 1. Prices come from the PnL and add up to its contract value.
    if intake.get('include_commercials', True):
        total = sum(i['amount'] for i in commercials.get('otc_items', []))
        cv = round(commercials.get('contract_value') or 0)
        results.append(_check('commercials', 'Commercials match the PnL contract value', total == cv,
                              f'One-time cost lines add up to {total:,}; the PnL version gives {cv:,}.'))

    # 2. The model wrote no prices.
    hits = sorted({m.group(0) for t in texts for m in MONEY.finditer(t)})[:5]
    results.append(_check('no_prices', 'No prices in the written sections', not hits,
                          'Found: ' + ', '.join(hits) if hits else ''))

    # 3. Timeline fits the plan's duration.
    weeks = commercials.get('duration_weeks') or 0
    ends = []
    for st in (content.get('timeline') or {}).get('stages', []):
        for m in WEEKS.finditer(st.get('timeline', '')):
            ends.append(int(m.group(2) or m.group(1)))
    last = max(ends) if ends else 0
    results.append(_check('timeline', f'Timeline fits the {weeks}-week plan', ends and last <= weeks,
                          f'The last stage ends in week {last}.' if ends else 'No week numbers found in the timeline.'))

    # 4. Client named, no placeholders, no other brand.
    client = intake.get('client', '')
    short = intake.get('client_short') or client
    summary = ' '.join(content.get('executive_summary') or [])
    results.append(_check('client_named', 'Executive summary names the client',
                          client.lower() in summary.lower() or short.lower() in summary.lower()))
    ph = sorted({m.group(0) for m in PLACEHOLDER.finditer(blob)})[:5]
    results.append(_check('placeholders', 'No placeholders left in', not ph, 'Found: ' + ', '.join(ph) if ph else ''))
    other = OTHER_BRAND[intake['brand']].search(blob)
    results.append(_check('brand', 'Only the chosen brand is mentioned', not other,
                          f'Mentions {other.group(0)}.' if other else ''))

    # 5. Sections the engagement and the form call for.
    missing = []
    if intake.get('engagement_type') == 'migration':
        if not (content.get('migration_mapping') or {}).get('rows'):
            missing.append('service mapping matrix')
        if not (content.get('inventory') or {}).get('rows'):
            missing.append('migration inventory')
    if 'project_governance' in (intake.get('extra_sections') or []) and not content.get('governance_cadence'):
        missing.append('project governance structure')
    if 'risks' in (intake.get('extra_sections') or []) and not content.get('risks'):
        missing.append('risk and mitigation')
    results.append(_check('sections', 'Required sections are present', not missing,
                          'Missing: ' + ', '.join(missing) if missing else ''))

    # 6. Inventory counts were given in the form, not invented.
    given = set()
    for v in ((intake.get('migration') or {}).get('inventory') or {}).values():
        given.add(str(v).replace(',', '').strip())
    for s in intake.get('sources') or []:
        given.update(re.findall(r'\d+', str(s.get('objects') or '')))
    given.update(re.findall(r'\d+', ' '.join(str(intake.get(k) or '') for k in ('brief', 'document_text', 'consumption'))))
    rows = (content.get('inventory') or {}).get('rows') or []
    invented = [f"{r['object_type']} ({r['count']})" for r in rows
                if re.sub(r'[^\d]', '', str(r.get('count'))) and re.sub(r'[^\d]', '', str(r.get('count'))) not in given]
    if rows:
        results.append(_check('inventory', 'Inventory counts come from the form or BRD', not invented,
                              'Not found in the inputs: ' + ', '.join(invented[:5]) if invented else ''))

    # 7. House style.
    d = sum(len(DASHES.findall(t)) for t in texts)
    results.append(_check('style', 'House style (no long dashes)', d == 0,
                          f'{d} long dash(es) in the model text; the document builder replaced them.' if d else ''))
    return results


def summary(checks: list[dict]) -> dict:
    return {'passed': sum(c['ok'] for c in checks), 'total': len(checks)}


def dumps(checks) -> str:
    return json.dumps(checks)
