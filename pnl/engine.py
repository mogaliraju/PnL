"""The PnL calculation engine: the single source of every cost, price and margin figure.

    calculate(snapshot, mode=None) -> PnLResult

`snapshot` is a project payload as stored in `projects.payload` / `project_versions.payload`.
`mode` is 'legacy' or 'v2'; when omitted it comes from `snapshot['calc_mode']`, and a
snapshot without one is 'legacy' (every project that existed before the redesign).

Legacy mode reproduces the pre-redesign maths exactly (DESIGN.md 7.3):
    cost_basis     = resources + one-time costs (margin-bearing)
    list_price     = cost_basis / (1 - gross)            (0 when cost_basis is 0 or gross >= 100%)
    contract_value = list_price + licenses               (travel/infra/third-party and discount ignored)

v2 mode is the redesigned maths (DESIGN.md 7.2): add-ons count, with a per-item treatment
(apply margin or pass through), and the discount is taken off the list price (from AX margin).

All arithmetic is Decimal. Nothing is rounded here; `PnLResult.to_dict()` and the display
layer round. Percentages in PnLResult are 0-100; stored payload margins are fractions (0.40).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

LEGACY = 'legacy'
V2 = 'v2'
MODES = (LEGACY, V2)

ZERO = Decimal('0')
ONE = Decimal('1')
HUNDRED = Decimal('100')

# Legacy clamps each margin to [0, 0.99] (pnl_service._clamp_margin, unchanged behaviour).
LEGACY_MARGIN_MAX = Decimal('0.99')
LEGACY_DEFAULT_MARGIN = Decimal('0.40')

# v2 lever limits (DESIGN.md 5.3): each margin 0-95, Cloud4C + AX under 95, discount 0-50, FX > 0.
V2_MARGIN_MAX = Decimal('0.95')
V2_DISCOUNT_MAX = Decimal('0.50')

ADDON_KEYS = ('travel', 'infra', 'third_party')
ADDON_FIELDS = {'travel': 'travel_cost', 'infra': 'infra_cost', 'third_party': 'third_party_cost'}
# Open decision 2 in DESIGN.md 15: Travel passes through, Infra and Third-party take margin.
DEFAULT_ADDON_TREATMENT = {'travel': 'pass', 'infra': 'margin', 'third_party': 'margin'}


class EngineInputError(ValueError):
    """Raised in v2 mode when a lever is outside its allowed range. `errors` maps field -> message."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__('; '.join(f"{k}: {v}" for k, v in errors.items()))


def D(value, default: Decimal = ZERO) -> Decimal:
    """Decimal from anything stored in a payload; invalid or empty values become `default`."""
    if value is None or value == '':
        return default
    if isinstance(value, Decimal):
        return value
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default
    return d if d.is_finite() else default


# ── rate lookup ────────────────────────────────────────────────────────────────

def rate_for(rate_card: list, level, category: str = '') -> Decimal:
    """Hourly USD rate for a level from a stored rate card.

    Rate card entries are either {level, rates: {category: rate}} or the older flat
    {level, rate}. A category the entry doesn't list falls back to its first rate,
    and a level the card doesn't have is 0 (both as in the pre-redesign code).
    """
    item = next((rc for rc in (rate_card or []) if isinstance(rc, dict) and rc.get('level') == level), None)
    if item is None:
        return ZERO
    rates = item.get('rates')
    if isinstance(rates, dict) and rates:
        if category in rates:
            return D(rates[category])
        return D(next(iter(rates.values()), 0))
    return D(item.get('rate'))


# ── margins ────────────────────────────────────────────────────────────────────

def _clamp(value, default: Decimal, hi: Decimal = LEGACY_MARGIN_MAX) -> Decimal:
    if value is None:
        return default
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default
    if not d.is_finite():
        return default
    return max(ZERO, min(d, hi))


def resolve_margins(snapshot: dict | None) -> tuple[Decimal, Decimal]:
    """(cloud4c, ax) as fractions. Payloads saved before the Cloud4C/AX split only have
    `target_margin`; it counts as the Cloud4C margin with AX = 0."""
    snapshot = snapshot or {}
    legacy = _clamp(snapshot.get('target_margin', LEGACY_DEFAULT_MARGIN), LEGACY_DEFAULT_MARGIN)
    c4c, ax = snapshot.get('cloud4c_margin'), snapshot.get('ax_margin')
    if c4c is None and ax is None:
        return legacy, ZERO
    return _clamp(c4c, legacy), _clamp(ax, ZERO)


# ── other costs ────────────────────────────────────────────────────────────────

def is_pass_through_item(item) -> bool:
    """One-time cost rows that are licenses (passed through at cost, no margin)."""
    return isinstance(item, dict) and (bool(item.get('exclude_from_margin')) or item.get('category') == 'license')


def addon_treatment(snapshot: dict) -> dict[str, str]:
    stored = snapshot.get('addon_treatment') or {}
    return {k: (stored.get(k) if stored.get(k) in ('margin', 'pass') else DEFAULT_ADDON_TREATMENT[k])
            for k in ADDON_KEYS}


# ── result ─────────────────────────────────────────────────────────────────────

@dataclass
class ResourceLine:
    index: int
    category: str
    role: str
    level: str
    hours: Decimal
    rate: Decimal
    cost: Decimal


@dataclass
class PnLResult:
    mode: str
    hours: Decimal
    resources: Decimal            # sum of hours x rate
    one_time: Decimal             # one-time costs that take margin
    addons_margin: Decimal        # travel/infra/third-party priced with margin (v2 only)
    addons_pass: Decimal          # travel/infra/third-party passed through (v2 only)
    licenses: Decimal             # license rows, passed through at cost
    cost_basis: Decimal           # resources + one_time + addons_margin
    c4c_pct: Decimal
    ax_pct: Decimal
    gross_pct: Decimal
    list_price: Decimal           # cost_basis / (1 - gross)
    c4c_amount: Decimal
    ax_amount: Decimal
    markup: Decimal               # list_price - cost_basis
    discount_pct: Decimal         # applied discount (always 0 in legacy)
    discount: Decimal
    pass_through: Decimal         # licenses + addons_pass
    contract_value: Decimal       # list_price - discount + pass_through
    total_cost: Decimal           # cost_basis + pass_through
    ax_net_pct: Decimal           # AX margin after discount, % of discounted list price
    effective_pct: Decimal        # (contract_value - total_cost) / contract_value
    fx_rate: Decimal
    contract_inr: Decimal
    stored_discount_pct: Decimal  # the discount entered on the project, even when legacy ignores it
    lines: list[ResourceLine] = field(default_factory=list)

    @property
    def legacy_discounted_revenue(self) -> Decimal:
        """Revenue as the pre-redesign Version History showed it: contract value less the
        stored discount. Only used to keep that screen's numbers unchanged in legacy mode."""
        if self.mode != LEGACY or not self.stored_discount_pct:
            return self.contract_value
        return self.contract_value * (ONE - self.stored_discount_pct / HUNDRED)

    def to_dict(self) -> dict:
        """JSON-friendly figures: money rounded to cents, percentages to 0.01."""
        money = ('resources', 'one_time', 'addons_margin', 'addons_pass', 'licenses', 'cost_basis',
                 'list_price', 'c4c_amount', 'ax_amount', 'markup', 'discount', 'pass_through',
                 'contract_value', 'total_cost', 'contract_inr')
        pct = ('c4c_pct', 'ax_pct', 'gross_pct', 'discount_pct', 'ax_net_pct', 'effective_pct')
        out = {'mode': self.mode, 'hours': float(self.hours), 'fx_rate': float(self.fx_rate)}
        out.update({k: round(float(getattr(self, k)), 2) for k in money})
        out.update({k: round(float(getattr(self, k)), 2) for k in pct})
        out['lines'] = [{'index': l.index, 'category': l.category, 'role': l.role, 'level': l.level,
                         'hours': float(l.hours), 'rate': float(l.rate), 'cost': round(float(l.cost), 2)}
                        for l in self.lines]
        return out


# ── calculation ────────────────────────────────────────────────────────────────

def validate_v2_levers(c4c: Decimal, ax: Decimal, discount: Decimal, fx) -> dict[str, str]:
    errors = {}
    if not ZERO <= c4c <= V2_MARGIN_MAX:
        errors['cloud4c_margin'] = 'Cloud4C margin must be between 0% and 95%.'
    if not ZERO <= ax <= V2_MARGIN_MAX:
        errors['ax_margin'] = 'AX margin must be between 0% and 95%.'
    if 'cloud4c_margin' not in errors and 'ax_margin' not in errors and c4c + ax >= V2_MARGIN_MAX:
        errors['ax_margin'] = 'Cloud4C and AX margin together must stay below 95%.'
    if not ZERO <= discount <= V2_DISCOUNT_MAX:
        errors['discount_pct'] = 'Discount must be between 0% and 50%.'
    if fx is not None and fx <= ZERO:
        errors['fx_rate'] = 'The exchange rate must be above 0.'
    return errors


def calculate(snapshot: dict, mode: str | None = None) -> PnLResult:
    snapshot = snapshot or {}
    mode = mode or snapshot.get('calc_mode') or LEGACY
    if mode not in MODES:
        raise ValueError(f"Unknown calc mode {mode!r}")
    project = snapshot.get('project') or {}
    rate_card = snapshot.get('rate_card') or []

    lines, hours, resources = [], ZERO, ZERO
    for i, r in enumerate(snapshot.get('resources') or []):
        if not isinstance(r, dict):
            continue
        h = D(r.get('hours'))
        # A saved line may carry its own resolved rate (DESIGN.md 8.3); otherwise look it up.
        rate = D(r['rate_usd']) if r.get('rate_usd') not in (None, '') else rate_for(rate_card, r.get('level'), r.get('group', ''))
        cost = h * rate
        hours += h
        resources += cost
        lines.append(ResourceLine(i, r.get('group', '') or '', r.get('role', '') or '', r.get('level', '') or '', h, rate, cost))

    items = [x for x in (snapshot.get('one_time_costs') or []) if isinstance(x, dict)]
    one_time = sum((D(x.get('amount')) for x in items if not is_pass_through_item(x)), ZERO)
    licenses = sum((D(x.get('amount')) for x in items if is_pass_through_item(x)), ZERO)
    stored_discount = D(project.get('discount_pct'))
    fx = D(snapshot.get('fx_rate'))

    if mode == LEGACY:
        c4c, ax = resolve_margins(snapshot)
        addons_margin = addons_pass = ZERO
        discount_frac = ZERO
    else:
        c4c = D(snapshot.get('cloud4c_margin'), LEGACY_DEFAULT_MARGIN)
        ax = D(snapshot.get('ax_margin'))
        discount_frac = stored_discount / HUNDRED
        errors = validate_v2_levers(c4c, ax, discount_frac, fx if snapshot.get('fx_rate') not in (None, '') else None)
        if errors:
            raise EngineInputError(errors)
        treatment = addon_treatment(snapshot)
        addons_margin = sum((D(project.get(ADDON_FIELDS[k])) for k in ADDON_KEYS if treatment[k] == 'margin'), ZERO)
        addons_pass = sum((D(project.get(ADDON_FIELDS[k])) for k in ADDON_KEYS if treatment[k] == 'pass'), ZERO)

    cost_basis = resources + one_time + addons_margin
    gross = c4c + ax
    divisor = ONE - gross
    list_price = cost_basis / divisor if (cost_basis > ZERO and divisor > ZERO) else ZERO
    c4c_amount = list_price * c4c
    ax_amount = list_price * ax
    markup = list_price - cost_basis
    discount = list_price * discount_frac
    pass_through = licenses + addons_pass
    contract_value = list_price - discount + pass_through
    total_cost = cost_basis + pass_through
    net = list_price - discount
    ax_net_pct = (ax_amount - discount) / net * HUNDRED if net > ZERO else ax * HUNDRED
    effective_pct = (contract_value - total_cost) / contract_value * HUNDRED if contract_value > ZERO else ZERO

    return PnLResult(
        mode=mode, hours=hours, resources=resources, one_time=one_time,
        addons_margin=addons_margin, addons_pass=addons_pass, licenses=licenses,
        cost_basis=cost_basis, c4c_pct=c4c * HUNDRED, ax_pct=ax * HUNDRED, gross_pct=gross * HUNDRED,
        list_price=list_price, c4c_amount=c4c_amount, ax_amount=ax_amount, markup=markup,
        discount_pct=discount_frac * HUNDRED, discount=discount, pass_through=pass_through,
        contract_value=contract_value, total_cost=total_cost, ax_net_pct=ax_net_pct,
        effective_pct=effective_pct, fx_rate=fx, contract_inr=contract_value * fx,
        stored_discount_pct=stored_discount, lines=lines,
    )


def legacy_costs_dict(result: PnLResult) -> dict:
    """The dict shape the pre-redesign `compute_costs` returned (list, dashboard, versions,
    Excel template). For a legacy result the values are exactly what they always were; for a
    v2 result the same keys carry the v2 figures (pass-through includes add-ons passed through,
    margin-bearing one-time costs include add-ons priced with margin)."""
    def r2(d):
        return round(float(d), 2)

    def r4(d):
        return round(float(d), 4)

    gross = result.gross_pct / HUNDRED
    markup_pct = result.markup / result.cost_basis if result.cost_basis > ZERO else ZERO
    return {
        'input_cost':             r2(result.cost_basis),
        'total_cost':             r2(result.total_cost),
        'resource_input_cost':    r2(result.resources),
        'one_time_input_cost':    r2(result.one_time + result.addons_margin),
        'non_margin_cost':        r2(result.pass_through),
        'margin_basis_sell_cost': r2(result.list_price),
        'sell_cost':              r2(result.contract_value),
        'markup':                 r2(result.markup),
        'markup_pct':             r4(markup_pct),
        'gross_margin':           r4(gross),
        'effective_margin':       r4(gross),
        'cloud4c_margin':         r4(result.c4c_pct / HUNDRED),
        'ax_margin':              r4(result.ax_pct / HUNDRED),
    }
