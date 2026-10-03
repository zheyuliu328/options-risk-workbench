"""Quote-to-volatility diagnostics using the explicitly selected pricing model.

No market retrieval or portfolio mutation. Premiums are per underlying unit;
volatilities are annual ratios. American results invert a fixed CRR tree and
are numerical-model estimates, not a calibrated continuous-exercise surface.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import html
import json
import math
from pathlib import Path

from .pricing import _number, price


def implied_volatility(premium, *, spot, strike, years, rate, dividend_yield=0.,
                       kind="call", style="european", steps=300,
                       max_volatility=5., price_tolerance=1e-8):
    """Bracket an IV without returning a fabricated root at a price boundary.

    Both price residual and volatility bracket width must converge. Price
    tolerance is absolute, per underlying unit. Expiry and near-zero-volatility
    values cannot identify a reliable positive IV. American roots use only the
    admissible CRR probability domain; the excluded lower domain is reported.
    """
    premium = _number('premium', premium)
    cap = _number('max_volatility', max_volatility)
    tolerance = _number('price_tolerance', price_tolerance)
    if premium < 0 or not 0 < cap <= 10 or tolerance <= 0:
        raise ValueError('premium must be nonnegative; volatility cap must be in (0, 10]; price tolerance must be positive')
    args = dict(spot=spot, strike=strike, years=years, rate=rate,
                dividend_yield=dividend_yield, kind=kind, style=style, steps=steps)
    zero = price(**args, volatility=0.)  # Validate all contract inputs first.
    result = dict(premium=premium, model='BSM' if style == 'european' else 'CRR',
                  steps=steps if style == 'american' else None,
                  price_tolerance=tolerance, volatility_cap=cap, volatility=None,
                  repriced=None, residual=None, iterations=0)

    def finish(status, **values):
        return result | dict(status=status, **values)

    if years == 0:
        return finish('unidentified_at_expiry' if abs(premium-zero) <= tolerance
                      else 'inconsistent_expiry_price')
    if premium < zero - tolerance:
        return finish('below_model_lower_bound', lower_price=zero)
    if premium <= zero + tolerance:
        return finish('boundary_at_price_tolerance', lower_price=zero)
    try:
        upper = (spot * math.exp(-dividend_yield * years) if kind == 'call'
                 else strike * math.exp(-rate * years))
        if style == 'american':
            upper = max(upper, spot if kind == 'call' else strike)
    except OverflowError as exc:
        raise ValueError('discounted price bound exceeds numeric range') from exc
    if premium > upper + tolerance:
        return finish('above_model_upper_bound', upper_price=upper)
    if style == 'european' and premium >= upper-tolerance:
        return finish('unresolved_at_asymptotic_bound', upper_price=upper)
    floor = (max(1e-10, abs(rate-dividend_yield) * math.sqrt(years/steps) * (1+1e-10))
             if style == 'american' else 0.)
    result['volatility_floor'] = floor
    if floor >= cap:
        return finish('empty_search_domain')
    low_price = price(**args, volatility=floor)
    if premium <= low_price + tolerance:
        return finish('unresolved_at_tree_floor', lower_price=low_price)
    high_price = price(**args, volatility=cap)
    if premium > high_price + tolerance:
        return finish('above_search_cap', cap_price=high_price)
    if abs(premium-high_price) <= tolerance:
        return finish('unresolved_at_search_cap', cap_price=high_price)
    low, high = floor, cap
    for iteration in range(1, 101):
        sigma = (low+high)/2
        calculated = price(**args, volatility=sigma)
        residual = calculated-premium
        result.update(iterations=iteration)
        if residual < 0:
            low = sigma
        else:
            high = sigma
        if high-low <= 1e-9 and abs(residual) <= tolerance:
            bump_low, bump_high = max(floor, sigma-1e-4), min(cap, sigma+1e-4)
            move = price(**args, volatility=bump_high) - price(**args, volatility=bump_low)
            status = ('negative_price_slope' if move < -tolerance else
                      'low_price_sensitivity' if move <= 2*tolerance else 'solved')
            return finish(status, volatility=sigma, repriced=calculated, residual=residual,
                          volatility_bracket=[low, high],
                          vega_per_vol_point=move/(bump_high-bump_low)*.01)
    return finish('not_converged', volatility_bracket=[low, high])


def review_quotes(request):
    """Review a bounded collection without discarding bad quote rows."""
    allowed = {'as_of', 'underlying', 'currency', 'spot', 'rate', 'dividend_yield', 'quotes'}
    if not isinstance(request, dict) or set(request)-allowed:
        raise ValueError('unsupported quote-review input fields')
    try:
        json.dumps(request, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError('input must be standard JSON: NaN, Infinity and non-JSON values are not permitted') from exc
    for name in ['underlying','currency','as_of']:
        if not isinstance(request.get(name), str) or not request[name].strip():
            raise ValueError(name+' must be a nonempty string')
    start = date.fromisoformat(request['as_of'])
    quotes = request['quotes']
    if not isinstance(quotes, list) or not 1 <= len(quotes) <= 20:
        raise ValueError('provide 1 to 20 quote rows')
    rows = []
    identifiers = Counter(q.get('id') for q in quotes
                          if isinstance(q,dict) and isinstance(q.get('id'),str))
    for index, quote in enumerate(quotes, 1):
        row = dict(row=index, input=quote)
        try:
            if not isinstance(quote, dict) or set(quote)-{'id','kind','style','strike','expiry','bid','ask'}:
                raise ValueError('unsupported quote row fields')
            identity = quote['id']
            if not isinstance(identity, str) or not identity.strip() or identifiers[identity] != 1:
                raise ValueError('quote ID must be nonempty and unique')
            bid, ask = _number('bid', quote['bid']), _number('ask', quote['ask'])
            if not 0 <= bid <= ask:
                raise ValueError('quote requires nonnegative bid <= ask')
            args = dict(spot=request['spot'], strike=quote['strike'],
                        years=(date.fromisoformat(quote['expiry'])-start).days/365,
                        rate=request.get('rate',0.), dividend_yield=request.get('dividend_yield',0.),
                        kind=quote['kind'], style=quote['style'])
            row['estimates'] = {label: implied_volatility(value, **args)
                                for label, value in [('bid',bid),('mid',bid+(ask-bid)/2),('ask',ask)]}
            if quote['style'] == 'american':
                row['mid_step_diagnostics'] = [implied_volatility(bid+(ask-bid)/2, **args, steps=n)
                                               for n in [301,600,601]]
            row['status'] = ('solved' if all(x['status']=='solved' for x in row['estimates'].values())
                             else 'needs_review')
            if any(x['status'] != 'solved' for x in row.get('mid_step_diagnostics', [])):
                row['status'] = 'needs_review'
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            row.update(status='invalid_input', error=str(exc))
        rows.append(row)
    return dict(request=request, rows=rows, attention_count=sum(r['status']!='solved' for r in rows),
                limits=[
                    'Quotes are caller-supplied; timestamps, source authenticity and executable liquidity are not verified.',
                    'IV is conditional on spot, rates, continuous dividend yield, exercise style and ACT/365 maturity.',
                    'Bid/ask IV is a quote-implied range, not a statistical confidence interval.',
                    'American IV inverts a fixed CRR tree; odd/even and refined step results show discretisation sensitivity, not error bounds.',
                    'No discrete dividends, volatility-surface fit, no-arbitrage surface certification or investment advice.',
                    'Low-sensitivity or boundary prices do not identify a reliable positive volatility.',
                    'No portfolio volatility is changed automatically.'])


def render_quote_review(result):
    def esc(value):
        if value is None:
            return 'Unavailable'
        return html.escape(format(value,'.8g') if isinstance(value,float) else str(value))
    rows = ''
    for row in result['rows']:
        estimates = row.get('estimates', {})
        cells = [row['row'], row['input'].get('id','') if isinstance(row['input'],dict) else '', row['status']]
        for label in ['bid','mid','ask']:
            estimate = estimates.get(label,{})
            cells.append(format(estimate['volatility']*100,'.7g')+'% ('+estimate['status']+')' if estimate.get('volatility') is not None
                         else estimate.get('status',row.get('error','')))
        cells.append(estimates.get('mid',{}).get('residual',''))
        rows += '<tr>'+''.join('<td>'+esc(x)+'</td>' for x in cells)+'</tr>'
    request = result['request']
    inputs = ''.join('<tr>'+''.join('<td>'+esc(row['input'].get(key,''))+'</td>' for key in
        ['id','kind','style','strike','expiry','bid','ask'])+'</tr>'
        for row in result['rows'] if isinstance(row['input'],dict))
    steps = ''.join('<tr>'+''.join('<td>'+esc(value)+'</td>' for value in
        [row['input'].get('id',''), estimate['steps'],estimate['status'],estimate['volatility'],estimate['residual']])+'</tr>'
        for row in result['rows'] for estimate in row.get('mid_step_diagnostics',[]))
    summary = ' | '.join(esc(key)+': '+esc(request.get(key,0)) for key in
                         ['as_of','underlying','currency','spot','rate','dividend_yield'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Option quote review</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:32px auto;padding:20px;color:#23313d}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>Option quote review</h1><p>Bid, midpoint and ask implied volatility under the declared model. Premiums and residuals are per underlying unit.</p>
<p>'''+summary+'''</p><p>Rates and dividend yields are annual continuous ratios. Time is ACT/365.</p>
<h2>Declared quotes</h2><div class="scroll"><table><tr><th>ID</th><th>Type</th><th>Style</th><th>Strike</th><th>Expiry</th><th>Bid</th><th>Ask</th></tr>'''+inputs+'''</table></div>
<h2>Quote-implied volatility</h2><p>Rows needing review: '''+esc(result['attention_count'])+'''. Solved means numerical inversion converged in the declared model (300 steps for American options), not that the model or market inputs are validated.</p><div class="scroll"><table><tr><th>Row</th><th>ID</th><th>Status</th><th>Bid IV</th><th>Mid IV</th><th>Ask IV</th><th>Mid price residual</th></tr>'''+rows+'''</table></div>
<h2>American midpoint step sensitivity</h2><p>The main estimate uses 300 steps. The alternative estimates below use annual volatility ratios. Changes reflect model discretisation, not solver error bounds.</p><div class="scroll"><table><tr><th>ID</th><th>Steps</th><th>Status</th><th>IV ratio</th><th>Price residual</th></tr>'''+steps+'''</table></div>
<h2>Interpretation and limits</h2><ul>'''+''.join('<li>'+esc(x)+'</li>' for x in result['limits'])+'''</ul>
<details><summary>Complete inputs and diagnostics</summary><p>Volatility brackets describe numerical root search, not uncertainty from rounded quotes or model assumptions.</p><pre>'''+esc(json.dumps(result,indent=2,allow_nan=False))+'</pre></details></html>'


def main():
    from .file_inputs import DOWNLOAD_LIMIT, quote_input, load_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new directory')
    try:
        raw = args.input.read_bytes()
        request, input_format = quote_input(load_download(raw))
        result = review_quotes(request)
        result['input_format'] = input_format
        if input_format == 'quote_report':
            result['limits'].append(DOWNLOAD_LIMIT)
        result['input_sha256'] = hashlib.sha256(raw).hexdigest()
        encoded = json.dumps(result,indent=2,allow_nan=False)+'\n'
        report = render_quote_review(result)
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'result.json').write_text(encoded)
        (args.output/'report.html').write_text(report)
    except (KeyError,TypeError,ValueError,OSError,OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output':str(args.output),'attention_count':result['attention_count']}))


if __name__ == '__main__':
    main()
