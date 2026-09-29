"""Independent vanilla-option valuation using only the Python standard library.

European options use Black--Scholes--Merton with continuous dividend yield.
American options use a Cox--Ross--Rubinstein tree, not an exchange settlement
model. Rates and volatility are decimals; time is ACT/365-style years. Prices
are per unit of underlying, before contract multipliers or transaction costs.
Greeks are numerical differences, not analytic Greeks. Tree Greeks can be
noisy, especially gamma near a strike or an exercise boundary; check convergence
across step counts before interpreting small differences.
"""

import math
from numbers import Real


def _number(name, value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return value


def _validate(spot, strike, years, rate, volatility, dividend_yield, kind, style, steps):
    values = tuple(_number(n, v) for n, v in (
        ("spot", spot), ("strike", strike), ("years", years),
        ("rate", rate), ("volatility", volatility), ("dividend_yield", dividend_yield)))
    spot, strike, years, rate, volatility, dividend_yield = values
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if years < 0 or volatility < 0:
        raise ValueError("years and volatility must be non-negative")
    if kind not in ("call", "put"):
        raise ValueError("kind must be 'call' or 'put'")
    if style not in ("european", "american"):
        raise ValueError("style must be 'european' or 'american'")
    if isinstance(steps, bool) or not isinstance(steps, int) or not 50 <= steps <= 2000:
        raise ValueError("steps must be an integer between 50 and 2000")
    return values


def _cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _deterministic(spot, strike, years, rate, dividend_yield, sign, american):
    # With zero volatility, maximise discounted intrinsic value along the
    # deterministic risk-neutral path. Endpoints and the one possible stationary
    # point suffice, including negative interest rates and dividend yields.
    candidates = [years]
    if american:
        candidates.append(0.0)
        if rate != dividend_yield and rate != 0 and dividend_yield != 0:
            if (rate > 0) == (dividend_yield > 0):
                stationary = (
                    math.log(abs(rate)) + math.log(strike)
                    - math.log(abs(dividend_yield)) - math.log(spot)
                ) / (rate - dividend_yield)
                if 0 < stationary < years:
                    candidates.append(stationary)
    return max(max(sign * (spot * math.exp(-dividend_yield * t)
                           - strike * math.exp(-rate * t)), 0.0)
               for t in candidates)


def _crr(spot, strike, years, rate, volatility, dividend_yield, sign, steps):
    """Price plus delta/gamma from the first two exercise-aware tree layers.

    Taking tiny external spot bumps differentiates the piecewise-linear tree
    interpolation and produces a spurious gamma spike at aligned strikes.
    Layer differences instead use the natural lattice spacing and converge to
    continuous-model Greeks as the time/space mesh is refined.
    """
    dt = years / steps
    dx = volatility * math.sqrt(dt)
    denominator = math.expm1(2.0 * dx)
    if denominator == 0:
        raise ValueError("CRR increment is below numeric resolution")
    probability = math.expm1((rate - dividend_yield) * dt + dx) / denominator
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("CRR probability outside [0, 1]; change inputs or increase steps")
    discount = math.exp(-rate * dt)
    values = [max(sign * (spot * math.exp((2 * j - steps) * dx) - strike), 0.0)
              for j in range(steps + 1)]
    layers = {}
    for level in range(steps - 1, -1, -1):
        for j in range(level + 1):
            continuation = discount * ((1 - probability) * values[j]
                                       + probability * values[j + 1])
            exercise = max(sign * (spot * math.exp((2 * j - level) * dx) - strike), 0.0)
            values[j] = max(continuation, exercise)
        if level in (1, 2):
            layers[level] = values[:level + 1]
    if exercise > continuation:
        # Inside the immediate-exercise region, local value is intrinsic.
        return values[0], sign, 0.0
    one, two = layers[1], layers[2]
    first_width = spot * (math.expm1(dx) - math.expm1(-dx))
    upper_width = spot * math.expm1(2 * dx)
    lower_width = -spot * math.expm1(-2 * dx)
    if min(first_width, upper_width, lower_width) <= 0:
        raise ValueError("CRR mesh is below numeric resolution for Greeks")
    delta = (one[1] - one[0]) / first_width
    delta_up = (two[2] - two[1]) / upper_width
    delta_down = (two[1] - two[0]) / lower_width
    gamma = (delta_up - delta_down) / (0.5 * (upper_width + lower_width))
    return values[0], delta, gamma


def price(*, spot, strike, years, rate, volatility, dividend_yield=0.0,
          kind="call", style="european", steps=300):
    """Return a per-unit model price, rejecting unsupported/unstable inputs.

    At expiry this is intrinsic value. Zero volatility uses an exact
    deterministic path with continuous early exercise for American options.
    Otherwise American exercise is discretised to ``steps`` tree dates.
    A CRR probability outside [0, 1] raises ValueError: no clipping, model
    substitution, or silent step-count change is performed.
    """
    spot, strike, years, rate, volatility, dividend_yield = _validate(
        spot, strike, years, rate, volatility, dividend_yield, kind, style, steps)
    sign = 1.0 if kind == "call" else -1.0
    if years == 0:
        return max(sign * (spot - strike), 0.0)
    try:
        if volatility == 0:
            result = _deterministic(spot, strike, years, rate, dividend_yield,
                                    sign, style == "american")
        elif style == "european":
            sigma_t = volatility * math.sqrt(years)
            if sigma_t == 0:
                raise ValueError("volatility/time combination is below numeric resolution")
            d1 = (math.log(spot) - math.log(strike)
                  + (rate - dividend_yield + 0.5 * volatility ** 2) * years) / sigma_t
            d2 = d1 - sigma_t
            result = sign * (spot * math.exp(-dividend_yield * years) * _cdf(sign * d1)
                             - strike * math.exp(-rate * years) * _cdf(sign * d2))
        else:
            result = _crr(spot, strike, years, rate, volatility, dividend_yield, sign, steps)[0]
        if not math.isfinite(result):
            raise ValueError("model result is not finite; inputs exceed numeric range")
        return max(result, 0.0)
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("inputs exceed model numeric range") from exc


def greeks(*, spot, strike, years, rate, volatility, dividend_yield=0.0,
           kind="call", style="european", steps=300):
    """Finite-difference sensitivities using the same model and fixed contract.

    European delta/gamma: central differences, spot bump 0.1%.
    American delta/gamma: finite differences on the first two CRR layers;
    inside the immediate-exercise region these are intrinsic delta and zero
    gamma. At zero volatility or expiry use spot differences as above. Tree
    layer estimates retain time/space discretisation error, but avoid the
    strike-alignment spike from tiny external spot bumps.
    Vega: central differences with a 0.001 absolute-volatility bump (or 0.1%
    of volatility, whichever is larger); second-order forward differences near
    zero volatility. Output is per +0.01 absolute volatility, i.e. one point.
    Rho: central differences, 0.0001 rate bump, output per +0.01 rate.
    Theta: backward maturity difference over at most one day, scaled per day;
    at expiry theta is conventionally zero. Expiry delta/gamma are numerical
    payoff differences, not smooth derivatives at the strike.
    Invalid bumped CRR inputs raise ValueError just like ``price``; such Greeks
    are unavailable at that step count rather than silently approximated by BSM.
    """
    spot, strike, years, rate, volatility, dividend_yield = _validate(
        spot, strike, years, rate, volatility, dividend_yield, kind, style, steps)
    inputs = dict(spot=spot, strike=strike, years=years, rate=rate,
                  volatility=volatility, dividend_yield=dividend_yield,
                  kind=kind, style=style, steps=steps)

    def value(**changes):
        return price(**(inputs | changes))

    if style == "american" and years > 0 and volatility > 0:
        try:
            base, delta, gamma = _crr(spot, strike, years, rate, volatility,
                                      dividend_yield, 1.0 if kind == "call" else -1.0, steps)
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("inputs exceed model numeric range") from exc
    else:
        base = value()
        ds = spot * 0.001
        if ds == 0 or ds * ds == 0:
            raise ValueError("spot is too small for finite-difference Greeks")
        up, down = value(spot=spot + ds), value(spot=spot - ds)
        delta = (up - down) / (2 * ds)
        gamma = (up - 2 * base + down) / (ds * ds)
    dv = max(0.001, volatility * 0.001)
    if volatility >= dv:
        vega = (value(volatility=volatility + dv) - value(volatility=volatility - dv)) / (2 * dv)
    else:
        vega = (-3 * base + 4 * value(volatility=volatility + dv)
                - value(volatility=volatility + 2 * dv)) / (2 * dv)
    dr = 0.0001
    rho = (value(rate=rate + dr) - value(rate=rate - dr)) / (2 * dr)
    elapsed = min(1 / 365, years)
    theta = (value(years=years - elapsed) - base) / elapsed / 365 if elapsed else 0.0
    result = dict(delta=delta, gamma=gamma, vega_per_vol_point=vega * 0.01,
                  rho_per_rate_point=rho * 0.01, theta_per_day=theta)
    if not all(math.isfinite(v) for v in result.values()):
        raise ValueError("finite-difference Greeks exceed numeric range")
    return result
