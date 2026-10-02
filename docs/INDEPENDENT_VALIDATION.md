# Independent fixed-contract revaluation investigation

This optional offline task compares the workbench against QuantLib 1.43. It adds no pricing model or market-data downloader to the public browser. The production pricing kernel, request schema and browser behavior are unchanged.

## Run an invented case

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[validation]'
.venv/bin/python -m options_risk.validation examples/portfolio.json --output /tmp/new-standard-investigation
.venv/bin/python -m options_risk.validation examples/counterexample.json --output /tmp/new-counterexample-investigation
```

Choose a new directory. Existing output is refused. Each task saves a self-contained HTML report, exact request/result, input SHA-256, reference engine version, investigation thresholds, unit-level comparisons and scenario results.

[Standard synthetic investigation](independent-reference/standard/report.html) · [Synthetic approximation-failure investigation](independent-reference/counterexample/report.html)

## Matched conventions and independent references

European options use QuantLib AnalyticEuropeanEngine; American options use FdBlackScholesVanillaEngine at 800 and 1600 time/space steps with two damping steps. Dates are fixed, ACT/365 and continuous flat interest/dividend yields match the workbench. The global QuantLib evaluation date is restored. At scenario expiry the reference uses payoff; beyond expiry the production request validation rejects the task.

Price, Delta and Gamma are compared per unit, before signed quantity and multiplier scaling. American CRR diagnostics retain 150/151/300/301/600/601 steps to expose odd/even oscillations. Thresholds are investigation rules, not universally validated error bounds. Reference mesh disagreement beyond 25% of the comparison threshold is flagged as reference_mesh_unstable, retaining the numbers rather than reporting unqualified agreement. The revision-2 policy added mesh classification after independent review; all diagnostics are retrospective and are not blind tests.

Each scenario is rebuilt from the original request for independent full revaluation. The local approximation and its residual remain explicitly labeled as workbench calculations. This version does not independently compare Vega, Rho or Theta. Workbench Theta is a one-calendar-day maturity difference; it must not be equated to an instantaneous QuantLib Theta. No interest-rate shock is added.

## Source-backed local tasks

Pass --context LOCAL_CONTEXT.json to retain provenance, assumptions and supplied quotes. A quotes list may contain id, date, bid and ask. IDs must be unique portfolio IDs, dates match the declared valuation day and bid/ask must be finite and nonnegative with bid <= ask. These checks do not establish intraday synchrony, quote authenticity, data-vintage independence or redistribution rights.

A model value outside a supplied bid/ask spread is retained as a conditional discrepancy. It is not automatically a pricing defect or an executable opportunity. Record rates, dividends, exercise conventions, vendor IV, underlying adjustment, quote timing and source rights before attributing the difference. Original academic/client files and their quote-derived case outputs remain local; only original methods and invented fixtures belong in this repository.

## Interpretation

Distinguish source/definition uncertainty, numerical engine differences and local-approximation failure. Engine agreement under common assumptions does not validate the assumptions. Hypothetical position quantities do not establish actual holdings, trading performance, portfolio VaR or model approval. This task is a conditional revaluation investigation, not a production risk platform.

Reference methodology: [QuantLib European tests](https://github.com/lballabio/QuantLib/blob/master/test-suite/europeanoption.cpp) and [American tests](https://github.com/lballabio/QuantLib/blob/master/test-suite/americanoption.cpp).
