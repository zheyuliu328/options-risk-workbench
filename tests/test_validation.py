import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from options_risk.validation import attach_context, investigate, main, reference, reference_sensitivities, render


def fixture():
    return dict(as_of='2026-09-29', underlying='SYNTHETIC', currency='USD',
                spot=100, rate=.03, dividend_yield=.01,
                positions=[dict(id='call', kind='call', style='european', strike=100,
                                expiry='2026-10-29', quantity=1, multiplier=100, volatility=.25)],
                scenarios=[dict(name='unchanged', spot_return=0, vol_change=0, days=0),
                           dict(name='up', spot_return=.05, vol_change=.02, days=1)])


@unittest.skipUnless(importlib.util.find_spec('QuantLib'), 'optional QuantLib reference unavailable')
class IndependentReferenceTests(unittest.TestCase):
    def test_analytic_identity_and_global_date_restored(self):
        import QuantLib as ql
        old = ql.Settings.instance().evaluationDate
        d = investigate(fixture())
        self.assertEqual(old, ql.Settings.instance().evaluationDate)
        self.assertEqual(d['attention_count'], 0)
        for row in d['scenario_reference']:
            self.assertAlmostEqual(row['workbench_pnl'], row['reference_pnl'], places=8)

    def test_expiry_payoff_and_beyond_expiry_rejection(self):
        r = fixture()
        r['positions'][0]['expiry'] = r['as_of']
        x = reference(r, r['positions'][0], r['as_of'], 110, .25)
        self.assertEqual(x, dict(price=10, delta=None, gamma=None))
        r = fixture()
        r['scenarios'][1]['days'] = 31
        with self.assertRaisesRegex(ValueError, 'beyond expiry'):
            investigate(r)

    def test_american_meshes_tree_steps_and_signed_expiry_pnl(self):
        r = fixture()
        r['positions'][0].update(style='american', quantity=-2)
        r['scenarios'] = [dict(name='expiry', spot_return=.1, vol_change=0, days=30)]
        d = investigate(r)
        p = d['positions'][0]
        self.assertEqual([x['steps'] for x in p['tree_diagnostics']], [150, 151, 300, 301, 600, 601])
        for grid in ['reference_800', 'reference_1600']:
            self.assertTrue(all(math.isfinite(p[grid][k]) for k in ['price', 'delta', 'gamma']))
        expected = (10 - p['reference_1600']['price']) * -200
        self.assertAlmostEqual(d['scenario_reference'][0]['reference_pnl'], expected, places=8)
        self.assertTrue(all('reference_mesh_threshold' in c for c in p['unit_checks']))

    def test_shocked_reference_refinement_is_checked_without_offset_masking(self):
        r = fixture()
        r['positions'].append({**r['positions'][0], 'id': 'offset', 'quantity': -1})
        original = reference
        def unstable(*args, **kwargs):
            result = original(*args, **kwargs)
            mesh = args[5] if len(args) > 5 else kwargs.get('mesh', 1600)
            if mesh == 800 and args[3] > r['spot']:
                result['price'] += .1
            return result
        with patch('options_risk.validation.reference', side_effect=unstable):
            d = investigate(r)
        self.assertEqual(d['attention_count'], 0)
        self.assertEqual(d['scenario_attention_count'], 1)
        row = d['scenario_reference'][1]
        self.assertAlmostEqual(row['reference_pnl_mesh_difference'], 0)
        self.assertEqual(row['reference_refinement_status'], 'reference_mesh_unstable')
        self.assertEqual(len(row['position_refinement']), 2)
        self.assertTrue(all(p['status'] == 'reference_mesh_unstable'
                            for p in row['position_refinement']))
        self.assertIn('Scenario reference P&amp;L refinement', render(d))

    def test_scenario_grid_identity_and_zero_exposure_rejected(self):
        r = fixture()
        d = investigate(r)
        self.assertEqual(d['scenario_attention_count'], 0)
        for row in d['scenario_reference']:
            self.assertAlmostEqual(row['reference_pnl'], row['reference_pnl_800'], places=10)
            self.assertEqual(row['reference_refinement_status'], 'within_refinement_screen')
        r['positions'][0]['quantity'] = 0
        with self.assertRaisesRegex(ValueError, 'nonzero signed integer'):
            investigate(r)

    def test_unstable_reference_cannot_report_unqualified_agreement(self):
        original = reference
        def unstable(*args, **kwargs):
            result = original(*args, **kwargs)
            if (len(args) > 5 and args[5] == 800) or kwargs.get('mesh') == 800:
                result['price'] += .1
            return result
        with patch('options_risk.validation.reference', side_effect=unstable):
            d = investigate(fixture())
        self.assertEqual(d['positions'][0]['unit_checks'][0]['status'], 'reference_mesh_unstable')
        self.assertGreater(d['attention_count'], 0)

    def test_one_day_theta_is_expiry_value_change_not_instantaneous_derivative(self):
        r = fixture()
        r['positions'][0].update(expiry='2026-09-30', volatility=.2, quantity=-2)
        r['scenarios'] = [dict(name='next day', days=1)]
        d = investigate(r)
        checks = {c['metric']: c for c in d['positions'][0]['unit_checks']}
        self.assertEqual(len(checks), 6)
        theta = checks['theta_per_day']
        self.assertAlmostEqual(theta['reference'], -.4203523730, places=8)
        self.assertEqual(theta['status'], 'within_threshold')
        self.assertIn('expiry fixed', theta['convention']['method'])
        scaled = {c['metric']: c for c in d['positions'][0]['scaled_checks']}
        self.assertAlmostEqual(scaled['theta_per_day']['reference'], theta['reference'] * -200, places=10)
        self.assertAlmostEqual(d['scenario_reference'][0]['reference_pnl'], scaled['theta_per_day']['reference'])

    def test_boundary_put_retains_non_green_greeks_and_refinement(self):
        r = fixture()
        r.update(spot=95, rate=.08, dividend_yield=0)
        r['positions'][0].update(kind='put', style='american', volatility=.2, quantity=-2)
        r['scenarios'] = [dict(name='unchanged')]
        d = investigate(r)
        checks = {c['metric']: c for c in d['positions'][0]['unit_checks']}
        for key in ('vega_per_vol_point', 'theta_per_day'):
            c = checks[key]
            self.assertEqual(c['status'], 'investigate')
            self.assertTrue(c['own_threshold_exceeded'])
            self.assertLess(abs(c['reference_mesh_difference']), c['reference_mesh_threshold'])
        self.assertAlmostEqual(checks['vega_per_vol_point']['reference'], .0659718490, places=8)
        self.assertAlmostEqual(checks['theta_per_day']['reference'], -.0141815817, places=8)
        self.assertGreater(d['attention_count'], 0)
        self.assertIn('retrospective', d['policy']['revision'])
        report = render(d)
        self.assertIn('Reference mesh difference', report)
        self.assertIn('theta_per_day', report)
        self.assertIn('investigate', report)

    def test_new_reference_metric_failure_is_local_and_cannot_turn_green(self):
        original = reference_sensitivities
        def failed(*args, **kwargs):
            result = original(*args, **kwargs)
            result['rho_per_rate_point'] = None
            result['errors']['rho_per_rate_point'] = 'Injected unavailable independent rate bump'
            return result
        with patch('options_risk.validation.reference_sensitivities', side_effect=failed):
            d = investigate(fixture())
        check = next(c for c in d['positions'][0]['unit_checks'] if c['metric'] == 'rho_per_rate_point')
        self.assertEqual(check['status'], 'reference_unavailable')
        self.assertGreater(d['attention_count'], 0)
        self.assertIn('rate bump', render(d))

    def test_each_new_greek_refinement_is_checked_independently(self):
        original = reference_sensitivities
        def unstable(*args, **kwargs):
            result = original(*args, **kwargs)
            if (len(args) > 5 and args[5] == 800) or kwargs.get('mesh') == 800:
                result['vega_per_vol_point'] += .01
            return result
        with patch('options_risk.validation.reference_sensitivities', side_effect=unstable):
            d = investigate(fixture())
        checks = {c['metric']: c for c in d['positions'][0]['unit_checks']}
        self.assertEqual(checks['vega_per_vol_point']['status'], 'reference_mesh_unstable')
        self.assertEqual(checks['price']['status'], 'within_threshold')

    def test_invalid_crr_bump_is_not_a_successful_greek_validation(self):
        from options_risk.pricing import price
        r = fixture()
        r.update(rate=.1, dividend_yield=0)
        r['positions'][0].update(style='american', expiry='2027-09-29', volatility=.1/math.sqrt(300)+.0001)
        self.assertGreater(price(spot=100,strike=100,years=1,rate=.1,volatility=r['positions'][0]['volatility'],style='american'), 0)
        with self.assertRaisesRegex(ValueError, 'probability'):
            investigate(r)

    def test_immediate_exercise_and_near_zero_forward_vega(self):
        r = fixture()
        r.update(spot=50, rate=.1, dividend_yield=0)
        p = r['positions'][0]
        p.update(kind='put', style='american', expiry='2027-03-28')
        for vol in (.2, 0):
            with self.subTest(vol=vol):
                fine = reference_sensitivities(r, p, r['as_of'], r['spot'], vol)
                for key in ['vega_per_vol_point', 'rho_per_rate_point', 'theta_per_day']:
                    self.assertIsNotNone(fine[key])
                    self.assertLess(abs(fine[key]), 1e-8)
                if vol == 0:
                    self.assertIn('forward', fine['conventions']['vega_per_vol_point']['method'])

    def test_forward_vega_nontrivial_low_volatility_reference(self):
        r = fixture()
        r.update(rate=0, dividend_yield=0)
        p = r['positions'][0]
        p.update(style='american', volatility=.0005)
        x = reference_sensitivities(r,p,r['as_of'],100,.0005,1600)
        self.assertAlmostEqual(x['vega_per_vol_point'], .11437336725564884, places=9)
        self.assertIn('forward',x['conventions']['vega_per_vol_point']['method'])
        self.assertEqual(x['conventions']['vega_per_vol_point']['volatility_bump'], .001)

    def test_unsupported_degenerate_reference_is_fail_loud(self):
        r = fixture()
        r.update(rate=0, dividend_yield=0)
        p = r['positions'][0]
        p.update(style='american', volatility=0)
        with self.assertRaises(RuntimeError):
            reference_sensitivities(r,p,r['as_of'],100,0,800)

    def test_negative_rate_rho_keeps_its_sign_and_units(self):
        r = fixture()
        r.update(rate=-.05, dividend_yield=.02)
        p = r['positions'][0]
        p.update(kind='put', style='american', expiry='2027-09-29', volatility=.2)
        x = reference_sensitivities(r, p, r['as_of'], 100, .2, 800)
        self.assertAlmostEqual(x['rho_per_rate_point'], -.70818618, places=7)
        self.assertEqual(x['conventions']['rho_per_rate_point']['rate_bump'], .0001)

    def test_failed_independent_bump_preserves_other_metrics(self):
        original = reference
        r = fixture()
        p = r['positions'][0]
        p['style'] = 'american'
        def failed(*args, **kwargs):
            if args[4] > p['volatility']:
                raise RuntimeError('Injected invalid reference volatility bump')
            return original(*args, **kwargs)
        with patch('options_risk.validation.reference', side_effect=failed):
            result = reference_sensitivities(r,p,r['as_of'],100,p['volatility'],800)
        self.assertIsNone(result['vega_per_vol_point'])
        self.assertIn('volatility bump',result['errors']['vega_per_vol_point'])
        self.assertTrue(math.isfinite(result['rho_per_rate_point']))
        self.assertTrue(math.isfinite(result['theta_per_day']))

    def test_offline_report_contains_inputs_and_escapes_identifiers(self):
        r = fixture()
        r['positions'][0]['id'] = '<script>alert(1)</script>'
        text = render(investigate(r))
        self.assertIn('Valuation date: 2026-09-29', text)
        self.assertIn('Multiplier', text)
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)


class QuoteContextTests(unittest.TestCase):
    def setUp(self):
        self.d = dict(request=dict(as_of='2026-09-29'), positions=[dict(id='call',
                      unit_checks=[dict(own=3.)])], limits=[])
        self.c = dict(quotes=[dict(id='call', date='2026-09-29', bid=2., ask=2.5)])

    def test_outside_spread_is_retained_not_price_certification(self):
        attach_context(self.d, self.c)
        self.assertFalse(self.d['quote_diagnostics'][0]['inside_supplied_spread'])
        self.assertEqual(self.d['quote_diagnostics'][0]['model_minus_mid'], .75)
        self.assertIn('not authenticated', self.d['limits'][0])

    def test_invalid_quotes_and_date_mismatch_are_rejected(self):
        for change in [dict(bid=3., ask=2.), dict(bid=float('nan')),
                       dict(id='missing'), dict(date='2026-09-28')]:
            c = copy.deepcopy(self.c)
            c['quotes'][0].update(change)
            with self.assertRaises(ValueError):
                attach_context(copy.deepcopy(self.d), c)

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'existing'
            output.mkdir()
            marker = output / 'user.txt'
            marker.write_text('preserve')
            with patch('sys.argv', ['validation', 'unused.json', '--output', str(output)]):
                with self.assertRaises(SystemExit) as exc:
                    main()
            self.assertEqual(exc.exception.code, 2)
            self.assertEqual(marker.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
