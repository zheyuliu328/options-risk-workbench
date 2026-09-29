"""Independent numerical and financial-invariant checks for option valuation.

The fixed BSM reference case is S=K=100, T=1, r=5%, sigma=20%, q=0.
Greek references use one percentage point for volatility/rates and 365 days.
Tests intentionally use reference values and financial identities rather than
reimplementing the engine's normal CDF or binomial recursion.
"""

import math
import unittest

from options_risk.pricing import greeks, price


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(spot=100.0, strike=100.0, years=1.0, rate=0.05,
                         volatility=0.20, dividend_yield=0.0)

    def value(self, **changes):
        return price(**(self.base | changes))

    def test_independent_bsm_reference_prices(self):
        self.assertAlmostEqual(self.value(kind="call"), 10.4505835722, places=8)
        self.assertAlmostEqual(self.value(kind="put"), 5.5735260223, places=8)

    def test_dividend_adjusted_put_call_parity_across_moneyness(self):
        for spot, strike, years, rate, dividend in (
            (70.0, 100.0, 0.25, 0.03, 0.02),
            (100.0, 100.0, 2.0, -0.01, 0.03),
            (150.0, 90.0, 0.75, 0.06, 0.08),
        ):
            with self.subTest(spot=spot, rate=rate):
                args = dict(spot=spot, strike=strike, years=years, rate=rate,
                            dividend_yield=dividend)
                parity = spot * math.exp(-dividend * years) - strike * math.exp(-rate * years)
                self.assertAlmostEqual(self.value(kind="call", **args) -
                                       self.value(kind="put", **args), parity, places=9)

    def test_european_no_arbitrage_bounds(self):
        for spot in (20.0, 100.0, 250.0):
            for vol in (0.01, 0.20, 1.20):
                for kind in ("call", "put"):
                    with self.subTest(spot=spot, vol=vol, kind=kind):
                        discounted_spot = spot * math.exp(-0.03)
                        discounted_strike = 100.0 * math.exp(-0.05)
                        if kind == "call":
                            lower, upper = max(0.0, discounted_spot - discounted_strike), discounted_spot
                        else:
                            lower, upper = max(0.0, discounted_strike - discounted_spot), discounted_strike
                        result = self.value(spot=spot, volatility=vol,
                                            dividend_yield=0.03, kind=kind)
                        self.assertGreaterEqual(result, lower - 1e-9)
                        self.assertLessEqual(result, upper + 1e-9)

    def test_american_put_has_exercise_value_and_european_lower_bound(self):
        # In-the-money, positive-rate put has a material early-exercise premium.
        european = self.value(spot=80.0, kind="put")
        american = self.value(spot=80.0, kind="put", style="american", steps=600)
        self.assertGreaterEqual(american, 20.0 - 1e-10)
        self.assertGreater(american, european)
        self.assertLessEqual(american, 100.0)

    def test_american_non_dividend_call_converges_to_european(self):
        expected = self.value(kind="call")
        coarse = self.value(kind="call", style="american", steps=100)
        fine = self.value(kind="call", style="american", steps=800)
        self.assertLess(abs(fine - expected), abs(coarse - expected))
        self.assertAlmostEqual(fine, expected, delta=0.005)

    def test_dividend_can_make_american_call_early_exercise_valuable(self):
        args = dict(spot=150.0, dividend_yield=0.15, kind="call")
        european = self.value(**args)
        american = self.value(**args, style="american", steps=600)
        self.assertGreaterEqual(american, 50.0 - 1e-9)
        self.assertGreater(american, european)

    def test_expiry_is_exact_intrinsic_value(self):
        for style in ("european", "american"):
            for spot in (80.0, 100.0, 120.0):
                for kind in ("call", "put"):
                    with self.subTest(style=style, spot=spot, kind=kind):
                        expected = max(spot - 100.0, 0.0) if kind == "call" else max(100.0 - spot, 0.0)
                        self.assertEqual(self.value(spot=spot, years=0.0, kind=kind,
                                                    style=style), expected)

    def test_zero_vol_european_is_discounted_deterministic_payoff(self):
        forward_discounted_difference = 100.0 * math.exp(-0.02) - 100.0 * math.exp(-0.05)
        self.assertAlmostEqual(self.value(volatility=0.0, dividend_yield=0.02),
                               max(forward_discounted_difference, 0.0), places=10)
        self.assertAlmostEqual(self.value(volatility=0.0, dividend_yield=0.02, kind="put"),
                               max(-forward_discounted_difference, 0.0), places=10)

    def test_spot_shock_keeps_original_contract_strike(self):
        original = self.value(kind="call")
        shocked = self.value(spot=120.0, kind="call")
        reset_contract = self.value(spot=120.0, strike=120.0, kind="call")
        self.assertGreater(shocked, original)
        self.assertGreater(shocked, reset_contract)
        self.assertEqual(self.value(spot=120.0, years=0.0), 20.0)
        # An original ATM straddle does not become a new ATM straddle on exit.
        expired_straddle = (self.value(spot=120.0, years=0.0, kind="call") +
                            self.value(spot=120.0, years=0.0, kind="put"))
        self.assertEqual(expired_straddle, 20.0)

    def test_european_greek_reference_values_and_units(self):
        actual = greeks(**self.base, kind="call")
        references = dict(delta=0.6368306512, gamma=0.01876201735,
                          vega_per_vol_point=0.3752403469,
                          rho_per_rate_point=0.5323248155,
                          theta_per_day=-0.0175726782)
        for name, expected in references.items():
            with self.subTest(greek=name):
                self.assertIn(name, actual)
                self.assertAlmostEqual(actual[name], expected, delta=2e-5)

    def test_vega_matches_one_percentage_point_not_unit_volatility(self):
        actual = greeks(**self.base)["vega_per_vol_point"]
        one_point_change = self.value(volatility=0.21) - self.value(volatility=0.20)
        self.assertAlmostEqual(actual, one_point_change, delta=0.001)
        self.assertGreater(actual, 0.3)
        self.assertLess(actual, 0.5)

    def test_put_call_greek_relations_with_dividends(self):
        args = self.base | dict(dividend_yield=0.03)
        call, put = greeks(**args, kind="call"), greeks(**args, kind="put")
        self.assertAlmostEqual(call["delta"] - put["delta"], math.exp(-0.03), delta=2e-5)
        self.assertAlmostEqual(call["gamma"], put["gamma"], delta=2e-5)
        self.assertAlmostEqual(call["vega_per_vol_point"], put["vega_per_vol_point"], delta=2e-5)

    def test_invalid_economic_inputs_are_rejected(self):
        invalid = [dict(spot=0.0), dict(spot=-1.0), dict(strike=0.0),
                   dict(strike=-1.0), dict(years=-0.1), dict(volatility=-0.1),
                   dict(kind="straddle"), dict(style="bermudan")]
        for field in self.base:
            for bad in (math.nan, math.inf, -math.inf):
                invalid.append({field: bad})
        for changes in invalid:
            for function in (price, greeks):
                with self.subTest(function=function.__name__, changes=changes):
                    with self.assertRaises(ValueError):
                        function(**(self.base | changes))

    def test_invalid_tree_step_counts_are_rejected(self):
        for steps in (0, -1, 2.5, True):
            with self.subTest(steps=steps):
                with self.assertRaises(ValueError):
                    self.value(style="american", steps=steps)


if __name__ == "__main__":
    unittest.main()
