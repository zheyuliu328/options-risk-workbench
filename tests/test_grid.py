import copy
import json
import math
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from options_risk.grid import review_grid, render_grid, prepare


def example():
    return json.loads((Path(__file__).parents[1]/'examples/price-grid.json').read_text())


class GridTest(unittest.TestCase):
    def test_anchor_and_sign(self):
        q=example();q['grid'].update(lower_return=-.13,upper_return=.27)
        r=review_grid(q)
        self.assertEqual(len(r['rows']),22)
        zero=next(x for x in r['rows'] if x['spot_return']==0)
        self.assertEqual((zero['change'],zero['approximation'],zero['residual']),(0,0,0))
        flipped=copy.deepcopy(q)
        for p in flipped['portfolio']['positions']:p['quantity']*=-1
        n=review_grid(flipped)
        for a,b in zip(r['rows'],n['rows']):
            for k in ('value','change','approximation','residual'):self.assertAlmostEqual(a[k],-b[k])
        self.assertEqual(q,example() | {'grid':q['grid']})

    def test_expiry_straddle_payoff(self):
        q=example();q['grid']['days']=30
        r=review_grid(q)
        for row in r['rows']:
            self.assertAlmostEqual(row['value'],100*abs(row['spot']-100),places=8)
            self.assertAlmostEqual(row['change'],100*abs(row['spot']-100)-r['valuation']['market_value'],places=8)
        zero=next(x for x in r['rows'] if x['spot_return']==0)
        self.assertLess(zero['change'],0)

    def test_put_call_parity_with_time_and_dividends(self):
        q=example();q['portfolio']['positions'][1]['quantity']=-1
        q['portfolio']['rate']=-.02;q['portfolio']['dividend_yield']=.07
        q['grid'].update(days=7,vol_change=.1)
        r=review_grid(q)
        initial=100*(100*math.exp(-.07*30/365)-100*math.exp(.02*30/365))
        for row in r['rows']:
            target=100*(row['spot']*math.exp(-.07*23/365)-100*math.exp(.02*23/365))
            self.assertAlmostEqual(row['value'],target,places=8)
            self.assertAlmostEqual(row['change'],target-initial,places=8)
        q['grid'].update(days=0,vol_change=0)
        for row in review_grid(q)['rows']:
            self.assertAlmostEqual(row['change'],100*math.exp(-.07*30/365)*(row['spot']-100),places=8)
            self.assertAlmostEqual(row['approximation'],row['change'],places=8)

    def test_invalid_grid_and_unsupported_fields(self):
        cases=[{'points':True},{'points':3.0},{'points':30},{'lower_return':-1},
               {'upper_return':0,'lower_return':0},{'lower_return':1e-17},
               {'lower_return':-1e-17,'upper_return':1e-17},{'days':True},
               {'days':31},{'vol_change':-.3},{'rate_change':.01}]
        for case in cases:
            with self.subTest(case=case):
                q=example();q['grid'].update(case)
                with self.assertRaises(ValueError):review_grid(q)
        q=example();q['portfolio']['scenarios']=[]
        with self.assertRaises(ValueError):prepare(q)

    def test_boundaries_and_per_position_values(self):
        q=example();q['grid'].update(points=29,lower_return=-.11,upper_return=.31)
        q['portfolio']['positions'][0].update(quantity=-3,multiplier=50)
        r=review_grid(q)
        self.assertEqual(len(r['rows']),30)
        self.assertTrue(all(a['spot']<b['spot'] for a,b in zip(r['rows'],r['rows'][1:])))
        for row in r['rows']:
            self.assertEqual(row['value'],sum(p['market_value'] for p in row['positions']))
        q['source_note']='<script>alert(1)</script>'
        html=render_grid(review_grid(q))
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        self.assertIn('Sampled extremes',html)

    def test_distinct_narrow_grid_labels_and_american_expiry(self):
        q = example()
        q['grid'].update(points=3, lower_return=-1e-12, upper_return=1e-12)
        result = review_grid(q)
        html = render_grid(result)
        labels = [str(row['spot']) for row in result['rows']]
        self.assertEqual(len(set(labels)), 3)
        for label in labels:
            self.assertIn('<td>' + label + '</td>', html)
        q = example()
        q['grid'].update(points=3, days=30)
        for position in q['portfolio']['positions']:
            position['style'] = 'american'
        q['portfolio']['positions'][0].update(quantity=-3, multiplier=50)
        q['portfolio']['positions'][1].update(quantity=2, multiplier=100)
        result = review_grid(q)
        for row in result['rows']:
            expected = -150 * max(row['spot'] - 100, 0) + 200 * max(100 - row['spot'], 0)
            self.assertAlmostEqual(row['value'], expected, places=8)
            self.assertAlmostEqual(row['change'], expected - result['valuation']['market_value'], places=8)

    def test_cli_replay_and_no_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'grid.json';source.write_text(json.dumps(example()))
            cmd=[sys.executable,'-m','options_risk.grid',str(source),'--output',str(root/'first')]
            subprocess.run(cmd,check=True,capture_output=True)
            subprocess.run([sys.executable,'-m','options_risk.grid',str(root/'first/request.json'),'--output',str(root/'second')],check=True,capture_output=True)
            self.assertEqual((root/'first/results.json').read_bytes(),(root/'second/results.json').read_bytes())
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            source.write_text('{"schema_version":1,"schema_version":1}')
            self.assertNotEqual(subprocess.run([*cmd[:-1],str(root/'bad')],capture_output=True).returncode,0)
            self.assertFalse((root/'bad').exists())


if __name__=='__main__':unittest.main()
