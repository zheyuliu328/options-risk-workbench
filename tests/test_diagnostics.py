import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from options_risk.diagnostics import diagnose, main, render


def fixture():
    return json.loads((Path(__file__).parents[1] / 'examples/greek-boundary.json').read_text())


class NumericalDiagnosticsTests(unittest.TestCase):
    def test_boundary_oscillation_signed_units_and_immutable_input(self):
        request = fixture()
        original = copy.deepcopy(request)
        result = diagnose(request)
        self.assertEqual(request, original)
        by_step = {r['steps']: r for r in result['step_results']}
        self.assertAlmostEqual(by_step[300]['greeks']['value']['vega_per_vol_point'], .0672473357, places=8)
        self.assertAlmostEqual(by_step[301]['greeks']['value']['vega_per_vol_point'], .064976349, places=8)
        self.assertEqual(by_step[300]['signed_price']['value'], by_step[300]['price']['value'] * -200)
        self.assertEqual(by_step[300]['signed_greeks']['value']['theta_per_day'],
                         by_step[300]['greeks']['value']['theta_per_day'] * -200)
        self.assertEqual(result['unavailable_count'], 0)
        self.assertNotIn('best_steps', result)
        self.assertEqual(result['fingerprint'], diagnose(request)['fingerprint'])
        central = result['bump_results'][1]
        low, high = [e['price']['value'] for e in central['endpoints']]
        self.assertAlmostEqual(central['value'], (high-low)/(.002)*.01)

    def test_valid_price_survives_invalid_greek_bump(self):
        r = fixture()
        r.update(spot=100, rate=.1)
        r['positions'][0].update(kind='call', expiry='2027-01-01', volatility=.1/math.sqrt(300)+.0001)
        d = diagnose(r)
        by_step = {x['steps']: x for x in d['step_results']}
        self.assertEqual(by_step[150]['price']['status'], 'unavailable')
        self.assertEqual(by_step[300]['price']['status'], 'available')
        self.assertAlmostEqual(by_step[300]['price']['value'], 9.5162581964, places=8)
        self.assertEqual(by_step[300]['greeks']['status'], 'unavailable')
        self.assertIn('probability', by_step[300]['greeks']['reason'])
        self.assertTrue(any(p['price']['status'] == 'unavailable'
                            for b in d['bump_results'] for p in b['endpoints']))
        self.assertGreater(d['unavailable_count'], 0)
        json.dumps(d, allow_nan=False)

    def test_zero_volatility_is_explicit_forward_and_immediate_exercise(self):
        r = fixture()
        r.update(spot=100, rate=0)
        r['positions'][0]['volatility'] = 0
        d = diagnose(r)
        self.assertTrue(all(row['price']['value'] == 0 for row in d['step_results']))
        self.assertTrue(all(row['method'] == 'second-order forward' for row in d['bump_results'][:3]))
        r.update(spot=50, rate=.1)
        r['positions'][0]['volatility'] = .2
        d = diagnose(r)
        self.assertTrue(all(row['price']['value'] == 50 for row in d['step_results']))
        self.assertTrue(all(abs(row['greeks']['value']['vega_per_vol_point']) < 1e-10
                            for row in d['step_results']))

    def test_no_dividend_american_call_against_closed_form_value(self):
        r = fixture()
        r.update(spot=100, rate=.05, dividend_yield=0)
        r['positions'][0].update(kind='call', expiry='2027-01-01', volatility=.2)
        d = diagnose(r)
        # Standard independently tabulated BSM call, S=K=100, T=1, r=.05, sigma=.2.
        for row in d['step_results']:
            self.assertLess(abs(row['price']['value'] - 10.450583572185565), .02)
        self.assertEqual(d['unavailable_count'], 0)

    def test_selection_scope_ambiguity_and_expiry_rejection(self):
        r = fixture()
        r['positions'].append({'id': 'unexamined', 'not_a_priced_contract': True})
        with self.assertRaisesRegex(ValueError, 'select a position'):
            diagnose(r)
        d = diagnose(r, 'boundary-put')
        self.assertEqual(d['input_position_count'], 2)
        self.assertNotIn('unexamined', json.dumps(d['selected_input']))
        self.assertIn('not validated', ' '.join(d['limits']))
        r['positions'][1]['id'] = 'boundary-put'
        with self.assertRaisesRegex(ValueError, 'unique'):
            diagnose(r, 'boundary-put')
        r = fixture()
        r['positions'][0]['expiry'] = r['as_of']
        with self.assertRaisesRegex(ValueError, 'nonsmooth'):
            diagnose(r)

    def test_scaled_overflow_does_not_hide_finite_unit_values(self):
        r = fixture()
        r['positions'][0].update(quantity=1e307, multiplier=10)
        d = diagnose(r)
        self.assertTrue(all(x['price']['status'] == 'available' for x in d['step_results']))
        self.assertTrue(all(x['signed_price']['status'] == 'unavailable' for x in d['step_results']))
        json.dumps(d, allow_nan=False)

    def test_scaled_greek_failure_is_visible_when_price_scaling_succeeds(self):
        r = fixture()
        r.update(spot=100, rate=0, dividend_yield=0)
        r['positions'][0].update(expiry='2026-01-02', volatility=.00001, quantity=1e307, multiplier=10)
        d = diagnose(r)
        self.assertTrue(all(row['signed_price']['status'] == 'available' for row in d['step_results']))
        self.assertTrue(all(row['signed_greeks']['status'] == 'unavailable' for row in d['step_results']))
        visible = render(d).split('<details>')[0]
        self.assertIn('Signed Greek status', visible)
        self.assertIn('exceeds numeric range', visible)

    def test_unsupported_inputs_escaping_and_output_protection(self):
        r = fixture()
        r['positions'][0]['id'] = '<script>alert(1)</script>'
        report = render(diagnose(r))
        self.assertNotIn('<script>', report)
        self.assertIn('&lt;script&gt;', report)
        r['cash_dividends'] = []
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            diagnose(r)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'existing'
            target.mkdir()
            marker = target / 'keep.txt'
            marker.write_text('preserved')
            with patch('sys.argv', ['diagnostics', 'unused.json', '--output', str(target)]):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(marker.read_text(), 'preserved')
