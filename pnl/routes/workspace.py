"""Project workspace API (DESIGN.md 5.3): options, live calculation, version compare."""
from flask import Blueprint, jsonify, request

from pnl import config, engine, vocab
from pnl.utils.auth import login_required
from pnl.utils.storage import load_global_settings, load_project_record, load_project_version, load_users

bp = Blueprint('workspace', __name__)


@bp.route('/api/workspace/options', methods=['GET'])
@login_required
def options():
    settings = load_global_settings()
    people = sorted(({'username': u, 'name': d.get('name') or u} for u, d in load_users().items()),
                    key=lambda p: p['name'].lower())
    return jsonify({
        'statuses': vocab.STATUSES, 'stages': vocab.STAGES, 'priorities': vocab.PRIORITIES,
        'delivery_models': vocab.DELIVERY_MODELS, 'billing_types': vocab.BILLING_TYPES,
        'currencies': vocab.CURRENCIES, 'license_types': vocab.LICENSE_TYPES,
        'industries': vocab.INDUSTRIES, 'project_types': vocab.PROJECT_TYPES, 'countries': vocab.COUNTRIES,
        'business_units': settings.get('business_units') or ['EDM', 'AI', 'SAP', 'RPA'],
        'people': people,
        'thresholds': {'good': config.AX_MARGIN_GOOD, 'warn': config.AX_MARGIN_WARN},
        'limits': {'margin_max': float(engine.V2_MARGIN_MAX) * 100, 'discount_max': float(engine.V2_DISCOUNT_MAX) * 100},
        'addon_defaults': engine.DEFAULT_ADDON_TREATMENT,
    })


def _calc(snapshot, mode=None):
    try:
        return engine.calculate(snapshot, mode).to_dict(), None
    except engine.EngineInputError as e:
        return None, e.errors


@bp.route('/api/pnl/calculate', methods=['POST'])
@login_required
def calculate():
    """Figures for a snapshot that may not be saved yet. Body: {snapshot, mode?, compare_mode?}."""
    body = request.get_json(silent=True) or {}
    snapshot = body.get('snapshot')
    if not isinstance(snapshot, dict):
        return jsonify({'error': 'Send the project as snapshot.'}), 400
    mode = body.get('mode') if body.get('mode') in engine.MODES else None
    result, errors = _calc(snapshot, mode)
    if errors:
        return jsonify({'error': 'Some levers are out of range.', 'errors': errors}), 422
    out = {'result': result}
    other = body.get('compare_mode')
    if other in engine.MODES:
        out['compare'], out['compare_errors'] = _calc(snapshot, other)
    return jsonify(out)


def _snapshot(pid, ref):
    if ref in (None, '', 'current'):
        return load_project_record(pid)
    return load_project_version(pid, ref)


@bp.route('/api/projects/<pid>/compare', methods=['GET'])
@login_required
def compare(pid):
    a, b = _snapshot(pid, request.args.get('a')), _snapshot(pid, request.args.get('b'))
    if a is None or b is None:
        return jsonify({'error': 'One of those versions no longer exists.'}), 404
    ra, ea = _calc(a)
    rb, eb = _calc(b)

    def lines(p):
        out = {}
        for r in p.get('resources') or []:
            if isinstance(r, dict):
                key = (r.get('group') or '', r.get('role') or '', r.get('level') or '')
                out[key] = out.get(key, 0) + float(engine.D(r.get('hours')))
        return out
    la, lb = lines(a), lines(b)
    changes = []
    for key in sorted(set(la) | set(lb)):
        x, y = la.get(key, 0), lb.get(key, 0)
        if x != y:
            changes.append({'category': key[0], 'role': key[1], 'level': key[2], 'hours_a': x, 'hours_b': y,
                            'status': 'added' if not x else 'removed' if not y else 'changed'})
    return jsonify({'a': ra, 'b': rb, 'errors_a': ea, 'errors_b': eb, 'resource_changes': changes,
                    'levers': {k: [a.get(k), b.get(k)] for k in ('cloud4c_margin', 'ax_margin', 'fx_rate', 'calc_mode', 'rate_card_version')},
                    'discount': [(a.get('project') or {}).get('discount_pct'), (b.get('project') or {}).get('discount_pct')]})
