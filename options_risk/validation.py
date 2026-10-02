"""Optional, offline independent-engine investigation. No market-data retrieval."""
import argparse
from datetime import date, timedelta
import hashlib
import html
import json
import math
from pathlib import Path

from .pricing import price, greeks
from .scenarios import analyse


POLICY = {
    "meaning": "Predeclared investigation thresholds, not model approval bounds",
    "european": {"price_abs": 1e-8, "price_rel": 1e-10,
                 "delta_abs": 1e-8, "gamma_abs": 1e-9},
    "american": {"price_abs": .01, "price_rel": .001,
                 "delta_abs": .005, "delta_rel": .01,
                 "gamma_abs": .0005, "gamma_rel": .05},
    "tree_steps": [150, 151, 300, 301, 600, 601],
    "fd_meshes": [800, 1600],
    "reference_refinement_fraction": .25,
    "revision": "2: independent review added reference mesh classification; retrospective diagnostics",
}


def reference(request, position, valuation_date, spot, volatility, mesh=1600):
    import QuantLib as ql
    settings = ql.Settings.instance()
    previous = settings.evaluationDate
    day = date.fromisoformat(valuation_date)
    expiry = date.fromisoformat(position['expiry'])
    sign = 1 if position['kind'] == 'call' else -1
    if expiry == day:
        return {"price": max(sign * (spot - position['strike']), 0),
                "delta": None, "gamma": None}
    try:
        today = ql.Date(day.day, day.month, day.year)
        end = ql.Date(expiry.day, expiry.month, expiry.year)
        settings.evaluationDate = today
        dc = ql.Actual365Fixed()
        r = ql.YieldTermStructureHandle(ql.FlatForward(today, request.get('rate', 0), dc))
        q = ql.YieldTermStructureHandle(ql.FlatForward(today, request.get('dividend_yield', 0), dc))
        v = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), volatility, dc))
        process = ql.BlackScholesMertonProcess(
            ql.QuoteHandle(ql.SimpleQuote(spot)), q, r, v)
        payoff = ql.PlainVanillaPayoff(ql.Option.Call if sign == 1 else ql.Option.Put,
                                     position['strike'])
        exercise = (ql.EuropeanExercise(end) if position['style'] == 'european'
                    else ql.AmericanExercise(today, end))
        option = ql.VanillaOption(payoff, exercise)
        engine = (ql.AnalyticEuropeanEngine(process) if position['style'] == 'european'
                  else ql.FdBlackScholesVanillaEngine(process, mesh, mesh, 2))
        option.setPricingEngine(engine)
        return {"price": option.NPV(), "delta": option.delta(), "gamma": option.gamma()}
    finally:
        settings.evaluationDate = previous


def investigate(request):
    import QuantLib as ql
    result = analyse(request)  # Preserve the production input/error contract.
    start = date.fromisoformat(request['as_of'])
    output = {"policy": POLICY, "quantlib_version": ql.__version__,
              "request": request, "workbench": result, "positions": [],
              "scenario_reference": [], "limits": [
                  "Independent engines agree only conditional on shared input conventions.",
                  "American FDM refinement and CRR oscillation are diagnostics, not exact error bounds.",
                  "Only price, delta and gamma have independent Greek comparisons here.",
                  "Workbench theta is a one-calendar-day change, not QuantLib instantaneous theta.",
                  "No market quotation, source authenticity, profit or model approval is certified.",
                  "Expiry Greeks are nonsmooth and are not compared as differentiable values."]}
    for position in request['positions']:
        args = dict(spot=request['spot'], strike=position['strike'],
                    years=(date.fromisoformat(position['expiry']) - start).days / 365,
                    rate=request.get('rate', 0), dividend_yield=request.get('dividend_yield', 0),
                    volatility=position['volatility'], kind=position['kind'], style=position['style'])
        fine = reference(request, position, request['as_of'], request['spot'], position['volatility'])
        coarse = reference(request, position, request['as_of'], request['spot'],
                           position['volatility'], 800)
        own = {"price": price(**args), **greeks(**args)}
        policy = POLICY[position['style']]
        checks = []
        for metric in ['price', 'delta', 'gamma']:
            expected = fine[metric]
            if expected is None:
                checks.append({"metric": metric, "status": "not_compared_at_expiry"})
                continue
            threshold = max(policy[metric + '_abs'],
                            policy.get(metric + '_rel', 0) * abs(expected))
            difference = own[metric] - expected
            refinement = expected - coarse[metric]
            reference_threshold = threshold * POLICY['reference_refinement_fraction']
            reference_stable = abs(refinement) <= reference_threshold
            checks.append({"metric": metric, "own": own[metric], "reference": expected,
                           "difference": difference, "threshold": threshold,
                           "reference_mesh_difference": refinement,
                           "reference_mesh_threshold": reference_threshold,
                           "own_threshold_exceeded": abs(difference) > threshold,
                           "status": ('reference_mesh_unstable' if not reference_stable else
                                      'investigate' if abs(difference) > threshold else 'within_threshold')})
        tree = []
        if position['style'] == 'american':
            for steps in POLICY['tree_steps']:
                try:
                    tree.append({"steps": steps, "price": price(**args, steps=steps),
                                 **greeks(**args, steps=steps)})
                except ValueError as exc:
                    tree.append({"steps": steps, "error": str(exc)})
        output['positions'].append({"id": position['id'], "unit_checks": checks,
                                    "reference_800": coarse, "reference_1600": fine,
                                    "fd_price_refinement": fine['price'] - coarse['price'],
                                    "tree_diagnostics": tree})
    reference_base = sum(reference(request, p, request['as_of'], request['spot'],
                                   p['volatility'])['price'] * p['quantity'] * p['multiplier']
                         for p in request['positions'])
    for scenario, actual in zip(request['scenarios'], result['scenarios']):
        when = (start + timedelta(days=scenario.get('days', 0))).isoformat()
        new_spot = request['spot'] * (1 + scenario.get('spot_return', 0))
        value = sum(reference(request, p, when, new_spot,
                              p['volatility'] + scenario.get('vol_change', 0))['price']
                    * p['quantity'] * p['multiplier'] for p in request['positions'])
        approximate = sum(p['greek_approximation'] for p in actual['positions'])
        output['scenario_reference'].append({"name": scenario['name'],
            "workbench_pnl": actual['pnl'], "reference_pnl": value - reference_base,
            "engine_pnl_difference": actual['pnl'] - (value - reference_base),
            "workbench_local_approximation": approximate,
            "workbench_approximation_residual": actual['pnl'] - approximate})
    output['attention_count'] = sum(c['status'] in ['investigate', 'reference_mesh_unstable']
        for p in output['positions'] for c in p['unit_checks'])
    return output


def attach_context(investigation, context):
    """Retain declared provenance and quote diagnostics, never certify them."""
    positions = {p['id']: p for p in investigation['positions']}
    seen = set()
    diagnostics = []
    for quote in context.get('quotes', []):
        identity = quote['id']
        if identity not in positions or identity in seen:
            raise ValueError('quote IDs must be unique and match portfolio positions')
        seen.add(identity)
        bid, ask = quote['bid'], quote['ask']
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or
               not math.isfinite(x) for x in [bid, ask]) or not 0 <= bid <= ask:
            raise ValueError('quote requires finite nonnegative bid <= ask')
        if quote['date'] != investigation['request']['as_of']:
            raise ValueError('quote date must match valuation date; intraday synchrony remains unverified')
        own = positions[identity]['unit_checks'][0]['own']
        diagnostics.append({"id": identity, "bid": bid, "ask": ask,
                            "model_price": own, "model_minus_mid": own - (bid + ask) / 2,
                            "inside_supplied_spread": bid <= own <= ask,
                            "interpretation": "Conditional discrepancy only; timing, rates, dividends and IV may differ"})
    investigation['source_context'] = context
    investigation['quote_diagnostics'] = diagnostics
    investigation['limits'].append('Supplied quote rows and provenance declarations are not authenticated by the tool.')


def render(investigation):
    def esc(value):
        return html.escape(format(value, '.8g') if isinstance(value, float) else str(value))
    rows = ''.join('<tr>' + ''.join('<td>' + esc(row[k]) + '</td>' for k in
        ['name', 'workbench_pnl', 'reference_pnl', 'engine_pnl_difference',
         'workbench_local_approximation', 'workbench_approximation_residual']) + '</tr>'
        for row in investigation['scenario_reference'])
    unit_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [p['id'], c['metric'], c.get('own', 'not compared'), c.get('reference', ''),
         c.get('difference', ''), c.get('threshold', ''), c['status']]) + '</tr>'
        for p in investigation['positions'] for c in p['unit_checks'])
    tree_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [p['id'], t['steps'], t.get('price', t.get('error')), t.get('delta', ''), t.get('gamma', '')])
        + '</tr>' for p in investigation['positions'] for t in p['tree_diagnostics'])
    quote_rows = ''.join('<tr>' + ''.join('<td>' + esc(q[k]) + '</td>' for k in
        ['id', 'bid', 'ask', 'model_price', 'model_minus_mid', 'inside_supplied_spread']) + '</tr>'
        for q in investigation.get('quote_diagnostics', []))
    source_section = ''
    if 'source_context' in investigation:
        source_section = '<h2>Source quality and declared assumptions</h2><ul>' + ''.join(
            '<li>' + esc(x) + '</li>' for x in investigation['source_context'].get('assumptions', [])) + '</ul>'
        source_section += '<h2>Supplied quotes: conditional discrepancies</h2><div class="scroll"><table><tr><th>Contract</th><th>Bid</th><th>Ask</th><th>Model</th><th>Model minus mid</th><th>Inside spread</th></tr>' + quote_rows + '</table></div>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Independent option revaluation investigation</title>
<style>body{font:16px/1.6 system-ui;color:#23313d;background:#f4f6f8;margin:0}
main{max-width:1100px;margin:32px auto;padding:28px;background:white}
.scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #dde3e8}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}h1{font-size:28px}</style><main>
<h1>Independent option revaluation investigation</h1>
<p>Fixed contracts, conditional model comparisons and local-approximation risk.
This report is not market-price certification, trading performance or VaR.</p>
<p>QuantLib version: ''' + esc(investigation['quantlib_version']) + '''. Unit-level checks requiring investigation: ''' + esc(investigation['attention_count']) + '''.</p>
<h2>Scenario P&amp;L and approximation residual</h2><div class="scroll"><table><tr>
<th>Scenario</th><th>Workbench P&amp;L</th><th>Reference P&amp;L</th>
<th>Engine difference</th><th>Local approximation</th><th>Approximation residual</th></tr>''' + rows + '''</table></div>
''' + source_section + '''<h2>Independent unit-level checks</h2><p>Price, Delta and Gamma are compared before quantity and multiplier scaling. Thresholds flag investigation, not acceptance.</p><div class="scroll"><table><tr><th>Position</th><th>Metric</th><th>Workbench</th><th>Reference</th><th>Difference</th><th>Threshold</th><th>Status</th></tr>''' + unit_rows + '''</table></div><h2>CRR step sensitivity</h2><p>Odd/even sequences may oscillate. More steps do not guarantee monotonic improvement.</p><div class="scroll"><table><tr><th>Position</th><th>Steps</th><th>Unit price</th><th>Delta</th><th>Gamma</th></tr>''' + tree_rows + '''</table></div><h2>Interpretation and limits</h2><ul>''' + ''.join('<li>' + esc(x) + '</li>' for x in investigation['limits']) + '''</ul>
<details><summary>Frozen inputs, methods and complete diagnostics</summary><p>Includes 800/1600 FDM refinement. Numerical agreement does not establish source quality.</p><pre>''' + esc(json.dumps(investigation, indent=2, allow_nan=False)) + '</pre></details></main></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--context', type=Path, help='Optional local provenance and quote JSON; never uploaded')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new directory')
    try:
        raw = args.input.read_bytes()
        request = json.loads(raw)
        investigation = investigate(request)
        if args.context:
            context_bytes = args.context.read_bytes()
            attach_context(investigation, json.loads(context_bytes))
            investigation['context_sha256'] = hashlib.sha256(context_bytes).hexdigest()
        investigation['input_sha256'] = hashlib.sha256(raw).hexdigest()
        report = render(investigation)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'investigation.json').write_text(json.dumps(investigation, indent=2, allow_nan=False) + '\n')
        (args.output / 'report.html').write_text(report)
    except (ImportError, ValueError, KeyError, TypeError, OSError, RuntimeError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.output), "attention_count": investigation['attention_count'],
                      "status": "investigation_complete_not_model_approval"}))


if __name__ == '__main__':
    main()
