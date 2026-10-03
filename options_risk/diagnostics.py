"""Bounded single-contract numerical diagnostics; no automatic model selection."""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path

from .pricing import _validate, greeks, price
from .scenarios import fields, finite_output, iso_date, number

STEPS = (150, 151, 300, 301, 600, 601)
VOL_BUMPS = (.0005, .001, .002)
RATE_BUMPS = (.00005, .0001, .0002)


def _attempt(function):
    try:
        return {"status": "available", "value": finite_output(function())}
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        return {"status": "unavailable", "value": None, "reason": str(exc)}


def diagnose(request, position_id=None):
    """Review one selected contract, not the remaining positions or scenarios."""
    fields(request, ['as_of', 'spot', 'rate', 'dividend_yield', 'positions', 'scenarios', 'underlying', 'currency'],
           ['as_of', 'spot', 'positions', 'underlying', 'currency'], 'request')
    positions = request['positions']
    if not isinstance(positions, list) or not 1 <= len(positions) <= 30:
        raise ValueError('provide 1–30 positions and select one for diagnostics')
    ids = [p.get('id') if isinstance(p, dict) else None for p in positions]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('position ids must be nonempty and unique')
    if position_id is None:
        if len(positions) != 1:
            raise ValueError('select a position id when the request contains multiple positions')
        position_id = ids[0]
    if position_id not in ids:
        raise ValueError('selected position id does not exist')
    position = positions[ids.index(position_id)]
    required = ['id', 'expiry', 'quantity', 'multiplier', 'strike', 'volatility', 'kind', 'style']
    fields(position, required, required, 'selected position')
    asof, expiry = iso_date(request['as_of'], 'as_of'), iso_date(position['expiry'], 'expiry')
    if expiry <= asof:
        raise ValueError('selected position must expire after the valuation date; expiry Greeks are nonsmooth')
    for key in ('underlying', 'currency'):
        if not isinstance(request[key], str) or not request[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    qty, multiplier = number(position['quantity'], 'quantity'), number(position['multiplier'], 'multiplier')
    if qty == 0 or not qty.is_integer() or multiplier <= 0 or not multiplier.is_integer():
        raise ValueError('quantity must be a nonzero signed integer and multiplier a positive integer')
    exposure = number(qty * multiplier, 'signed exposure')
    args = dict(spot=number(request['spot'], 'spot'), strike=number(position['strike'], 'strike'),
                years=(expiry - asof).days / 365, rate=number(request.get('rate', 0), 'rate'),
                dividend_yield=number(request.get('dividend_yield', 0), 'dividend_yield'),
                volatility=number(position['volatility'], 'volatility'), kind=position['kind'],
                style=position['style'])
    _validate(**args, steps=300)  # Structural checks; probability failures belong in each diagnostic row.
    snapshot = {k: copy.deepcopy(request[k]) for k in ('as_of', 'underlying', 'currency', 'spot')}
    snapshot.update(rate=args['rate'], dividend_yield=args['dividend_yield'], position=copy.deepcopy(position))
    steps = []
    for count in STEPS:
        p = _attempt(lambda: price(**args, steps=count))
        g = _attempt(lambda: greeks(**args, steps=count))
        steps.append({'steps': count, 'price': p, 'greeks': g,
            'signed_price': _attempt(lambda: p['value'] * exposure) if p['status'] == 'available' else p.copy(),
            'signed_greeks': _attempt(lambda: {k: v * exposure for k, v in g['value'].items()})
                             if g['status'] == 'available' else g.copy()})
    bumps = []
    for field, sizes, output_name in [('volatility', VOL_BUMPS, 'vega_per_vol_point'),
                                      ('rate', RATE_BUMPS, 'rho_per_rate_point')]:
        for bump in sizes:
            forward = field == 'volatility' and args[field] < bump
            changes = (0, bump, 2 * bump) if forward else (-bump, bump)
            endpoints = [{'input_value': args[field] + change,
                          'price': _attempt(lambda change=change: price(
                              **(args | {field: args[field] + change}), steps=300))}
                         for change in changes]
            def sensitivity():
                if any(p['price']['status'] != 'available' for p in endpoints):
                    raise ValueError('; '.join(p['price']['reason'] for p in endpoints
                                              if p['price']['status'] != 'available'))
                values = [p['price']['value'] for p in endpoints]
                return ((-3 * values[0] + 4 * values[1] - values[2]) / (2 * bump) if forward
                        else (values[1] - values[0]) / (2 * bump)) * .01
            value = _attempt(sensitivity)
            bumps.append({'metric': output_name, 'steps': 300, 'absolute_bump': bump, 'endpoints': endpoints,
                          'method': 'second-order forward' if forward else 'central',
                          **value, 'signed': _attempt(lambda: value['value'] * exposure)
                          if value['status'] == 'available' else value.copy()})
    limits = [
        'Only the selected contract is examined; other positions and all scenarios are not validated here.',
        'All step counts and bumps are fixed in advance. No best row is chosen and no portfolio input is changed.',
        'This is within-engine sensitivity, not an independent reference, convergence proof or error bound.',
        'More steps and smaller bumps need not improve a Greek. Failed rows remain visible.',
        'Vega and Rho are per +0.01 absolute volatility/rate; Theta is per calendar day elapsed.',
        'European production Vega is analytic; the bump table deliberately shows finite-difference estimates.',
        'Continuous yields, flat contract volatility and ACT/365 apply; no discrete cash dividends or trading costs.',
        'Unscaled unit values are multiplied by signed quantity times multiplier for position values.',
        'Expiry Greeks are nonsmooth; this task requires a future expiry and does not certify model approval.',
    ]
    output = {'schema_version': 1, 'input_position_count': len(positions), 'selected_position_id': position_id, 'selected_input': snapshot, 'signed_exposure': exposure,
              'step_results': steps, 'bump_results': bumps, 'limits': limits,
              'policy': {'step_counts': list(STEPS), 'volatility_bumps': list(VOL_BUMPS),
                         'rate_bumps': list(RATE_BUMPS), 'bump_steps': 300,
                         'selection': 'No automatic best result or production default change'}}
    output['fingerprint'] = hashlib.sha256(json.dumps({'input': snapshot, 'policy': output['policy']},
        sort_keys=True, allow_nan=False).encode()).hexdigest()
    output['unavailable_count'] = sum(row[key]['status'] == 'unavailable' for row in steps
                                    for key in ('price', 'greeks', 'signed_price', 'signed_greeks')) + sum(
        int(row['status'] == 'unavailable') + int(row['signed']['status'] == 'unavailable') for row in bumps)
    output['unavailable_count_definition'] = 'Failed unit price, unit Greek bundle, signed price, signed Greek bundle and unit/signed bump checks; not distinct failed contracts'
    return finite_output(output)


def render(result):
    def esc(value):
        return html.escape(str(value))
    def value(check):
        return esc(format(check['value'], '.8g')) if check['status'] == 'available' else esc(check['reason'])
    selected = result['selected_input']
    contract = selected['position']
    summary = '<dl>' + ''.join('<dt>' + esc(label) + '</dt><dd>' + esc(val) + '</dd>' for label, val in [
        ('Contract', contract['id']), ('Underlying / currency', selected['underlying'] + ' / ' + selected['currency']),
        ('Valuation / expiry', selected['as_of'] + ' / ' + contract['expiry']),
        ('Type / exercise', contract['kind'] + ' / ' + contract['style']),
        ('Spot / strike', str(selected['spot']) + ' / ' + str(contract['strike'])),
        ('Quantity × multiplier', str(contract['quantity']) + ' × ' + str(contract['multiplier'])),
        ('Annual volatility (ratio)', contract['volatility']),
        ('Annual rate / continuous yield (ratios)', str(selected['rate']) + ' / ' + str(selected['dividend_yield'])),
        ('Unavailable checks', result['unavailable_count']),
    ]) + '</dl>'
    signed_rows = ''
    for row in result['step_results']:
        check = row['signed_greeks']
        g = check['value'] or {}
        cells = [str(row['steps'])] + [esc(format(g[k], '.8g')) if k in g else 'Unavailable' for k in
                  ('delta', 'gamma', 'vega_per_vol_point', 'rho_per_rate_point', 'theta_per_day')]
        cells += [esc(check.get('reason', 'Available'))]
        signed_rows += '<tr>' + ''.join('<td>' + c + '</td>' for c in cells) + '</tr>'
    rows = ''
    for row in result['step_results']:
        g = row['greeks']['value'] or {}
        cells = [row['steps'], value(row['price']), value(row['signed_price'])]
        cells += [esc(format(g[k], '.8g')) if k in g else 'Unavailable' for k in
                  ('delta', 'gamma', 'vega_per_vol_point', 'rho_per_rate_point', 'theta_per_day')]
        cells += [esc(row['greeks'].get('reason', 'Available; not a stability certificate')),
                  esc(row['signed_greeks'].get('reason', 'Available'))]
        rows += '<tr>' + ''.join('<td>' + str(c) + '</td>' for c in cells) + '</tr>'
    bump_rows = ''.join('<tr>' + ''.join('<td>' + x + '</td>' for x in [esc(row['metric']),
        esc(row['absolute_bump']), esc(row['method']), value(row), value(row['signed'])]) + '</tr>'
        for row in result['bump_results'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Option numerical sensitivity</title><style>body{font:16px/1.6 system-ui;color:#23313d;background:#f4f6f8;margin:0}main{max-width:1100px;margin:auto;padding:28px;background:white}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap;overflow-wrap:anywhere}dl{display:grid;grid-template-columns:minmax(140px,1fr) 2fr;gap:8px 20px}dt{font-weight:600}dd{margin:0;overflow-wrap:anywhere}</style><main>
<h1>Option numerical sensitivity</h1><p>One fixed contract, multiple numerical resolutions. No best result is selected.</p>
<h2>Selected contract</h2>''' + summary + '<p>' + esc(result['unavailable_count_definition']) + '''. Availability is not evidence of numerical stability.</p>
<h2>Step sensitivity</h2><p>Prices and Greeks are per underlying unit unless explicitly signed. Signed price uses quantity × multiplier. Signed position Greeks are listed in the next table.</p><div class="scroll"><table><tr><th>Steps</th><th>Unit price</th><th>Signed value</th><th>Delta</th><th>Gamma</th><th>Vega / point</th><th>Rho / point</th><th>Theta / day</th><th>Unit Greek status</th><th>Signed Greek status</th></tr>''' + rows + '''</table></div>
<h2>Signed position sensitivities</h2><p>All values include signed quantity × multiplier. Delta is currency per spot unit; Gamma is currency per spot unit squared; Vega and Rho are currency per +0.01 absolute volatility or rate; Theta is currency per calendar day elapsed.</p><div class="scroll"><table><tr><th>Steps</th><th>Delta</th><th>Gamma</th><th>Vega / point</th><th>Rho / point</th><th>Theta / day</th><th>Status</th></tr>''' + signed_rows + '''</table></div>
<h2>Fixed 300-step bump sensitivity</h2><p>The bump size is an absolute ratio. Vega/Rho outputs are per +0.01, regardless of bump size. These estimates do not replace production Greeks.</p><div class="scroll"><table><tr><th>Metric</th><th>Absolute bump</th><th>Method</th><th>Unit sensitivity</th><th>Signed sensitivity</th></tr>''' + bump_rows + '''</table></div><h2>Limits</h2><ul>''' + ''.join('<li>' + esc(x) + '</li>' for x in result['limits']) + '''</ul><details><summary>Complete frozen diagnostics</summary><pre>''' + esc(json.dumps(result, indent=2, allow_nan=False)) + '</pre></details></main></html>'


def main():
    from .file_inputs import DOWNLOAD_LIMIT, portfolio_input, load_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--position')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new directory')
    try:
        raw = args.input.read_bytes()
        request, input_format = portfolio_input(load_download(raw))
        result = diagnose(request, args.position)
        result['input_sha256'] = hashlib.sha256(raw).hexdigest()
        result['input_format'] = input_format
        if input_format != 'portfolio_request':
            result['limits'].append(DOWNLOAD_LIMIT)
        report = render(result)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'diagnostics.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        (args.output / 'report.html').write_text(report)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output), 'unavailable_count': result['unavailable_count'],
                      'status': 'diagnostics_only_no_automatic_selection'}))


if __name__ == '__main__':
    main()
