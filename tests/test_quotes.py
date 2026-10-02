import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from options_risk.quotes import implied_volatility, review_quotes, render_quote_review


BASE = dict(spot=100., strike=100., years=1., rate=.05)


def request():
    return dict(as_of='2026-01-01', underlying='INVENTED', currency='USD',
                spot=100, rate=.05, dividend_yield=0,
                quotes=[dict(id='call', kind='call', style='european', strike=100,
                             expiry='2027-01-01', bid=10.40, ask=10.50)])


class QuoteTests(unittest.TestCase):
    def test_published_bsm_reference_and_residual(self):
        # Standard BSM example: S=K=100, r=5%, T=1, sigma=20%.
        result = implied_volatility(10.450583572185565, **BASE)
        self.assertEqual(result['status'],'solved')
        self.assertAlmostEqual(result['volatility'],.2,places=8)
        self.assertLessEqual(abs(result['residual']),1e-8)

    def test_boundaries_and_configured_cap_are_distinct(self):
        cases = [(0., BASE, 'below_model_lower_bound'),
                 (101., BASE, 'above_model_upper_bound'),
                 (100., BASE, 'unresolved_at_asymptotic_bound'),
                 (10.450583572185565, BASE | dict(max_volatility=.1), 'above_search_cap'),
                 (0., BASE | dict(years=0), 'unidentified_at_expiry'),
                 (1., BASE | dict(years=0), 'inconsistent_expiry_price'),
                 (50., BASE | dict(spot=50,kind='put',style='american',rate=.1,years=.5),
                  'boundary_at_price_tolerance'),
                 (10., BASE | dict(rate=0,dividend_yield=20,style='american',max_volatility=.01),
                  'empty_search_domain')]
        for premium, args, status in cases:
            with self.subTest(status=status):
                self.assertEqual(implied_volatility(premium,**args)['status'],status)

    def test_bad_numerics_and_unsupported_style_rejected(self):
        for premium in [True, float('nan'), float('inf'), -1]:
            with self.assertRaises(ValueError):
                implied_volatility(premium,**BASE)
        with self.assertRaises(ValueError):
            implied_volatility(10,**BASE,style='bermudan')

    def test_nonstandard_json_and_missing_metadata_fail_clearly(self):
        source=request();source['quotes'][0]['bid']=float('nan')
        with self.assertRaisesRegex(ValueError,'standard JSON'):
            review_quotes(source)
        source=request();del source['currency']
        with self.assertRaisesRegex(ValueError,'currency'):
            review_quotes(source)

    def test_low_price_sensitivity_is_visible_beside_numeric_estimate(self):
        estimate=implied_volatility(2e-8,spot=100,strike=200,years=.01,rate=0)
        self.assertEqual(estimate['status'],'low_price_sensitivity')
        result=review_quotes(request())
        result['rows'][0]['estimates']['mid']=estimate
        result['rows'][0]['status']='needs_review'
        self.assertIn('% (low_price_sensitivity)',render_quote_review(result))

    def test_invalid_row_retained_and_recovery_has_no_stale_results(self):
        source=request()
        bad=copy.deepcopy(source['quotes'][0]);bad.update(id='bad',bid=11,ask=10)
        source['quotes'].append(bad)
        result=review_quotes(source)
        self.assertEqual([r['status'] for r in result['rows']],['solved','invalid_input'])
        self.assertEqual(result['rows'][1]['input'],bad)
        source['quotes'][1].update(bid=10.4,ask=10.5)
        self.assertEqual(review_quotes(source)['attention_count'],0)

    def test_failed_bid_does_not_erase_other_endpoints(self):
        source=request();source['rate']=0
        source['quotes'][0].update(bid=0,ask=10)
        row=review_quotes(source)['rows'][0]
        self.assertEqual(row['estimates']['bid']['status'],'boundary_at_price_tolerance')
        self.assertEqual(row['estimates']['mid']['status'],'solved')
        self.assertEqual(row['estimates']['ask']['status'],'solved')
        self.assertEqual(row['status'],'needs_review')

    def test_every_duplicate_id_is_rejected_without_order_dependence(self):
        source=request()
        source['quotes'].append(copy.deepcopy(source['quotes'][0]))
        source['quotes'][1]['bid']=11
        for quotes in [source['quotes'],list(reversed(source['quotes']))]:
            result=review_quotes(source | dict(quotes=quotes))
            self.assertEqual([r['status'] for r in result['rows']],['invalid_input','invalid_input'])
            self.assertTrue(all('unique' in r['error'] for r in result['rows']))

    def test_report_escaping_and_cli_output_protection(self):
        source=request();source['quotes'][0]['id']='<script>oops</script>'
        report=render_quote_review(review_quotes(source))
        self.assertNotIn('<script>',report)
        self.assertIn('&lt;script&gt;',report)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'request.json';path.write_text(json.dumps(source))
            output=Path(tmp)/'out'
            cmd=[sys.executable,'-m','options_risk.quotes',str(path),'--output',str(output)]
            first=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            saved=(output/'result.json').read_bytes()
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)
            self.assertEqual(saved,(output/'result.json').read_bytes())
            self.assertIn('input_sha256',json.loads(saved))


@unittest.skipUnless(importlib.util.find_spec('QuantLib'),'optional QuantLib unavailable')
class IndependentQuoteTests(unittest.TestCase):
    def test_analytic_reference_grid(self):
        from options_risk.validation import reference
        source=request();contract=source['quotes'][0]
        for kind in ['call','put']:
            for rate,dividend in [(.05,0),(-.02,.03)]:
                for sigma in [.05,.2,1.2]:
                    source.update(rate=rate,dividend_yield=dividend)
                    contract.update(kind=kind)
                    expected=reference(source,contract,source['as_of'],100,sigma)['price']
                    result=implied_volatility(expected,**(BASE | dict(rate=rate,dividend_yield=dividend,kind=kind)))
                    self.assertEqual(result['status'],'solved',result)
                    self.assertAlmostEqual(result['volatility'],sigma,places=7)

    def test_american_fd_reference_and_tree_sensitivity(self):
        from options_risk.validation import reference
        source=request();source.update(rate=.03,dividend_yield=.01)
        contract=source['quotes'][0];contract.update(kind='put',style='american')
        ref=reference(source,contract,source['as_of'],100,.25,1600)['price']
        coarse=reference(source,contract,source['as_of'],100,.25,800)['price']
        self.assertLess(abs(ref-coarse),.001)
        contract.update(bid=ref-.01,ask=ref+.01)
        row=review_quotes(source)['rows'][0]
        self.assertEqual(row['status'],'solved',row)
        estimates=[row['estimates']['mid'],*row['mid_step_diagnostics']]
        self.assertEqual([x['steps'] for x in estimates],[300,301,600,601])
        for estimate in estimates:
            self.assertLess(abs(estimate['volatility']-.25),.001)
            self.assertLessEqual(abs(estimate['residual']),1e-8)
        self.assertLess(row['estimates']['bid']['volatility'],row['estimates']['ask']['volatility'])
