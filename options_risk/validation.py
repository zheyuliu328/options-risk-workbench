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
    "meaning": "Versioned investigation thresholds, not model approval bounds; new Greek thresholds are retrospective screening choices",
    "european": {"price_abs": 1e-8, "price_rel": 1e-10,
                 "delta_abs": 1e-8, "gamma_abs": 1e-9,
                 "vega_per_vol_point_abs": 1e-8, "rho_per_rate_point_abs": 1e-8,
                 "theta_per_day_abs": 1e-8},
    "american": {"price_abs": .01, "price_rel": .001,
                 "delta_abs": .005, "delta_rel": .01,
                 "gamma_abs": .0005, "gamma_rel": .05,
                 "vega_per_vol_point_abs": .0001, "vega_per_vol_point_rel": .01,
                 "rho_per_rate_point_abs": .0001, "rho_per_rate_point_rel": .01,
                 "theta_per_day_abs": .0001, "theta_per_day_rel": .01},
    "tree_steps": [150, 151, 300, 301, 600, 601],
    "fd_meshes": [800, 1600],
    "reference_refinement_fraction": .25,
    "revision": "5: matched zero-volatility European spot differences and separate tree price/Greek availability; retrospective, not blind validation",
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
        result = {"price": option.NPV(), "delta": option.delta(), "gamma": option.gamma()}
        if position['style'] == 'european' and volatility > 0:
            result['analytic_vega_per_vol_point'] = option.vega() * .01
        return result
    finally:
        settings.evaluationDate = previous


METRICS = ['price', 'delta', 'gamma', 'vega_per_vol_point',
           'rho_per_rate_point', 'theta_per_day']


def reference_sensitivities(request, position, valuation_date, spot, volatility, mesh=1600):
    """Independent engines with production units and explicit difference conventions."""
    base = reference(request, position, valuation_date, spot, volatility, mesh)
    day = date.fromisoformat(valuation_date)
    expiry = date.fromisoformat(position['expiry'])
    dv = max(.001, volatility * .001)
    output = dict(base)
    output['errors'] = {}
    output['conventions'] = {
        'price': {'unit': 'currency per underlying unit', 'method': 'independent engine price'},
        'delta': {'unit': 'currency per spot unit', 'method': 'independent engine derivative'},
        'gamma': {'unit': 'currency per squared spot unit', 'method': 'independent engine derivative'},
        'vega_per_vol_point': {
            'unit': 'currency per +0.01 absolute volatility',
            'method': ('analytic European Vega' if position['style'] == 'european' and volatility > 0
                       else 'central volatility difference' if volatility >= dv
                       else 'second-order forward volatility difference'),
            'volatility_bump': None if position['style'] == 'european' and volatility > 0 else dv},
        'rho_per_rate_point': {'unit': 'currency per +0.01 continuous annual rate',
                              'method': 'central rate difference, dividend yield held fixed',
                              'rate_bump': .0001},
        'theta_per_day': {'unit': 'currency per one calendar day elapsed',
                          'method': 'valuation date +1 calendar day, expiry fixed',
                          'calendar_days': 1},
    }
    if day >= expiry:
        for key in METRICS[1:]:
            output[key] = None
            output['errors'][key] = 'Expiry derivatives are not compared as smooth sensitivities.'
        return output

    def value(*, rate=None, vol=volatility, when=valuation_date, at_spot=spot):
        changed = dict(request)
        if rate is not None:
            changed['rate'] = rate
        return reference(changed, position, when, at_spot, vol, mesh)['price']

    def vega():
        if position['style'] == 'european' and volatility > 0:
            return base['analytic_vega_per_vol_point']
        if volatility >= dv:
            return (value(vol=volatility + dv) - value(vol=volatility - dv)) / (2 * dv) * .01
        return (-3 * base['price'] + 4 * value(vol=volatility + dv)
                - value(vol=volatility + 2 * dv)) / (2 * dv) * .01

    rate = request.get('rate', 0)
    methods = {
        'vega_per_vol_point': vega,
        'rho_per_rate_point': lambda: (value(rate=rate + .0001) - value(rate=rate - .0001)) / .0002 * .01,
        'theta_per_day': lambda: value(when=(day + timedelta(days=1)).isoformat()) - base['price'],
    }
    if position['style'] == 'european' and volatility == 0:
        ds = spot * .001
        for key in ('delta', 'gamma'):
            output['conventions'][key].update(
                method='matched central payoff difference; not a smooth derivative at a kink',
                spot_bump=ds)
        methods.update(
            delta=lambda: (value(at_spot=spot + ds) - value(at_spot=spot - ds)) / (2 * ds),
            gamma=lambda: (value(at_spot=spot + ds) - 2 * base['price']
                           + value(at_spot=spot - ds)) / (ds * ds))
    for key, method in methods.items():
        try:
            result = method()
            if not math.isfinite(result):
                raise ValueError('Independent Greek is non-finite.')
            output[key] = result
        except (RuntimeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            output[key] = None
            output['errors'][key] = str(exc)
    return output


def investigate(request):
    import QuantLib as ql
    result = analyse(request)  # Preserve the production input/error contract.
    start = date.fromisoformat(request['as_of'])
    output = {"policy": POLICY, "quantlib_version": ql.__version__,
              "request": request, "workbench": result, "positions": [],
              "scenario_reference": [], "limits": [
                  "Independent engines agree only conditional on shared input conventions.",
                  "American FDM refinement and CRR oscillation are diagnostics, not exact error bounds.",
                  "All five reported Greeks are compared with matched units; method differences remain explicit.",
                  "New Greek thresholds are retrospective screening choices, not independently calibrated approval bounds.",
                  "Workbench theta is a one-calendar-day change, not QuantLib instantaneous theta.",
                  "No market quotation, source authenticity, profit or model approval is certified.",
                  "Expiry Greeks are nonsmooth and are not compared as differentiable values.",
                  "Zero-volatility European Delta/Gamma comparisons use matched spot payoff differences, not smooth derivatives at a kink.",
                  "An unavailable base reference or production Greek fails the investigation explicitly; no complete report is claimed.",
                  "Exact-zero American volatility can make the independent FDM grid degenerate; no positive volatility is substituted."]}
    for position in request['positions']:
        args = dict(spot=request['spot'], strike=position['strike'],
                    years=(date.fromisoformat(position['expiry']) - start).days / 365,
                    rate=request.get('rate', 0), dividend_yield=request.get('dividend_yield', 0),
                    volatility=position['volatility'], kind=position['kind'], style=position['style'])
        fine = reference_sensitivities(request, position, request['as_of'], request['spot'], position['volatility'])
        coarse = reference_sensitivities(request, position, request['as_of'], request['spot'],
                           position['volatility'], 800)
        own = {"price": price(**args), **greeks(**args)}
        policy = POLICY[position['style']]
        checks = []
        for metric in METRICS:
            expected = fine[metric]
            if expected is None or coarse.get(metric) is None:
                checks.append({"metric": metric, "own": own.get(metric), "reference": expected,
                               "status": "reference_unavailable",
                               "detail": fine['errors'].get(metric) or coarse['errors'].get(metric),
                               "convention": fine['conventions'][metric]})
                continue
            threshold = max(policy[metric + '_abs'],
                            policy.get(metric + '_rel', 0) * abs(expected))
            difference = own[metric] - expected
            refinement = expected - coarse[metric]
            reference_threshold = threshold * POLICY['reference_refinement_fraction']
            reference_stable = abs(refinement) <= reference_threshold
            checks.append({"metric": metric, "convention": fine["conventions"][metric],
                           "own": own[metric], "reference": expected,
                           "difference": difference, "threshold": threshold,
                           "reference_mesh_difference": refinement,
                           "reference_mesh_threshold": reference_threshold,
                           "own_threshold_exceeded": abs(difference) > threshold,
                           "status": ('reference_mesh_unstable' if not reference_stable else
                                      'investigate' if abs(difference) > threshold else 'within_threshold')})
        tree = []
        if position['style'] == 'american':
            for steps in POLICY['tree_steps']:
                row = {'steps': steps}
                try:
                    row.update(price=price(**args, steps=steps), price_status='available')
                except (ValueError, OverflowError, ZeroDivisionError) as exc:
                    row.update(price_status='unavailable', price_error=str(exc), error=str(exc))
                try:
                    row.update(**greeks(**args, steps=steps), greek_status='available')
                except (ValueError, OverflowError, ZeroDivisionError) as exc:
                    row.update(greek_status='unavailable', greek_error=str(exc), error=str(exc))
                tree.append(row)
        exposure = position['quantity'] * position['multiplier']
        scaled = [{"metric": c['metric'], "own": c.get('own') * exposure if c.get('own') is not None else None,
                   "reference": c.get('reference') * exposure if c.get('reference') is not None else None,
                   "difference": c.get('difference') * exposure if c.get('difference') is not None else None,
                   "status": c['status']} for c in checks]
        output['positions'].append({"id": position['id'], "unit_checks": checks,
                                    "signed_exposure": exposure, "scaled_checks": scaled,
                                    "reference_800": coarse, "reference_1600": fine,
                                    "fd_price_refinement": fine['price'] - coarse['price'],
                                    "tree_diagnostics": tree})
    reference_base = sum(p['reference_1600']['price'] * p['signed_exposure']
                         for p in output['positions'])
    coarse_base = sum(p['reference_800']['price'] * p['signed_exposure']
                      for p in output['positions'])
    for scenario, actual in zip(request['scenarios'], result['scenarios']):
        when = (start + timedelta(days=scenario.get('days', 0))).isoformat()
        new_spot = request['spot'] * (1 + scenario.get('spot_return', 0))
        values = {800: 0.0, 1600: 0.0}
        refinements = []
        for p, base in zip(request['positions'], output['positions']):
            scenario_prices = {mesh: reference(request, p, when, new_spot,
                p['volatility'] + scenario.get('vol_change', 0), mesh)['price']
                for mesh in values}
            exposure = base['signed_exposure']
            for mesh in values:
                values[mesh] += scenario_prices[mesh] * exposure
            pnl_refinement = ((scenario_prices[1600] - base['reference_1600']['price']) -
                              (scenario_prices[800] - base['reference_800']['price'])) * exposure
            price_policy = POLICY[p['style']]
            # Sum the two endpoint screening scales; this is not an error bound.
            endpoint_scale = sum(max(price_policy['price_abs'],
                price_policy.get('price_rel', 0) * abs(v)) for v in
                (scenario_prices[1600], base['reference_1600']['price']))
            threshold = abs(exposure) * endpoint_scale * POLICY['reference_refinement_fraction']
            refinements.append({'id': p['id'], 'signed_exposure': exposure,
                'pnl_mesh_difference': pnl_refinement, 'mesh_threshold': threshold,
                'status': 'reference_mesh_unstable' if abs(pnl_refinement) > threshold
                          else 'within_refinement_screen'})
        approximate = sum(p['greek_approximation'] for p in actual['positions'])
        reference_pnl = values[1600] - reference_base
        output['scenario_reference'].append({'name': scenario['name'],
            'workbench_pnl': actual['pnl'], 'reference_pnl': reference_pnl,
            'engine_pnl_difference': actual['pnl'] - reference_pnl,
            'workbench_local_approximation': approximate,
            'workbench_approximation_residual': actual['pnl'] - approximate,
            'reference_pnl_800': values[800] - coarse_base,
            'reference_pnl_mesh_difference': reference_pnl - (values[800] - coarse_base),
            'reference_refinement_status': 'reference_mesh_unstable' if any(
                row['status'] == 'reference_mesh_unstable' for row in refinements)
                else 'within_refinement_screen',
            'position_refinement': refinements})
    output['scenario_attention_count'] = sum(row['reference_refinement_status'] ==
        'reference_mesh_unstable' for row in output['scenario_reference'])
    output['attention_count'] = sum(c['status'] in ['investigate', 'reference_mesh_unstable', 'reference_unavailable']
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
        midpoint = bid + (ask - bid) / 2
        difference = own - midpoint
        if not math.isfinite(midpoint) or not math.isfinite(difference):
            raise ValueError('quote comparison exceeds numeric range')
        diagnostics.append({"id": identity, "bid": bid, "ask": ask,
                            "model_price": own, "model_minus_mid": difference,
                            "inside_supplied_spread": bid <= own <= ask,
                            "interpretation": "Conditional discrepancy only; timing, rates, dividends and IV may differ"})
    investigation['source_context'] = context
    investigation['quote_diagnostics'] = diagnostics
    investigation['limits'].append('Supplied quote rows and provenance declarations are not authenticated by the tool.')


def render(investigation):
    def esc(value):
        return html.escape(format(value, '.8g') if isinstance(value, float) else str(value))
    request = investigation['request']
    portfolio_rows = ''.join('<tr>' + ''.join('<td>' + esc(p[k]) + '</td>' for k in
        ['id', 'kind', 'style', 'strike', 'expiry', 'quantity', 'multiplier', 'volatility'])
        + '</tr>' for p in request['positions'])
    portfolio = '<h2>Fixed portfolio and valuation inputs</h2><p>' + esc(request['underlying']) + ' | ' + esc(request['currency']) + ' | Valuation date: ' + esc(request['as_of']) + '<br>Spot: ' + esc(request['spot']) + ' | Annual continuous rate: ' + esc(request.get('rate', 0)) + ' | Continuous dividend yield: ' + esc(request.get('dividend_yield', 0)) + '<br>Current model portfolio value: ' + esc(investigation['workbench']['market_value']) + '</p><div class="scroll"><table><tr><th>ID</th><th>Type</th><th>Style</th><th>Strike</th><th>Expiry</th><th>Quantity</th><th>Multiplier</th><th>Annual vol (ratio)</th></tr>' + portfolio_rows + '</table></div>'
    rows = ''.join('<tr>' + ''.join('<td>' + esc(row[k]) + '</td>' for k in
        ['name', 'workbench_pnl', 'reference_pnl', 'engine_pnl_difference',
         'workbench_local_approximation', 'workbench_approximation_residual']) + '</tr>'
        for row in investigation['scenario_reference'])
    scenario_grid_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [row['name'], p['id'], p['pnl_mesh_difference'], p['mesh_threshold'], p['status']]) + '</tr>'
        for row in investigation['scenario_reference'] for p in row.get('position_refinement', []))
    unit_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [p['id'], c['metric'], c.get('own', 'not compared'), c.get('reference', ''),
         c.get('difference', ''), c.get('threshold', ''), c.get('reference_mesh_difference', ''),
         c.get('reference_mesh_threshold', ''), c['status'], c.get('convention', {}).get('unit', ''),
         c.get('detail') or c.get('convention', {}).get('method', '')]) + '</tr>'
        for p in investigation['positions'] for c in p['unit_checks'])
    tree_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [p['id'], t['steps'], t.get('price', ''), t.get('price_status', ''),
         t.get('delta', ''), t.get('gamma', ''), t.get('vega_per_vol_point', ''),
         t.get('rho_per_rate_point', ''), t.get('theta_per_day', ''), t.get('greek_status', ''),
         '; '.join(x for x in (t.get('price_error'), t.get('greek_error')) if x)])
        + '</tr>' for p in investigation['positions'] for t in p['tree_diagnostics'])
    scaled_rows = ''.join('<tr>' + ''.join('<td>' + esc(value) + '</td>' for value in
        [p['id'], p['signed_exposure'], c['metric'], c.get('own'), c.get('reference'),
         c.get('difference'), c['status']]) + '</tr>'
        for p in investigation['positions'] for c in p['scaled_checks'])
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
<p>QuantLib version: ''' + esc(investigation['quantlib_version']) + '''. Unit-level checks requiring investigation: ''' + esc(investigation['attention_count']) + '''. Scenarios with unstable reference P&amp;L: ''' + esc(investigation.get('scenario_attention_count', 0)) + '''.</p>
''' + portfolio + '''<h2>Scenario P&amp;L and approximation residual</h2><div class="scroll"><table><tr>
<th>Scenario</th><th>Workbench P&amp;L</th><th>Reference P&amp;L</th>
<th>Engine difference</th><th>Local approximation</th><th>Approximation residual</th></tr>''' + rows + '''</table></div>
''' + source_section + '''<h2>Scenario reference P&amp;L refinement</h2><p>Each position's reference P&amp;L is rebuilt on both grids. Offsetting position errors cannot hide an unstable position. The screen sums the base and shocked price scales, multiplied by absolute exposure; it is retrospective and is not a numerical error bound or a risk limit. Stable P&amp;L refinement does not establish stable endpoint prices or workbench agreement.</p><div class="scroll"><table><tr><th>Scenario</th><th>Position</th><th>P&amp;L mesh difference</th><th>Mesh threshold</th><th>Status</th></tr>''' + scenario_grid_rows + '''</table></div><h2>Independent unit-level checks</h2><p>Price and all five reported Greeks are compared before signed quantity and multiplier scaling. Vega is per volatility point, Rho per rate point and Theta is the next-calendar-day value change. Reference refinement is calculated separately for each sensitivity. Thresholds flag investigation, not acceptance; added Greek screening thresholds are retrospective.</p><div class="scroll"><table><tr><th>Position</th><th>Metric</th><th>Workbench</th><th>Reference</th><th>Difference</th><th>Threshold</th><th>Reference mesh difference</th><th>Mesh threshold</th><th>Status</th><th>Unit</th><th>Method / unavailable reason</th></tr>''' + unit_rows + '''</table></div><h2>CRR step sensitivity</h2><p>Odd/even sequences may oscillate. More steps do not guarantee monotonic improvement.</p><div class="scroll"><table><tr><th>Position</th><th>Steps</th><th>Unit price</th><th>Price status</th><th>Delta</th><th>Gamma</th><th>Vega / point</th><th>Rho / point</th><th>Theta / day</th><th>Greek status</th><th>Unavailable reason</th></tr>''' + tree_rows + '''</table></div><h2>Signed position comparisons</h2><p>Unit values are multiplied by quantity × multiplier. A short position reverses the sign. Unit-level status is retained; no portfolio acceptance threshold is inferred.</p><div class="scroll"><table><tr><th>Position</th><th>Signed exposure</th><th>Metric</th><th>Workbench</th><th>Reference</th><th>Difference</th><th>Unit status</th></tr>''' + scaled_rows + '''</table></div><h2>Interpretation and limits</h2><ul>''' + ''.join('<li>' + esc(x) + '</li>' for x in investigation['limits']) + '''</ul>
<details><summary>Frozen inputs, methods and complete diagnostics</summary><p>Includes 800/1600 FDM refinement. Numerical agreement does not establish source quality.</p><pre>''' + esc(json.dumps(investigation, indent=2, allow_nan=False)) + '</pre></details></main></html>'


def main():
    from .file_inputs import DOWNLOAD_LIMIT, portfolio_input
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--context', type=Path, help='Optional local provenance and quote JSON; never uploaded')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new directory')
    try:
        raw = args.input.read_bytes()
        request, input_format = portfolio_input(json.loads(raw))
        investigation = investigate(request)
        investigation['input_format'] = input_format
        if input_format == 'browser_portfolio_export':
            investigation['limits'].append(DOWNLOAD_LIMIT)
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
                      "scenario_attention_count": investigation['scenario_attention_count'],
                      "status": "investigation_complete_not_model_approval"}))


if __name__ == '__main__':
    main()
