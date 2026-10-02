# Quote-to-volatility review

This optional native workflow starts from per-unit bid/ask option premiums, rather than requiring an externally supplied volatility. It uses the existing BSM European or fixed-step CRR American model, checks each endpoint independently, and exports complete inputs and readable diagnostics. It has no market-data downloader. This feature is not yet in the public browser application.

## Complete a task

```sh
python -m options_risk.quotes examples/quotes.json --output /tmp/my-new-quote-review
```

Choose a new directory. Open `report.html` offline and retain `result.json` for reproduction. No optional library is required for the calculation. The example is invented, including the crossed spread, exercise-boundary and expiry-price counterexamples. Incorrect rows remain visible rather than disappearing from the report. A nonstandard JSON file containing NaN or Infinity is rejected as a whole before creating output.

Required top-level fields: `as_of` (ISO date), `underlying`, `currency`, `spot`, and `quotes` (1–20 rows). Optional `rate` and `dividend_yield` are annual continuous ratios, defaulting to zero. Each quote requires a unique `id`, `kind` (`call`/`put`), `style` (`european`/`american`), positive `strike`, ISO `expiry`, `bid` and `ask`. Premiums are per underlying unit, without a quantity or multiplier. All occurrences of duplicate IDs are rejected. Unknown fields are rejected to prevent silent interpretation loss.

## Interpret the result

- Bid, midpoint and ask are inverted separately. A failed bid does not remove a usable midpoint; do not turn failed endpoints into a numeric volatility range.
- Positive IV estimates are annual ratios in JSON and percentages in the report. Bid/ask-derived IV is a quote-implied range, not a confidence interval.
- `solved` means a model price residual no larger than 1e-8 per unit and a numerical volatility bracket no wider than 1e-9. It does not mean the market or the model is correct.
- `boundary_at_price_tolerance` avoids inventing a positive IV near the deterministic lower price. For American immediate exercise, this can be a broad plateau. A European boundary may identify zero volatility mathematically; the status concerns resolution at the chosen tolerance.
- `low_price_sensitivity` means a local 0.0001-volatility bump changes price by no more than the tolerance scale. The displayed estimate is poorly conditioned. The numerical root bracket is not price-rounding uncertainty.
- Expired premiums, model-bound violations, inadmissible tree domain, search-cap limits and convergence failures have distinct statuses. The default volatility cap is 5.0 (500%), a numerical search limit, not an economic bound. The Python solver accepts an explicit cap up to 10.0.
- American midpoint estimates at 300, 301, 600 and 601 steps show discretisation sensitivity. Odd/even steps can oscillate. No automatic convergence or model-approval threshold is imposed.

The American minimum positive volatility is just above `abs(rate-dividend_yield)*sqrt(years/steps)` to keep CRR probabilities admissible. Deterministic zero-volatility pricing is checked separately. The solver never bridges the inadmissible interval or substitutes a European model. A negative local price slope is reported as a diagnostic failure.

## Independent verification and provenance

Tests use separate QuantLib analytic prices over call/put, negative/positive rates, dividends and a volatility grid. American tests use refined finite-difference reference prices and inspect the resulting tree-IV discrepancy and parity of step counts. Same-engine round trips alone would not independently validate prices.

Capability references, inspected 2026-10-03:

- [QuantLib option inversion](https://github.com/lballabio/QuantLib/blob/master/ql/instruments/vanillaoption.cpp) selects engines appropriate to exercise style.
- [QuantLib inverse-method warnings](https://github.com/lballabio/QuantLib/blob/master/ql/instruments/vanillaoption.hpp) discuss unattainable prices and inverse-problem limitations.
- [vollib BSM inversion](https://github.com/vollib/py_vollib/blob/master/vollib/black_scholes_merton/implied_volatility.py) is an established European-model capability reference.

The implementation here is independent and uses only the standard library. QuantLib is an optional test reference. Its CRR class uses a different probability convention from this engine; identical step counts do not imply exact equality. These libraries offer substantially broader numerical capabilities. Adding this task does not establish overall parity with them.

Remaining delivery: browser quote input/error recovery, explicit user-selected transfer to a portfolio, browser/offline export parity and deployed-version verification. Missing model capabilities include discrete cash dividends and surface calibration. Quotes do not establish source authenticity, point-in-time availability or executable liquidity.
