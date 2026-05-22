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


def _sum_one_time_costs(items: list | None) -> float:
    total = 0.0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            total += float(item.get('amount') or 0)
        except (TypeError, ValueError):
            continue
    return total


def _is_non_margin_cost(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(item.get('exclude_from_margin')) or item.get('category') == 'license'


def _sum_margin_included_one_time_costs(items: list | None) -> float:
    return _sum_one_time_costs(
        [item for item in (items or []) if not _is_non_margin_cost(item)]
    )


def _sum_non_margin_costs(items: list | None) -> float:
    return _sum_one_time_costs(
        [item for item in (items or []) if _is_non_margin_cost(item)]
    )


def _clamp_margin(value, default=0.0) -> float:
    try:
        margin = float(value)
    except (TypeError, ValueError):
        margin = default
    return max(0.0, min(margin, 0.99))


def resolve_margin_inputs(payload: dict | None) -> tuple[float, float]:
    payload = payload or {}
    legacy_margin = _clamp_margin(payload.get('target_margin', 0.40), 0.40)
    cloud4c_margin = payload.get('cloud4c_margin')
    ax_margin = payload.get('ax_margin')

    if cloud4c_margin is None and ax_margin is None:
        # Legacy projects stored one margin only. Preserve old behavior by
        # treating it as the Cloud4C margin with no AX uplift.
        return legacy_margin, 0.0

    return _clamp_margin(cloud4c_margin, legacy_margin), _clamp_margin(ax_margin, 0.0)


def effective_margin(cloud4c_margin: float, ax_margin: float) -> float:
    return _clamp_margin(cloud4c_margin) + _clamp_margin(ax_margin)


def compute_costs(
    resources: list,
    rate_card: list,
    target_margin: float = 0.40,
    cloud4c_margin: float | None = None,
    ax_margin: float | None = None,
    one_time_costs: list | None = None,
) -> dict:
    resource_input_cost = sum(
        (r.get('hours') or 0) * _get_rate(
            next((rc for rc in rate_card if rc.get('level') == r.get('level')), {}),
            r.get('group', '')
        )
        for r in resources
    )
    one_time_input_cost = _sum_margin_included_one_time_costs(one_time_costs)
    non_margin_cost = _sum_non_margin_costs(one_time_costs)
    input_cost = resource_input_cost + one_time_input_cost
    total_cost = input_cost + non_margin_cost
    if cloud4c_margin is None and ax_margin is None:
        cloud4c_margin = _clamp_margin(target_margin, 0.40)
        ax_margin = 0.0
    else:
        cloud4c_margin = _clamp_margin(cloud4c_margin, _clamp_margin(target_margin, 0.40))
        ax_margin = _clamp_margin(ax_margin, 0.0)

    combined_margin = cloud4c_margin + ax_margin
    combined_divisor = 1.0 - combined_margin
    sell_cost    = input_cost / combined_divisor if (input_cost > 0 and combined_divisor > 0) else 0
    markup       = sell_cost - input_cost
    markup_pct   = markup / input_cost if input_cost > 0 else 0
    gross_margin = combined_margin  # markup / sell_cost == combined_margin by definition

    return {
        'input_cost':          round(input_cost, 2),
        'total_cost':          round(total_cost, 2),
        'resource_input_cost': round(resource_input_cost, 2),
        'one_time_input_cost': round(one_time_input_cost, 2),
        'non_margin_cost':     round(non_margin_cost, 2),
        'sell_cost':           round(sell_cost, 2),
        'markup':              round(markup, 2),
        'markup_pct':          round(markup_pct, 4),
        'gross_margin':        round(gross_margin, 4),
        'effective_margin':    round(gross_margin, 4),
        'cloud4c_margin':      round(cloud4c_margin, 4),
        'ax_margin':           round(ax_margin, 4),
    }


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
