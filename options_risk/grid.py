"""Fixed-contract sampled spot curves; no paid-premium or probability claims."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, localcontext
from html import escape
import argparse
import hashlib
import json
import math
from pathlib import Path

from .scenarios import analyse, fields, finite_output, iso_date, number
from .report import render as render_portfolio


def prepare(request):
    fields(request, ['schema_version', 'portfolio', 'grid', 'source_note'],
           ['schema_version', 'portfolio', 'grid'], 'price-grid request')
    if type(request['schema_version']) is not int or request['schema_version'] != 1:
        raise ValueError('price-grid schema_version must be 1')
    if 'source_note' in request and (not isinstance(request['source_note'], str)
                                    or len(request['source_note']) > 4000):
        raise ValueError('source_note must be text of at most 4000 characters')
    portfolio = request['portfolio']
    fields(portfolio, ['as_of','spot','rate','dividend_yield','positions','underlying','currency'],
           ['as_of','spot','positions','underlying','currency'], 'grid portfolio')
    grid = request['grid']
    fields(grid, ['lower_return','upper_return','points','days','vol_change'],
           ['lower_return','upper_return','points','days','vol_change'], 'grid')
    lo = number(grid['lower_return'], 'lower_return')
    hi = number(grid['upper_return'], 'upper_return')
    if not -1 < lo <= 0 <= hi or lo >= hi:
        raise ValueError('grid returns must span zero, with -1 < lower_return < upper_return')
    count = grid['points']
    if type(count) is not int or not 3 <= count <= 29:
        raise ValueError('grid points must be an integer from 3 to 29 (plus a zero-return anchor if needed)')
    days = grid['days']
    if type(days) is not int or days < 0:
        raise ValueError('grid days must be a nonnegative integer')
    vol = number(grid['vol_change'], 'vol_change')
    asof = iso_date(portfolio['as_of'], 'as_of')
    if days > (iso_date('9999-12-31', 'maximum date') - asof).days:
        raise ValueError('grid days exceeds the supported calendar range')
    spot = number(portfolio['spot'], 'spot')
    if spot <= 0:
        raise ValueError('spot must be positive')
    # Decimal interpolation avoids repeated-addition drift; pricing still uses binary floats.
    with localcontext() as ctx:
        ctx.prec = 400
        low, high = Decimal(str(lo)), Decimal(str(hi))
        returns = [float(low + (high-low)*i/(count-1)) for i in range(count)]
    if any(a >= b for a, b in zip(returns, returns[1:])):
        raise ValueError('grid returns collapse at numeric resolution; widen the range')
    if 0.0 not in returns:
        returns.append(0.0)
        returns.sort()
    spots = [spot*(1+x) for x in returns]
    if (any(not math.isfinite(x) or x <= 0 for x in spots)
            or any(a >= b for a, b in zip(spots, spots[1:]))):
        raise ValueError('grid prices overflow or collapse at numeric resolution; change the range')
    expanded = deepcopy(portfolio)
    expanded['scenarios'] = [dict(name=f'Grid node {i+1:02d}', spot_return=x,
                                  vol_change=vol, days=days) for i, x in enumerate(returns)]
    return expanded, spots, (asof+timedelta(days=days)).isoformat()


def review_grid(request):
    """Compute baseline once, then all nodes using the existing <=30-scenario engine."""
    expanded, spots, horizon = prepare(request)
    result = analyse(expanded)
    rows = []
    for scenario, spot in zip(result['scenarios'], spots):
        local = sum(p['greek_approximation'] for p in scenario['positions'])
        rows.append(dict(name=scenario['name'], spot=spot, spot_return=scenario['spot_return'],
                         value=sum(p['market_value'] for p in scenario['positions']),
                         change=scenario['pnl'], approximation=local, residual=scenario['pnl']-local,
                         positions=deepcopy(scenario['positions'])))
    return finite_output(dict(schema_version=1, task='price_grid', request=deepcopy(request),
        scenario_request=expanded, valuation=result, horizon=horizon, rows=rows,
        sampled_min_change=min(r['change'] for r in rows), sampled_max_change=max(r['change'] for r in rows),
        largest_abs_residual=max(abs(r['residual']) for r in rows),
        limits=[
            'Model-value change from the current valuation, not paid-premium trading profit.',
            'Prices are sampled nodes; connecting lines are visual guides, not extra valuations.',
            'Sampled extremes are neither full-domain extrema nor VaR or expected shortfall.',
            'All nodes share one elapsed time and volatility change; rates and dividend yield stay fixed.',
            'Zero spot return need not mean zero value change when time or volatility changes.',
            'No settlement ledger beyond the earliest expiry; no discrete dividends, fees or financing.',
            'Full revaluation still retains the underlying model and American 300-step tree error.',
            'Approximation omits higher-order and cross terms; inspect signed and absolute residuals.',
            'Grid request can be replayed by the grid CLI. Expanded scenario request uses the native '
            'portfolio CLI; more than 10 scenarios exceed the existing scenario-editor import limit.'
        ]))


def plot_svg(result):
    """Accessible static plot; the exact values remain in the accompanying table."""
    rows = result['rows']
    values = [r[k] for r in rows for k in ('change','approximation')] + [0.0]
    scale = max(max(abs(v) for v in values), 1.0)
    low, high = min(values)/scale, max(values)/scale
    if high == low:
        low, high = -1.0, 1.0
    sx = max(abs(rows[0]['spot']), abs(rows[-1]['spot']), 1.0)
    x0, x1 = rows[0]['spot']/sx, rows[-1]['spot']/sx
    def xy(row, key):
        return f"{80+680*(row['spot']/sx-x0)/(x1-x0):.3f},{270-220*(row[key]/scale-low)/(high-low):.3f}"
    lines = ''.join(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" '
                    f'{dash} points="'+ ' '.join(xy(r,k) for r in rows)+'"/>'
                    for k,color,dash in [('change','#264c71',''),('approximation','#a35b2d','stroke-dasharray="7 5"')])
    unit = escape(result['valuation']['currency'])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 330" width="100%" role="img" '
            f'aria-label="Sampled model-value change versus spot price in {unit}">'
            '<title>Full revaluation (solid blue) and local approximation (dashed brown)</title>'
            '<rect width="840" height="330" fill="white"/>'
            '<path d="M80 40V270H770" fill="none" stroke="#708090"/>'
            f'<path d="M80 {270-220*(0-low)/(high-low):.3f}H770" stroke="#ccd3dc"/>'
            f'{lines}<g fill="#23313d" font-family="sans-serif" font-size="14">'
            f'<text x="80" y="305">Spot {rows[0]["spot"]:.17g}</text>'
            f'<text x="760" y="305" text-anchor="end">{rows[-1]["spot"]:.17g}</text>'
            f'<text x="8" y="50">{high*scale:.4g}</text><text x="8" y="270">{low*scale:.4g}</text>'
            f'<text x="80" y="25">Value change ({unit})</text></g></svg>')


def render_grid(result):
    esc = lambda value: escape(str(value), quote=True)
    headers = ['Spot','Spot return (fraction)','Model value','Full change','Local approximation','Residual']
    keys = ['spot','spot_return','value','change','approximation','residual']
    table = '<div class="scroll"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'
    table += ''.join('<tr>'+''.join('<td>'+esc(str(r[k]))+'</td>' for k in keys)+'</tr>' for r in result['rows'])
    table += '</tbody></table></div>'
    grid = result['request']['grid']
    block = ('<h1>Portfolio price-range review</h1><p>Model-value change from current valuation. '
             'Full revaluation: solid blue. Local approximation: dashed brown.</p>'
             f'<p>Scenario date {esc(result["horizon"])}; elapsed days {esc(grid["days"])}; '
             f'volatility change {esc(grid["vol_change"])} (absolute fraction); '
             f'{len(result["rows"])} sampled prices, including zero spot return.</p>'
             +plot_svg(result)+table+'<h2>Curve limits</h2><ul>'
             +''.join('<li>'+esc(x)+'</li>' for x in result['limits'])+'</ul>')
    return render_portfolio(result['valuation'],result['scenario_request'],
                            result['request'].get('source_note')).replace('<main>', '<main>'+block, 1)


def main():
    from .file_inputs import load_download
    parser = argparse.ArgumentParser(description='Sample a fixed-contract portfolio over a spot-price range')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New directory for replayable outputs')
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('output exists; choose a new directory')
        with args.input.open('rb') as handle:
            raw = handle.read(1024*1024+1)
        if len(raw) > 1024*1024:
            raise ValueError('grid request limit: 1 MiB')
        request = load_download(raw)
        result = review_grid(request)
        payloads = {'request.json':request,'scenario-request.json':result['scenario_request'],'results.json':result}
        files = {name:(json.dumps(value,indent=2,allow_nan=False)+'\n').encode() for name,value in payloads.items()}
        files['report.html'] = render_grid(result).encode()
        files['manifest.json'] = (json.dumps({'schema_version':1,'input_sha256':hashlib.sha256(raw).hexdigest(),
            'files_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
            'source_code_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in ['grid.py','scenarios.py','pricing.py','report.py','file_inputs.py']}},indent=2)+'\n').encode()
        args.output.mkdir(parents=True,exist_ok=False)
        for name,data in files.items():
            with (args.output/name).open('xb') as handle:
                handle.write(data)
        print(json.dumps({'output':str(args.output),'nodes':len(result['rows'])}))
    except (ValueError,TypeError,KeyError,OverflowError,OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
