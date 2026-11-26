"""Tests for pnl/engine.py (DESIGN.md 7.4)."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from pnl import engine
from pnl.engine import LEGACY, V2, EngineInputError, calculate, legacy_costs_dict

FIXTURES = json.loads((Path(__file__).parent / 'fixtures' / 'legacy_parity.json').read_text(encoding='utf-8'))

RATE_CARD = [
    {'level': 'L1', 'rates': {'Data': 20, 'BI': 18}},
    {'level': 'L2', 'rates': {'Data': 30, 'BI': 26}},
    {'level': 'L3', 'rate': 45},                       # older flat entry
]


def snap(resources=(), one_time=(), c4c=0.40, ax=0.12, discount=0, fx=89.4, mode=None, **project):
    s = {
        'resources': list(resources),
        'rate_card': RATE_CARD,
        'one_time_costs': list(one_time),
        'cloud4c_margin': c4c,
        'ax_margin': ax,
        'fx_rate': fx,
        'project': {'discount_pct': discount, **project},
    }
    if mode:
        s['calc_mode'] = mode
    return s


def res(group, level, hours):
    return {'group': group, 'role': 'Role', 'level': level, 'hours': hours}


class TestLegacyParity(unittest.TestCase):
    """Ten anonymised production projects must give exactly what the pre-redesign code gave."""

    def test_fixtures_match_pre_redesign_figures(self):
        self.assertEqual(len(FIXTURES['fixtures']), 10)
        for fx in FIXTURES['fixtures']:
            with self.subTest(fx['name'], tags=fx['tags']):
                r = calculate(fx['snapshot'], LEGACY)
                got = legacy_costs_dict(r)
                exp = fx['expected']
                for key in ('input_cost', 'total_cost', 'resource_input_cost', 'one_time_input_cost',
                            'non_margin_cost', 'margin_basis_sell_cost', 'sell_cost', 'markup'):
                    self.assertAlmostEqual(got[key], exp[key], delta=0.01, msg=key)
                for key in ('cloud4c_margin', 'ax_margin', 'gross_margin'):
                    self.assertAlmostEqual(got[key], exp[key], places=4, msg=key)
                self.assertAlmostEqual(float(r.legacy_discounted_revenue), exp['revenue_after_discount'], delta=0.01)
                self.assertAlmostEqual(float(r.hours), exp['total_hours'], places=3)

    def test_legacy_is_the_default_mode(self):
        self.assertEqual(calculate(snap([res('Data', 'L1', 10)])).mode, LEGACY)
        self.assertEqual(calculate(snap([res('Data', 'L1', 10)], mode=V2)).mode, V2)

    def test_legacy_ignores_addons_and_discount(self):
        s = snap([res('Data', 'L1', 100)], discount=10, travel_cost=5000, infra_cost=1000)
        r = calculate(s, LEGACY)
        self.assertEqual(r.cost_basis, Decimal('2000'))
        self.assertEqual(r.discount, 0)
        self.assertEqual(r.addons_margin + r.addons_pass, 0)
        self.assertAlmostEqual(float(r.contract_value), 2000 / 0.48, places=6)
        # Version History applied the stored discount on top; that number is kept for legacy only
        self.assertAlmostEqual(float(r.legacy_discounted_revenue), 2000 / 0.48 * 0.9, places=6)

    def test_legacy_target_margin_only_payload(self):
        s = {'resources': [res('Data', 'L2', 10)], 'rate_card': RATE_CARD, 'target_margin': 0.35}
        r = calculate(s, LEGACY)
        self.assertEqual(r.c4c_pct, Decimal('35.00'))
        self.assertEqual(r.ax_pct, 0)

    def test_legacy_margins_clamped_to_99_percent(self):
        r = calculate(snap([res('Data', 'L1', 10)], c4c=1.5, ax=0.6), LEGACY)
        self.assertEqual(r.c4c_pct, Decimal('99'))
        self.assertEqual(r.list_price, 0)   # combined margin >= 100% gives no price, as before


class TestRates(unittest.TestCase):
    def test_category_rate(self):
        self.assertEqual(engine.rate_for(RATE_CARD, 'L2', 'BI'), Decimal('26'))

    def test_unknown_category_falls_back_to_first_rate(self):
        self.assertEqual(engine.rate_for(RATE_CARD, 'L2', 'Unknown'), Decimal('30'))

    def test_flat_rate_entry(self):
        self.assertEqual(engine.rate_for(RATE_CARD, 'L3', 'BI'), Decimal('45'))

    def test_missing_level_costs_nothing(self):
        r = calculate(snap([res('Data', 'L9', 100), res('Data', None, 50)]))
        self.assertEqual(r.resources, 0)
        self.assertEqual(r.hours, Decimal('150'))

    def test_line_rate_override(self):
        line = {**res('Data', 'L1', 10), 'rate_usd': 99}
        self.assertEqual(calculate(snap([line])).resources, Decimal('990'))

    def test_bad_values_count_as_zero(self):
        r = calculate(snap([res('Data', 'L1', 'abc')], one_time=[{'amount': 'n/a'}, 'junk']))
        self.assertEqual(r.cost_basis, 0)


class TestV2(unittest.TestCase):
    def test_design_spec_worked_example(self):
        # DESIGN.md 5.3 ledger: basis 148,320 at 40% + 12% -> list 309,000; +23,600 pass-through
        s = {
            'calc_mode': V2,
            'resources': [{'group': 'X', 'level': 'L1', 'hours': 1, 'rate_usd': 142320}],
            'one_time_costs': [{'amount': 6000}, {'amount': 23600, 'category': 'license'}],
            'cloud4c_margin': 0.40, 'ax_margin': 0.12, 'fx_rate': 89.40,
            'project': {'discount_pct': 0},
        }
        r = calculate(s)
        self.assertEqual(r.cost_basis, Decimal('148320'))
        self.assertEqual(r.list_price, Decimal('309000'))
        self.assertEqual(r.c4c_amount, Decimal('123600'))
        self.assertEqual(r.ax_amount, Decimal('37080'))
        self.assertEqual(r.contract_value, Decimal('332600'))
        self.assertEqual(r.contract_inr, Decimal('29734440'))
        self.assertEqual(r.ax_net_pct, Decimal('12'))

    def test_zero_resources(self):
        r = calculate(snap(mode=V2))
        self.assertEqual((r.cost_basis, r.list_price, r.contract_value, r.ax_net_pct), (0, 0, 0, Decimal('12')))
        self.assertEqual(r.effective_pct, 0)

    def test_pass_through_only(self):
        r = calculate(snap(one_time=[{'amount': 5000, 'exclude_from_margin': True}], travel_cost=1000, mode=V2))
        self.assertEqual(r.list_price, 0)
        self.assertEqual(r.pass_through, Decimal('6000'))
        self.assertEqual(r.contract_value, Decimal('6000'))
        self.assertEqual(r.effective_pct, 0)

    def test_discount_comes_off_list_price_and_ax(self):
        r = calculate(snap([res('Data', 'L1', 1000)], c4c=0.40, ax=0.20, discount=5, mode=V2))
        self.assertEqual(r.list_price, Decimal('50000'))
        self.assertEqual(r.discount, Decimal('2500'))
        self.assertEqual(r.contract_value, Decimal('47500'))
        # AX keeps 10,000 - 2,500 of a 47,500 net price
        self.assertAlmostEqual(float(r.ax_net_pct), 7500 / 47500 * 100, places=9)

    def test_addon_treatment_defaults_and_override(self):
        s = snap([res('Data', 'L1', 100)], c4c=0.30, ax=0.20, travel_cost=1000, infra_cost=400,
                 third_party_cost=600, mode=V2)
        r = calculate(s)
        self.assertEqual(r.addons_pass, Decimal('1000'))    # travel passes through by default
        self.assertEqual(r.addons_margin, Decimal('1000'))  # infra + third-party take margin
        self.assertEqual(r.cost_basis, Decimal('3000'))
        s['addon_treatment'] = {'travel': 'margin', 'infra': 'pass', 'third_party': 'bogus'}
        r = calculate(s)
        self.assertEqual(r.addons_margin, Decimal('1600'))
        self.assertEqual(r.addons_pass, Decimal('400'))

    def test_margins_at_limits(self):
        ok = calculate(snap([res('Data', 'L1', 10)], c4c=0.94, ax=0.0, mode=V2))
        self.assertGreater(ok.list_price, 0)
        for c4c, ax, field in ((0.96, 0, 'cloud4c_margin'), (0, -0.01, 'ax_margin'), (0.50, 0.45, 'ax_margin')):
            with self.assertRaises(EngineInputError) as cm:
                calculate(snap([res('Data', 'L1', 10)], c4c=c4c, ax=ax, mode=V2))
            self.assertIn(field, cm.exception.errors)

    def test_discount_and_fx_limits(self):
        with self.assertRaises(EngineInputError) as cm:
            calculate(snap(discount=51, fx=0, mode=V2))
        self.assertEqual(set(cm.exception.errors), {'discount_pct', 'fx_rate'})

    def test_decimal_has_no_float_drift(self):
        r = calculate(snap(one_time=[{'amount': 0.1}, {'amount': 0.2}], c4c=0, ax=0, mode=V2))
        self.assertEqual(r.cost_basis, Decimal('0.3'))

    def test_to_dict_rounds_for_display(self):
        d = calculate(snap([res('Data', 'L1', 1)], c4c=0.33, ax=0, mode=V2)).to_dict()
        self.assertEqual(d['list_price'], 29.85)
        self.assertEqual(d['lines'][0]['rate'], 20.0)


if __name__ == '__main__':
    unittest.main()
