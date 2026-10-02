import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from options_risk.validation import attach_context, investigate, main, reference, render


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
