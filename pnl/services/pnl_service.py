"""Core PnL calculation logic."""


def _get_rate(rc_item: dict, group: str) -> float:
    """Get the rate for a level item, preferring the resource's group.
    Handles both new format {rates: {group: value}} and old flat {rate: value}."""
    rates = rc_item.get('rates')
    if isinstance(rates, dict) and rates:
        if group in rates:
            return float(rates[group] or 0)
        # Fall back to first available rate
        return float(next(iter(rates.values()), 0) or 0)
    # Backward compat: flat rate field
    return float(rc_item.get('rate', 0) or 0)


def _build_rate_lookup(rate_card: list, group: str) -> dict:
    """Build level→rate dict for a specific group."""
    return {rc['level']: _get_rate(rc, group) for rc in rate_card if rc.get('level')}


def compute_costs(resources: list, rate_card: list, target_margin: float = 0.40) -> dict:
    input_cost = sum(
        (r.get('hours') or 0) * _get_rate(
            next((rc for rc in rate_card if rc.get('level') == r.get('level')), {}),
            r.get('group', '')
        )
        for r in resources
    )
    divisor      = 1.0 - max(0.0, min(target_margin, 0.99))
    sell_cost    = input_cost / divisor if input_cost > 0 else 0
    markup       = sell_cost - input_cost
    markup_pct   = markup / input_cost if input_cost > 0 else 0
    gross_margin = markup / sell_cost  if sell_cost  > 0 else 0

    return {
        'input_cost':   round(input_cost,   2),
        'sell_cost':    round(sell_cost,    2),
        'markup':       round(markup,       2),
        'markup_pct':   round(markup_pct,   4),
        'gross_margin': round(gross_margin, 4),
    }


def compare_versions(v1: dict, v2: dict) -> dict:
    """Return a structured diff between two project snapshots."""
    c1 = compute_costs(v1.get('resources', []), v1.get('rate_card', []))
    c2 = compute_costs(v2.get('resources', []), v2.get('rate_card', []))

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
