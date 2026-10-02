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

The input may also be this tool's browser portfolio JSON download. Only its embedded `request` is recomputed; saved results and source notes are not authenticated or used as reference evidence. The original download is unchanged and its hash and input format are recorded. Supply independently declared provenance through `--context` when needed.

[Standard synthetic investigation](independent-reference/standard/report.html) · [Synthetic approximation-failure investigation](independent-reference/counterexample/report.html). These frozen earlier reports retain their original price/Delta/Gamma scope; the full-Greek boundary report below records the current validator.

## Matched conventions and independent references

European options use QuantLib AnalyticEuropeanEngine; American options use FdBlackScholesVanillaEngine at 800 and 1600 time/space steps with two damping steps. Dates are fixed, ACT/365 and continuous flat interest/dividend yields match the workbench. The global QuantLib evaluation date is restored. At scenario expiry the reference uses payoff; beyond expiry the production request validation rejects the task.

Price and all five reported Greeks are compared per unit, before signed quantity and multiplier scaling. American CRR diagnostics retain 150/151/300/301/600/601 steps to expose odd/even oscillations. Thresholds are investigation rules, not universally validated error bounds. Reference mesh disagreement beyond 25% of the comparison threshold is flagged as reference_mesh_unstable, retaining the numbers rather than reporting unqualified agreement. The revision-2 policy added mesh classification after independent review; all diagnostics are retrospective and are not blind tests.

Each scenario is rebuilt from the original request for independent full revaluation. The local approximation and its residual remain explicitly labeled as workbench calculations. Vega, Rho and Theta now have convention-matched independent comparisons described below. Workbench Theta is a one-calendar-day maturity difference; it must not be equated to an instantaneous QuantLib Theta. No interest-rate shock is added.

## Source-backed local tasks

Pass --context LOCAL_CONTEXT.json to retain provenance, assumptions and supplied quotes. A quotes list may contain id, date, bid and ask. IDs must be unique portfolio IDs, dates match the declared valuation day and bid/ask must be finite and nonnegative with bid <= ask. These checks do not establish intraday synchrony, quote authenticity, data-vintage independence or redistribution rights.

A model value outside a supplied bid/ask spread is retained as a conditional discrepancy. It is not automatically a pricing defect or an executable opportunity. Record rates, dividends, exercise conventions, vendor IV, underlying adjustment, quote timing and source rights before attributing the difference. Original academic/client files and their quote-derived case outputs remain local; only original methods and invented fixtures belong in this repository.

## Interpretation

Distinguish source/definition uncertainty, numerical engine differences and local-approximation failure. Engine agreement under common assumptions does not validate the assumptions. Hypothetical position quantities do not establish actual holdings, trading performance, portfolio VaR or model approval. This task is a conditional revaluation investigation, not a production risk platform.

Reference methodology: [QuantLib European tests](https://github.com/lballabio/QuantLib/blob/master/test-suite/europeanoption.cpp) and [American tests](https://github.com/lballabio/QuantLib/blob/master/test-suite/americanoption.cpp).

## Independent sensitivity comparisons

The offline validator now compares price and all five reported Greeks, with units and calculation conventions recorded per metric:

- European Vega uses the independent analytic engine and is expressed per +0.01 absolute volatility.
- American Vega uses independent FDM prices with the same central volatility bump as the workbench, or second-order forward differences near zero. The bump is max(0.001, 0.001 × volatility).
- Rho uses rates shifted by ±0.0001 with continuous dividend yield held fixed, reported per +0.01 rate. It is not silently substituted with an instantaneous analytic derivative.
- Theta advances the valuation date by one calendar day with expiry fixed, comparing the resulting value change. QuantLib instantaneous theta divided by 365 is a different definition.
- Both 800 and 1600 meshes independently rebuild each sensitivity. Reference price stability alone is insufficient to label a bumped Greek stable.

Revision 5 corrects zero-volatility European Delta/Gamma comparisons: both engines now use the declared central spot payoff differences with bump 0.1% of spot. At or across the deterministic payoff kink these are finite-step values, not smooth derivatives. Price and other sensitivity definitions are unchanged; expiry smooth-Greek comparisons remain unavailable. Tree diagnostics also retain price availability independently of the Greek bundle: a failed volatility bump must not erase a valid base price. These repairs preserve the observed failures and do not change the production pricing engine.

Run the original boundary example:

```sh
python -m options_risk.validation examples/greek-boundary.json --output /tmp/new-boundary-review
```

[Read the frozen original report](greek-boundary-example/report.html) and [complete diagnostics](greek-boundary-example/investigation.json). The hypothetical short American put has spot 95, strike 100, 30 calendar days, continuous rate 8%, no dividend yield and volatility 20%. It is not a market-data observation. The two signed contracts each have multiplier 100.

| Unit sensitivity | Workbench | Independent FDM 1600 | Outcome |
|---|---:|---:|---|
| Vega per volatility point | 0.0672473357 | 0.0659718490 | Investigate |
| One-calendar-day Theta | -0.0146827056 | -0.0141815817 | Investigate |
| Rho per rate point | -0.0293236675 | -0.0292899147 | Within screening threshold |

The two non-green outcomes remain visible. New sensitivity thresholds are retrospective screening choices: absolute 0.0001 or 1% of the reference magnitude for American options, whichever is larger. Mesh changes must be within one quarter of that threshold before own/reference agreement is classified. These numbers have not been calibrated to an economic use case and are not approval tolerances. Old pricing/Delta/Gamma criteria are retained.

Signed comparisons multiply by quantity × multiplier after unit checks. A short position reverses signs; the report does not infer a portfolio approval threshold from these scaled values. Per-Greek independent bump failures retain an unavailable status and explanation while other available metrics remain visible. If the base independent engine or production Greek calculation fails, the whole investigation fails explicitly and no complete report is claimed. Exact-zero-volatility American FDM can have a degenerate grid, including zero rate and yield; no positive volatility is substituted to conceal that limitation.

Tests include a one-day European option whose finite Theta is -0.4203523730, immediate exercise, low positive volatility forward Vega, negative-rate Rho, separately unstable reference Greeks, signed scaling and valid base prices with invalid CRR bumps. These are agent-operated numerical checks, not evidence of market suitability or external human adoption. The validator remains an optional offline tool; the browser pricing engine is unchanged by this extension.

## Scenario reference P&L refinement

The current offline validator independently reprices both the initial and shocked states at 800 and 1600 grids. Reports retain the resulting P&L difference for every position, plus the portfolio difference. An unstable position cannot be hidden by an equal and opposite position. `scenario_attention_count` is separate from the original unit-level `attention_count`; both must be read.

The refinement screen is one quarter of the sum of the base and shocked price screening scales, multiplied by absolute signed exposure. This is a retrospective numerical diagnostic, not a proven error bound, economic materiality threshold or risk limit. Passing the P&L-refinement screen does not establish stable endpoint prices or workbench/reference agreement. Policy revision 4 records this additional screen. Frozen earlier examples retain their generation-time scope; rerun the CLI into a new directory for current diagnostics.
