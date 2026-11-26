"""PnL figures for the existing screens.

All arithmetic lives in pnl/engine.py. These functions keep the pre-redesign call
signatures and return shapes so the list, dashboard, version history, compare and
Excel export keep working unchanged; they run the engine in legacy mode.
"""
from pnl import engine


def _get_rate(rc_item: dict, group: str) -> float:
    """Rate for one rate-card entry (kept for callers that need a single lookup)."""
    return float(engine.rate_for([rc_item], rc_item.get('level'), group)) if isinstance(rc_item, dict) else 0.0


def resolve_margin_inputs(payload: dict | None) -> tuple[float, float]:
    c4c, ax = engine.resolve_margins(payload)
    return float(c4c), float(ax)


def effective_margin(cloud4c_margin: float, ax_margin: float) -> float:
    return float(engine._clamp(cloud4c_margin, engine.ZERO) + engine._clamp(ax_margin, engine.ZERO))


def compute_costs(
    resources: list,
    rate_card: list,
    target_margin: float = 0.40,
    cloud4c_margin: float | None = None,
    ax_margin: float | None = None,
    one_time_costs: list | None = None,
) -> dict:
    """Legacy-mode figures in the original dict shape (input_cost, sell_cost, markup, ...)."""
    snapshot = {
        'resources': resources or [],
        'rate_card': rate_card or [],
        'one_time_costs': one_time_costs or [],
        'target_margin': target_margin,
        'cloud4c_margin': cloud4c_margin,
        'ax_margin': ax_margin,
    }
    return engine.legacy_costs_dict(engine.calculate(snapshot, engine.LEGACY))


def legacy_version_revenue(payload: dict) -> float:
    """Revenue as Version History has always shown it (sell cost less the stored discount)."""
    return round(float(engine.calculate(payload, engine.LEGACY).legacy_discounted_revenue), 2)


def compare_versions(v1: dict, v2: dict) -> dict:
    """Return a structured diff between two project snapshots."""
    c4c_1, ax_1 = resolve_margin_inputs(v1)
    c4c_2, ax_2 = resolve_margin_inputs(v2)
    c1 = compute_costs(
        v1.get('resources', []),
        v1.get('rate_card', []),
        cloud4c_margin=c4c_1,
        ax_margin=ax_1,
        one_time_costs=v1.get('one_time_costs', []),
    )
    c2 = compute_costs(
        v2.get('resources', []),
        v2.get('rate_card', []),
        cloud4c_margin=c4c_2,
        ax_margin=ax_2,
        one_time_costs=v2.get('one_time_costs', []),
    )

    def delta(a, b):
        return round(b - a, 2)

    def pct_delta(a, b):
        if a == 0:
            return None
        return round((b - a) / abs(a) * 100, 1)

    res1 = {r.get('role', ''): r for r in v1.get('resources', [])}
    res2 = {r.get('role', ''): r for r in v2.get('resources', [])}
    all_roles = sorted(set(list(res1) + list(res2)))

    resource_changes = []
    for role in all_roles:
        r1 = res1.get(role)
        r2 = res2.get(role)
        if r1 and r2:
            h_delta = (r2.get('hours', 0) or 0) - (r1.get('hours', 0) or 0)
            if h_delta != 0 or r1.get('level') != r2.get('level'):
                resource_changes.append({
                    'role': role, 'status': 'changed',
                    'hours_v1': r1.get('hours', 0), 'hours_v2': r2.get('hours', 0),
                    'hours_delta': h_delta,
                    'level_v1': r1.get('level'), 'level_v2': r2.get('level'),
                })
        elif r1:
            resource_changes.append({'role': role, 'status': 'removed',
                                     'hours_v1': r1.get('hours', 0), 'hours_v2': 0})
        else:
            resource_changes.append({'role': role, 'status': 'added',
                                     'hours_v1': 0, 'hours_v2': r2.get('hours', 0)})

    return {
        'v1_meta': v1.get('_meta', {}),
        'v2_meta': v2.get('_meta', {}),
        'costs': {
            'input_cost':   {'v1': c1['input_cost'],  'v2': c2['input_cost'],
                             'delta': delta(c1['input_cost'],  c2['input_cost']),
                             'pct':   pct_delta(c1['input_cost'],  c2['input_cost'])},
            'sell_cost':    {'v1': c1['sell_cost'],   'v2': c2['sell_cost'],
                             'delta': delta(c1['sell_cost'],   c2['sell_cost']),
                             'pct':   pct_delta(c1['sell_cost'],   c2['sell_cost'])},
            'markup':       {'v1': c1['markup'],      'v2': c2['markup'],
                             'delta': delta(c1['markup'],      c2['markup']),
                             'pct':   pct_delta(c1['markup'],      c2['markup'])},
            'gross_margin': {'v1': round(c1['gross_margin']*100, 1),
                             'v2': round(c2['gross_margin']*100, 1),
                             'delta': round((c2['gross_margin']-c1['gross_margin'])*100, 1)},
        },
        'resource_changes': resource_changes,
        'has_changes': bool(resource_changes) or c1 != c2,
    }
