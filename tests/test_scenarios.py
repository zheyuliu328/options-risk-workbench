import copy
import unittest
from options_risk.scenarios import analyse


def sample():
    return dict(as_of='2026-09-29', underlying='SYNTHETIC', currency='USD', spot=100, rate=.03,
                positions=[dict(id='call', expiry='2026-10-29', strike=100, quantity=1,
                                multiplier=100, volatility=.25, kind='call', style='european')],
                scenarios=[dict(name='unchanged'), dict(name='up', spot_return=.1),
                           dict(name='vol', vol_change=.05)])


class ScenariosTest(unittest.TestCase):
    def test_fixed_contract_and_identity(self):
        r = analyse(sample())
        self.assertEqual(r['scenarios'][0]['pnl'], 0)
        self.assertGreater(r['scenarios'][1]['pnl'], 0)
        self.assertGreater(r['scenarios'][2]['pnl'], 0)
        for scenario in r['scenarios']:
            self.assertEqual(scenario['positions'][0]['strike'], 100)
            self.assertEqual(scenario['positions'][0]['expiry'], '2026-10-29')

    def test_offsetting_positions(self):
        q = sample()
        other = copy.deepcopy(q['positions'][0])
        other.update(id='short', quantity=-1)
        q['positions'].append(other)
        r = analyse(q)
        self.assertEqual(r['market_value'], 0)
        self.assertTrue(all(v == 0 for v in r['greeks'].values()))
        self.assertTrue(all(s['pnl'] == 0 for s in r['scenarios']))

    def test_expiry_and_beyond(self):
        q = sample()
        q['scenarios'] = [dict(name='expiry', days=30, spot_return=.1)]
        r = analyse(q)
        self.assertAlmostEqual(r['scenarios'][0]['positions'][0]['market_value'], 1000)
        q['scenarios'][0]['days'] = 31
        with self.assertRaises(ValueError):
            analyse(q)

    def test_invalid_input(self):
        for key,value in [('spot_return', -1), ('vol_change', -.3), ('days', True), ('days', -1)]:
            with self.subTest(key=key):
                q = sample()
                q['scenarios'] = [dict(name='bad', **{key:value})]
                with self.assertRaises(ValueError):
                    analyse(q)

    def test_unsupported_shocks_are_not_silently_ignored(self):
        q = sample()
        q['scenarios'][0]['rate_change'] = .02
        with self.assertRaises(ValueError):
            analyse(q)


if __name__ == '__main__':
    unittest.main()
