"""Fixed-contract full revaluation. No trading-performance claims."""
from datetime import date, timedelta
import math
from .pricing import price, greeks


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} exceeds numeric range") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def iso_date(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO date") from exc


def finite_output(value):
    """Reject overflow even when every individual input was finite."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("portfolio calculation exceeds numeric range; reduce position or scenario magnitude")
    if isinstance(value, dict):
        for child in value.values():
            finite_output(child)
    elif isinstance(value, list):
        for child in value:
            finite_output(child)
    return value


def fields(value, allowed, required, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    if set(value) - set(allowed):
        raise ValueError(f'{name}: unsupported fields {sorted(set(value)-set(allowed))}')
    if set(required) - set(value):
        raise ValueError(f'{name}: missing fields {sorted(set(required)-set(value))}')


def analyse(request):
    """Value a single-underlying, single-currency portfolio under declared shocks.

    Volatility shocks are absolute (0.05 = five vol points). Rates and dividends
    are continuously compounded. ACT/365 calendar time. No financing/cash flows.
    """
    fields(request, ['as_of','spot','rate','dividend_yield','positions','scenarios','underlying','currency'],
           ['as_of','spot','positions','scenarios','underlying','currency'], 'request')
    for key in ['underlying','currency']:
        if not isinstance(request[key], str) or not request[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    asof = iso_date(request['as_of'], 'as_of')
    spot = number(request['spot'], 'spot')
    rate = number(request.get('rate', 0), 'rate')
    dividend = number(request.get('dividend_yield', 0), 'dividend_yield')
    if spot <= 0:
        raise ValueError('spot must be positive')
    positions = request['positions']
    shocks = request['scenarios']
    if not isinstance(positions, list) or not 1 <= len(positions) <= 30:
        raise ValueError('provide 1–30 positions')
    if not isinstance(shocks, list) or not 1 <= len(shocks) <= 30:
        raise ValueError('provide 1–30 scenarios')
    rows = []
    ids = set()
    total_greeks = {}
    for position in positions:
        required = ['id','expiry','quantity','multiplier','strike','volatility','kind','style']
        fields(position, required, required, 'position')
        identity = position['id']
        if not isinstance(identity, str) or not identity.strip() or identity in ids:
            raise ValueError('position ids must be nonempty and unique')
        ids.add(identity)
        expiry = iso_date(position['expiry'], 'expiry')
        if expiry <= asof:
            raise ValueError('positions must expire after the valuation date')
        qty = number(position['quantity'], 'quantity')
        multiplier = number(position['multiplier'], 'multiplier')
        if multiplier <= 0 or not multiplier.is_integer():
            raise ValueError('multiplier must be a positive integer')
        if not qty.is_integer() or qty == 0:
            raise ValueError('quantity must be a nonzero signed integer')
        args = dict(spot=spot, strike=number(position['strike'], 'strike'),
                    years=(expiry-asof).days/365, rate=rate,
                    volatility=number(position['volatility'], 'volatility'),
                    dividend_yield=dividend, kind=position['kind'],
                    style=position['style'], steps=300)
        value = price(**args)
        exposure = number(qty * multiplier, "quantity times multiplier")
        sensitivities = {k: v*exposure for k,v in greeks(**args).items()}
        for k,v in sensitivities.items():
            total_greeks[k] = total_greeks.get(k, 0) + v
        rows.append(dict(id=identity, expiry=expiry.isoformat(), strike=args['strike'],
                         quantity=qty, multiplier=multiplier, unit_value=value,
                         market_value=value*exposure, greeks=sensitivities,
                         _args=args, _exposure=exposure))
    scenario_results = []
    names = set()
    for scenario in shocks:
        fields(scenario, ['name','spot_return','vol_change','days'], ['name'], 'scenario')
        name = scenario['name']
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('scenario names must be nonempty and unique')
        names.add(name)
        move = number(scenario.get('spot_return', 0), 'spot_return')
        vol_move = number(scenario.get('vol_change', 0), 'vol_change')
        days = scenario.get('days', 0)
        if type(days) is not int or days < 0:
            raise ValueError('days must be a nonnegative integer')
        if move <= -1:
            raise ValueError('spot_return must be greater than -1')
        if days > (date.max - asof).days:
            raise ValueError("days exceeds the supported calendar range")
        scenario_date = asof + timedelta(days=days)
        changes = []
        for row in rows:
            if scenario_date > date.fromisoformat(row['expiry']):
                raise ValueError('scenario beyond expiry requires an exercise/settlement ledger; not supported')
            args = dict(row['_args'])
            args.update(spot=spot*(1+move), volatility=args['volatility']+vol_move,
                        years=(date.fromisoformat(row['expiry'])-scenario_date).days/365)
            shocked = price(**args)*row['_exposure']
            pnl = shocked-row['market_value']
            g = row['greeks']
            ds = spot*move
            approx = (g['delta']*ds + .5*g['gamma']*ds*ds
                      + g['vega_per_vol_point']*vol_move*100
                      + g['theta_per_day']*days)
            changes.append(dict(id=row['id'], strike=row['strike'], expiry=row['expiry'],
                                market_value=shocked, pnl=pnl,
                                greek_approximation=approx, approximation_residual=pnl-approx))
        scenario_results.append(dict(name=name, date=scenario_date.isoformat(),
                                     spot_return=move, vol_change=vol_move,
                                     pnl=sum(x['pnl'] for x in changes), positions=changes))
    for row in rows:
        del row['_args'], row['_exposure']
    return finite_output(dict(schema_version=1, underlying=request['underlying'], currency=request['currency'],
                as_of=asof.isoformat(), spot=spot, rate=rate, dividend_yield=dividend,
                market_value=sum(x['market_value'] for x in rows), greeks=total_greeks,
                positions=rows, scenarios=scenario_results,
                assumptions=['Single underlying and currency; signed quantities and explicit multipliers.',
                             'European BSM or American CRR, 300 steps; continuous dividend yield.',
                             'Flat per-position volatility; no smile recalibration or historical executable quotes.',
                             'ACT/365 calendar days; rates/dividends unchanged under shocks.',
                             'Model-value changes exclude fees, financing, realised exercise and assignment cash flows.',
                             'Greeks are local sensitivities: analytic European delta/gamma at positive time/volatility; other finite differences and tree Greeks retain numerical error.',
                             'Scenarios are hypothetical, not a backtest, prediction or trading recommendation.']))
