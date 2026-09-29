"""Regressions from the independent overnight boundary audit."""
import copy
import json
from pathlib import Path
import unittest
from options_risk.pricing import greeks
from options_risk.scenarios import analyse


class NumericBoundaryTests(unittest.TestCase):
    def request(self):
        return json.loads((Path(__file__).parents[1] / 'examples/portfolio.json').read_text())

    def test_one_day_low_vol_gamma_reference(self):
        for kind in ('call', 'put'):
            actual = greeks(spot=100, strike=100, years=1/365, rate=0,
                            dividend_yield=0, volatility=.01, kind=kind)
            self.assertAlmostEqual(actual['gamma'], 7.621781304, places=8)

    def test_finite_inputs_cannot_produce_nonfinite_output(self):
        for quantity in (1e308, 10**1000):
            request = self.request()
            request['positions'][0]['quantity'] = quantity
            with self.assertRaises(ValueError):
                analyse(request)

    def test_large_finite_exposure_still_checks_valuation_overflow(self):
        request = self.request()
        request['positions'][0].update(quantity=1e307, multiplier=1)
        request['spot'] = 10000
        with self.assertRaises(ValueError):
            analyse(request)

    def test_invalid_dates_and_calendar_overflow_are_user_errors(self):
        original = self.request()
        requests = []
        a=copy.deepcopy(original);a['as_of']=None;requests.append(a)
        a=copy.deepcopy(original);a['positions'][0]['expiry']=None;requests.append(a)
        a=copy.deepcopy(original);a['scenarios'][0]['days']=10**100;requests.append(a)
        for request in requests:
            with self.assertRaises(ValueError):
                analyse(request)

    def test_normal_report_is_strict_json(self):
        json.dumps(analyse(self.request()), allow_nan=False)

    def test_model_error_identifies_position_and_stage(self):
        request = self.request()
        request['positions'][0]['volatility'] = 0.00001
        with self.assertRaisesRegex(ValueError, r'Position "long-call" \(valuation\).*CRR probability'):
            analyse(request)

    def test_scenario_error_identifies_original_contract(self):
        request = self.request()
        request['scenarios'][0]['days'] = 366
        with self.assertRaisesRegex(ValueError, r'Scenario .*position "long-call".*beyond expiry'):
            analyse(request)

    def test_low_vol_vega_independent_decimal_references(self):
        # 70-digit Decimal evaluation of the normal density and BSM derivative.
        for spot, expected in ((99, 0.0002440727707836168), (101, 0.0002784235628368248)):
            for kind in ('call', 'put'):
                g=greeks(spot=spot,strike=100,years=30/365,rate=0,
                         dividend_yield=0,volatility=.01,kind=kind)
                self.assertAlmostEqual(g['vega_per_vol_point'], expected, delta=1e-14)
