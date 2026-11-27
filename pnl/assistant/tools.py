"""Tools the PnL assistant can call (DESIGN.md 9.4).

Every tool reads through `_ro()`, a connection that cannot write: on Postgres the session
runs with default_transaction_read_only=on, using ASSISTANT_DATABASE_URL (a SELECT-only
role, recommended) or DATABASE_URL. All figures come from pnl/engine.py. The only write any
tool makes is export_pnl_excel recording a one-time download link in export_token.

Project text (names, notes) is returned as data. The system prompt tells the model to treat
it as data, never as instructions.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from pnl import config, engine, vocab
from pnl.utils import storage

EXPORT_TTL_MINUTES = 15
MAX_LIST = 25


class ToolError(Exception):
    """A problem the model should see and work around (bad input, unknown project...)."""


# ── read-only data access ─────────────────────────────────────────────────

_RO_POOL = None


def _ro_pool():
    """Pooled read-only connections: every session runs with default_transaction_read_only=on."""
    global _RO_POOL
    if _RO_POOL is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        url = (os.environ.get('ASSISTANT_DATABASE_URL') or storage._DATABASE_URL).replace('postgres://', 'postgresql://', 1)
        _RO_POOL = ConnectionPool(url, min_size=0, max_size=4, max_idle=240, open=True,
                                  kwargs={'row_factory': dict_row, 'prepare_threshold': None,
                                          'options': '-c default_transaction_read_only=on'},
                                  check=ConnectionPool.check_connection)
    return _RO_POOL


@contextlib.contextmanager
def _ro():
    if storage._USE_POSTGRES:
        with _ro_pool().connection() as conn:
            conn.read_only = True
            yield conn
        return
    else:
        conn = sqlite3.connect(f"file:{storage.DB_FILE}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _q(conn, sql, params=()):
    return [dict(r) for r in conn.execute(storage._sql(sql), params).fetchall()]


def _load(raw):
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def _projects(conn, include_archived=False):
    feats = storage._features()
    cols = 'pid, name, customer, folder, saved_at, saved_by, payload' + (', archived_at' if feats['archive'] else '')
    where = '' if include_archived or not feats['archive'] else 'WHERE archived_at IS NULL'
    rows = _q(conn, f"SELECT {cols} FROM projects {where}")
    counts = {r['pid']: r['n'] for r in _q(conn, "SELECT pid, COUNT(*) AS n FROM project_versions GROUP BY pid")}
    for r in rows:
        r['payload'] = _load(r['payload'])
        r['version_count'] = counts.get(r['pid'], 0)
    return rows


def _versions(conn, pid):
    numbered = storage._features()['rate_cards']
    rows = _q(conn, f"SELECT vid, saved_at, saved_by, label, payload{', version_no' if numbered else ''} "
                    "FROM project_versions WHERE pid = ? ORDER BY saved_at, vid", (pid,))
    for i, r in enumerate(rows, start=1):
        r['payload'] = _load(r['payload'])
        r['version_no'] = r.get('version_no') or i
    return rows


def _fig(payload):
    try:
        r = engine.calculate(payload)
    except engine.EngineInputError as e:
        return {'error': f'Levers out of range: {e}'}
    d = r.to_dict()
    d.pop('lines', None)
    return d


def _brief(row):
    p = row['payload']
    pr = vocab.normalise_project(p.get('project') or {})
    f = _fig(p)
    return {
        'project_id': row['pid'], 'customer': pr.get('customer') or row.get('customer') or '',
        'name': (p.get('_meta') or {}).get('name') or row.get('name') or '',
        'status': pr.get('status'), 'stage': pr.get('stage'), 'business_unit': pr.get('business_unit') or '',
        'owner': pr.get('project_owner') or '', 'folder': row.get('folder') or '', 'location': pr.get('location') or '',
        'industry': pr.get('industry') or '', 'latest_version': row.get('version_count', 0),
        'calc_mode': p.get('calc_mode') or 'legacy', 'rate_card_version': p.get('rate_card_version'),
        'contract_value_usd': f.get('contract_value'), 'ax_margin_after_discount_pct': f.get('ax_net_pct'),
        'last_saved': str(row.get('saved_at') or ''), 'archived': bool(row.get('archived_at')),
    }


def _resolve(conn, ref, include_archived=True):
    """Find one project from an id or a name; ambiguity is an error the model must ask about."""
    ref = str(ref or '').strip()
    if not ref:
        raise ToolError('Name the project (its id, customer or project name).')
    rows = _projects(conn, include_archived)
    exact = [r for r in rows if r['pid'] == ref]
    if exact:
        return exact[0]
    low = ref.lower()
    hits = [r for r in rows if low in ' '.join(str(x or '') for x in (
        r['customer'], r['name'], (r['payload'].get('_meta') or {}).get('name'))).lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ToolError(f'No project matches "{ref}". Use search_projects to find it.')
    raise ToolError('Several projects match "%s": %s. Ask the user which one.' % (
        ref, '; '.join(f"{h['pid']} ({h['customer']}, {h['name']})" for h in hits[:8])))


def _version(conn, pid, number):
    vs = _versions(conn, pid)
    if number in (None, '', 'latest'):
        return None, vs
    try:
        n = int(number)
    except (TypeError, ValueError):
        raise ToolError('Versions are numbered 1, 2, 3 ...')
    for v in vs:
        if v['version_no'] == n:
            return v, vs
    raise ToolError(f'That project has versions 1 to {len(vs)}; there is no version {n}.' if vs else 'That project has no saved versions yet.')


def _snapshot(conn, ref, version):
    row = _resolve(conn, ref)
    v, vs = _version(conn, row['pid'], version)
    if v:
        label = f"version {v['version_no']}"
        return row, v['payload'], label, vs
    label = f"version {len(vs)} (latest)" if vs else 'unsaved draft'
    return row, row['payload'], label, vs


def _source(row, label, payload):
    rc = payload.get('rate_card_version')
    return [f"{row['payload'].get('project', {}).get('customer') or row['pid']} {label}",
            f"Rate card v{rc}" if rc else 'Rates stored with the project']


# ── tool handlers ─────────────────────────────────────────────────────────

def search_projects(query='', status=None, business_unit=None, owner=None, folder=None, location=None,
                    include_archived=False, limit=MAX_LIST):
    with _ro() as conn:
        rows = [_brief(r) for r in _projects(conn, include_archived)]
    words = [w for w in str(query or '').lower().split() if w]

    def keep(b):
        hay = ' '.join(str(b[k] or '') for k in ('customer', 'name', 'owner', 'folder', 'location', 'industry',
                                                    'business_unit', 'project_id')).lower()
        return all(w in hay for w in words) and all(
            not want or (b[k] or '') in want for k, want in
            (('status', status), ('business_unit', business_unit), ('owner', owner), ('folder', folder), ('location', location)))
    hits = sorted((b for b in rows if keep(b)), key=lambda b: b['last_saved'], reverse=True)
    lim = max(1, min(int(limit or MAX_LIST), 50))
    return {'count': len(hits), 'projects': hits[:lim], 'truncated': len(hits) > lim,
            '_sources': ['Project search, latest saved figures']}


def get_project(project, version=None):
    with _ro() as conn:
        row, p, label, vs = _snapshot(conn, project, version)
    pr = vocab.normalise_project(p.get('project') or {})
    try:
        r = engine.calculate(p).to_dict()
    except engine.EngineInputError as e:
        r = {'error': str(e)}
    return {
        'project_id': row['pid'], 'showing': label, 'versions_saved': len(vs),
        'details': {k: pr.get(k) for k in ('customer', 'status', 'stage', 'business_unit', 'project_owner', 'account_manager',
                                           'location', 'industry', 'project_type', 'delivery_model', 'billing_type',
                                           'currency', 'proposal_date', 'expected_start_date', 'expected_end_date',
                                           'discount_pct', 'travel_cost', 'infra_cost', 'third_party_cost')},
        'notes': {k: str(pr.get(k) or '')[:600] for k in ('project_description', 'risks', 'dependencies', 'next_action')},
        'levers': {'cloud4c_margin_pct': round(engine.D(p.get('cloud4c_margin')) * 100, 2) if p.get('cloud4c_margin') is not None else None,
                   'ax_margin_pct': round(engine.D(p.get('ax_margin')) * 100, 2) if p.get('ax_margin') is not None else None,
                   'fx_rate': p.get('fx_rate'), 'calc_mode': p.get('calc_mode') or 'legacy',
                   'rate_card_version': p.get('rate_card_version'), 'addon_treatment': p.get('addon_treatment')},
        'other_costs': [{'item': x.get('label'), 'amount_usd': x.get('amount'),
                         'pricing': 'pass-through' if engine.is_pass_through_item(x) else 'margin'}
                        for x in (p.get('one_time_costs') or []) if isinstance(x, dict)],
        'pnl': r,
        '_sources': _source(row, label, p),
    }


def list_versions(project):
    with _ro() as conn:
        row = _resolve(conn, project)
        vs = _versions(conn, row['pid'])
    out = []
    for v in vs:
        f = _fig(v['payload'])
        out.append({'version': v['version_no'], 'label': v.get('label') or '', 'saved_at': str(v['saved_at'] or ''),
                    'saved_by': v.get('saved_by') or '', 'rate_card_version': v['payload'].get('rate_card_version'),
                    'calc_mode': v['payload'].get('calc_mode') or 'legacy',
                    'cloud4c_margin_pct': f.get('c4c_pct'), 'ax_margin_pct': f.get('ax_pct'),
                    'discount_pct': f.get('discount_pct'), 'hours': f.get('hours'),
                    'contract_value_usd': f.get('contract_value'), 'ax_margin_after_discount_pct': f.get('ax_net_pct')})
    name = row['payload'].get('project', {}).get('customer') or row['pid']
    return {'project_id': row['pid'], 'versions': out, '_sources': [f"{name} v{v['version']}" for v in out][-6:]}


def _lines(p):
    out = {}
    for r in p.get('resources') or []:
        if isinstance(r, dict):
            k = (r.get('group') or '', r.get('role') or '', r.get('level') or '')
            out[k] = out.get(k, 0) + float(engine.D(r.get('hours')))
    return out


def _diff(a, b):
    fa, fb = _fig(a), _fig(b)
    keys = ('cost_basis', 'list_price', 'contract_value', 'c4c_pct', 'ax_pct', 'discount_pct', 'ax_net_pct', 'hours', 'pass_through')
    figures = {k: {'a': fa.get(k), 'b': fb.get(k),
                   'change': None if fa.get(k) is None or fb.get(k) is None else round(fb[k] - fa[k], 2)} for k in keys}
    la, lb = _lines(a), _lines(b)
    res = [{'category': k[0], 'role': k[1], 'level': k[2], 'hours_a': la.get(k, 0), 'hours_b': lb.get(k, 0)}
           for k in sorted(set(la) | set(lb)) if la.get(k, 0) != lb.get(k, 0)]
    other = []
    for k in ('calc_mode', 'rate_card_version'):
        if (a.get(k) or None) != (b.get(k) or None):
            other.append({'field': k, 'a': a.get(k), 'b': b.get(k)})
    return {'figures': figures, 'resource_changes': res, 'other_changes': other}


def compare_versions(project, version_a, version_b):
    with _ro() as conn:
        row, a, la, _ = _snapshot(conn, project, version_a)
        _, b, lb, _ = _snapshot(conn, row['pid'], version_b)
    out = _diff(a, b)
    out.update({'project_id': row['pid'], 'a': la, 'b': lb,
                '_sources': _source(row, la, a)[:1] + _source(row, lb, b)[:1]})
    return out


def compare_projects(project_a, project_b):
    with _ro() as conn:
        ra, a, la, _ = _snapshot(conn, project_a, None)
        rb, b, lb, _ = _snapshot(conn, project_b, None)
    out = _diff(a, b)
    out.update({'a': _brief(ra), 'b': _brief(rb), '_sources': _source(ra, la, a)[:1] + _source(rb, lb, b)[:1]})
    return out


def _card_payload(conn, version):
    if not storage._features()['rate_cards']:
        raise ToolError('Versioned rate cards are not set up on this database.')
    card = (_q(conn, "SELECT id, version FROM rate_card WHERE version = ?", (int(version),)) if version
            else _q(conn, "SELECT id, version FROM rate_card WHERE status = 'published'"))
    if not card:
        raise ToolError(f'There is no rate card v{version}.' if version else 'No rate card is published.')
    rows = _q(conn, """SELECT l.code, c.name, r.rate_usd FROM rate_card_rate r JOIN level l ON l.id = r.level_id
                       JOIN role_category c ON c.id = r.category_id WHERE r.rate_card_id = ? AND r.rate_usd IS NOT NULL
                       ORDER BY l.sort_order, c.sort_order""", (card[0]['id'],))
    out = {}
    for r in rows:
        out.setdefault(r['code'], {})[r['name']] = float(r['rate_usd'])
    return card[0]['version'], [{'level': k, 'rates': v} for k, v in out.items()]


def apply_overrides(conn, payload, overrides):
    """A copy of `payload` with scenario overrides applied. Nothing is saved."""
    p = json.loads(json.dumps(payload))
    o = overrides or {}
    allowed = {'c4c_pct', 'ax_pct', 'discount_pct', 'fx_rate', 'rate_card_version', 'hours_scale', 'calc_mode'}
    unknown = set(o) - allowed
    if unknown:
        raise ToolError(f'Unknown overrides: {", ".join(sorted(unknown))}. Allowed: {", ".join(sorted(allowed))}.')

    def num(k, lo, hi):
        try:
            v = float(o[k])
        except (TypeError, ValueError):
            raise ToolError(f'{k} must be a number.')
        if not lo <= v <= hi:
            raise ToolError(f'{k} must be between {lo} and {hi}.')
        return v
    if 'c4c_pct' in o:
        p['cloud4c_margin'] = num('c4c_pct', 0, 95) / 100
    if 'ax_pct' in o:
        p['ax_margin'] = num('ax_pct', 0, 95) / 100
    if 'discount_pct' in o:
        p.setdefault('project', {})['discount_pct'] = num('discount_pct', 0, 50)
    if 'fx_rate' in o:
        p['fx_rate'] = num('fx_rate', 0.0001, 100000)
    if 'hours_scale' in o:
        s = num('hours_scale', 0, 10)
        for r in p.get('resources') or []:
            if isinstance(r, dict):
                r['hours'] = round(float(engine.D(r.get('hours'))) * s, 2)
    if 'calc_mode' in o:
        if o['calc_mode'] not in engine.MODES:
            raise ToolError('calc_mode is legacy or v2.')
        p['calc_mode'] = o['calc_mode']
    if 'rate_card_version' in o:
        v, card = _card_payload(conn, o['rate_card_version'])
        p['rate_card'], p['rate_card_version'] = card, v
    return p


def calculate_scenario(project, overrides, version=None):
    with _ro() as conn:
        row, base, label, _ = _snapshot(conn, project, version)
        scen = apply_overrides(conn, base, overrides)
    before, after = _fig(base), _fig(scen)
    if 'error' in after:
        raise ToolError(after['error'])
    return {'project_id': row['pid'], 'based_on': label, 'overrides': overrides, 'saved': False,
            'before': before, 'after': after,
            'contract_value_change_usd': round(after['contract_value'] - before.get('contract_value', 0), 2),
            'meets_ax_target': after['ax_net_pct'] >= config.AX_MARGIN_GOOD,
            '_scenario': {'project_id': row['pid'], 'overrides': overrides},
            '_sources': _source(row, label, base)[:1] + ['PnL calculator (scenario, not saved)']}


def get_rate_card(version=None, category=None):
    with _ro() as conn:
        v, card = _card_payload(conn, version)
    if category:
        card = [{'level': e['level'], 'rate_usd': e['rates'].get(category)} for e in card if category in e['rates']]
        if not card:
            raise ToolError(f'Rate card v{v} has no category "{category}".')
    return {'rate_card_version': v, 'rates_usd_per_hour': card, '_sources': [f'Rate card v{v}']}


def portfolio_summary(status=None, business_unit=None, owner=None, folder=None, location=None):
    res = search_projects('', status, business_unit, owner, folder, location, limit=50)
    with _ro() as conn:
        rows = [_brief(r) for r in _projects(conn)]
    rows = [b for b in rows if all(not want or (b[k] or '') in want for k, want in
            (('status', status), ('business_unit', business_unit), ('owner', owner), ('folder', folder), ('location', location)))]
    by = {}
    for b in rows:
        s = by.setdefault(b['status'], {'projects': 0, 'contract_value_usd': 0.0})
        s['projects'] += 1
        s['contract_value_usd'] = round(s['contract_value_usd'] + (b['contract_value_usd'] or 0), 2)
    priced = [b for b in rows if b['status'] != 'Lost' and (b['contract_value_usd'] or 0) > 0]
    below = sorted((b for b in priced if b['status'] in ('Draft', 'Submitted', 'On hold')
                    and b['ax_margin_after_discount_pct'] < config.AX_MARGIN_GOOD), key=lambda b: b['ax_margin_after_discount_pct'])
    del res
    return {'projects': len(rows), 'by_status': by,
            'average_ax_margin_after_discount_pct': round(sum(b['ax_margin_after_discount_pct'] for b in priced) / len(priced), 2) if priced else None,
            'ax_target_pct': config.AX_MARGIN_GOOD,
            'open_below_target': [{k: b[k] for k in ('project_id', 'customer', 'name', 'status', 'ax_margin_after_discount_pct',
                                                     'contract_value_usd')} for b in below],
            '_sources': ['All projects, latest saved figures']}


def export_pnl_excel(project, version=None, scenario_overrides=None, *, username=''):
    with _ro() as conn:
        row, payload, label, _ = _snapshot(conn, project, version)
        if scenario_overrides:
            apply_overrides(conn, payload, scenario_overrides)          # validate now, apply at download
        vid = None
        if version not in (None, '', 'latest'):
            vid = _version(conn, row['pid'], version)[0]['vid']
    customer = (payload.get('project') or {}).get('customer') or row['pid']
    suffix = f" v{version}" if version not in (None, '', 'latest') else ''
    filename = f"{customer} PnL{suffix}{' scenario' if scenario_overrides else ''}.xlsx"
    token = secrets.token_urlsafe(24)
    with storage._connect() as conn:
        storage._execute(conn, """INSERT INTO export_token(token, username, project_id, version_id, overrides, filename, expires_at)
                                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (token, username, row['pid'], vid, json.dumps(scenario_overrides or {}), filename,
                          datetime.now(timezone.utc) + timedelta(minutes=EXPORT_TTL_MINUTES)))
        conn.commit()
    return {'filename': filename, 'download_url': f'/api/exports/{token}', 'expires_in_minutes': EXPORT_TTL_MINUTES,
            'based_on': label, '_file': {'filename': filename, 'url': f'/api/exports/{token}'},
            '_sources': _source(row, label, payload)[:1]}


# ── definitions sent to the model ─────────────────────────────────────────

def _obj(props, required=()):
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}


_LIST = {'type': 'array', 'items': {'type': 'string'}}
_PROJECT = {'type': 'string', 'description': 'Project id, or a customer or project name.'}
_VERSION = {'type': 'integer', 'description': 'Version number (1 = first save). Leave out for the latest.'}
_OVERRIDES = _obj({
    'c4c_pct': {'type': 'number', 'description': 'Cloud4C margin %, 0-95'},
    'ax_pct': {'type': 'number', 'description': 'AX margin %, 0-95'},
    'discount_pct': {'type': 'number', 'description': 'Discount %, 0-50'},
    'fx_rate': {'type': 'number', 'description': 'USD to INR rate'},
    'rate_card_version': {'type': 'integer', 'description': 'Price with this rate card version'},
    'hours_scale': {'type': 'number', 'description': 'Multiply every resource line\'s hours, e.g. 0.9'},
    'calc_mode': {'type': 'string', 'enum': ['legacy', 'v2']},
})

TOOLS = {
    'search_projects': (search_projects, 'Find projects by words in customer, project name, owner, folder, location or industry, with optional exact filters. Returns latest saved figures.',
                        _obj({'query': {'type': 'string'}, 'status': _LIST, 'business_unit': _LIST, 'owner': _LIST, 'folder': _LIST,
                              'location': _LIST, 'include_archived': {'type': 'boolean'}, 'limit': {'type': 'integer'}})),
    'get_project': (get_project, 'One project\'s details, levers, other costs and full calculated PnL, for its latest saved version or a given version.',
                    _obj({'project': _PROJECT, 'version': _VERSION}, ['project'])),
    'list_versions': (list_versions, 'Every saved version of a project with label, author, rate card and key figures.',
                      _obj({'project': _PROJECT}, ['project'])),
    'compare_versions': (compare_versions, 'Differences between two saved versions of one project: figures, resource hours, calculation mode and rate card.',
                         _obj({'project': _PROJECT, 'version_a': _VERSION, 'version_b': _VERSION}, ['project', 'version_a', 'version_b'])),
    'compare_projects': (compare_projects, 'Compare the latest saved versions of two projects.',
                         _obj({'project_a': _PROJECT, 'project_b': _PROJECT}, ['project_a', 'project_b'])),
    'calculate_scenario': (calculate_scenario, 'What-if: recalculate a project with changed levers, rate card or hours. Nothing is saved.',
                           _obj({'project': _PROJECT, 'version': _VERSION, 'overrides': _OVERRIDES}, ['project', 'overrides'])),
    'get_rate_card': (get_rate_card, 'Hourly USD rates by level and category for a rate card version (default: the published one).',
                      _obj({'version': {'type': 'integer'}, 'category': {'type': 'string'}})),
    'portfolio_summary': (portfolio_summary, 'Totals by status, average AX margin after discount, and open projects below the AX target, with optional filters.',
                          _obj({'status': _LIST, 'business_unit': _LIST, 'owner': _LIST, 'folder': _LIST, 'location': _LIST})),
    'export_pnl_excel': (export_pnl_excel, 'Create a one-time Excel download (Benline template) of a project version or a what-if scenario. Returns a link valid for 15 minutes.',
                         _obj({'project': _PROJECT, 'version': _VERSION, 'scenario_overrides': _OVERRIDES}, ['project'])),
}


def tool_config() -> dict:
    """Bedrock Converse toolConfig for the nine tools."""
    return {'tools': [{'toolSpec': {'name': n, 'description': d, 'inputSchema': {'json': s}}} for n, (_, d, s) in TOOLS.items()]}


def _check(schema, value, path='input'):
    """Validate a model-supplied tool input against its schema before running the tool."""
    t = schema.get('type')
    if t == 'object':
        if not isinstance(value, dict):
            raise ToolError(f'{path} must be an object.')
        extra = set(value) - set(schema['properties'])
        if extra:
            raise ToolError(f'{path} has unknown fields: {", ".join(sorted(extra))}.')
        for k in schema.get('required', []):
            if k not in value:
                raise ToolError(f'{path}.{k} is required.')
        for k, v in value.items():
            if v is not None:
                _check(schema['properties'][k], v, f'{path}.{k}')
    elif t == 'array':
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ToolError(f'{path} must be a list of strings.')
    elif t == 'string':
        if not isinstance(value, str):
            raise ToolError(f'{path} must be text.')
        if 'enum' in schema and value not in schema['enum']:
            raise ToolError(f'{path} must be one of {schema["enum"]}.')
    elif t == 'integer':
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolError(f'{path} must be a whole number.')
    elif t == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolError(f'{path} must be a number.')
    elif t == 'boolean' and not isinstance(value, bool):
        raise ToolError(f'{path} must be true or false.')


def run(name: str, args, username: str = '') -> dict:
    if name not in TOOLS:
        raise ToolError(f'There is no tool called {name}.')
    fn, _, schema = TOOLS[name]
    _check(schema, args)
    kwargs = {k: v for k, v in args.items() if v is not None}
    if name == 'export_pnl_excel':
        kwargs['username'] = username
    return fn(**kwargs)
