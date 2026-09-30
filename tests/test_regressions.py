import unittest
from options_risk.pricing import greeks
from options_risk.report import render
from options_risk.scenarios import analyse
from test_scenarios import sample


class RegressionTest(unittest.TestCase):
    def test_american_atm_gamma_converges_without_small_bump_spike(self):
        p = dict(spot=100,strike=100,years=30/365,rate=.04,volatility=.25)
        reference = greeks(**p, style='european')['gamma']
        errors = []
        for steps in [100,300,1000]:
            gamma = greeks(**p, style='american',steps=steps)['gamma']
            errors.append(abs(gamma-reference))
            self.assertLess(abs(gamma-reference)/reference,.02)
        self.assertLess(errors[-1], errors[0])

    def test_report_escapes_identifiers(self):
        q = sample()
        q['underlying'] = '<script>alert(1)</script>'
        result = render(analyse(q))
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)

    def test_report_contains_replay_inputs_and_sensitivity_units(self):
        q = sample()
        q['positions'][0]['id'] = '<img onerror=alert(1)>'
        result = render(analyse(q), q)
        self.assertIn('Annual vol', result)
        self.assertIn('currency per 1 vol percentage point', result)
        self.assertIn('Scenario maximum loss is not VaR', result)
        self.assertIn('european', result)
        self.assertNotIn('<img', result)
        self.assertIn('&lt;img', result)
