# Options Risk Workbench

Revalue a fixed option portfolio under spot, volatility and time shocks. Inspect signed exposures, full-revaluation P&L and the difference from a local Greek approximation.

**Current delivery: [public browser tool](https://options-risk-zheyuliu.mystic-pear-2111.chatgpt.site) and local Python tool.** No external data, credentials or dependencies are required for the numerical calculation. The included ETF example is entirely invented.

## Run

From this checkout, using Python 3.10 or newer:

```sh
python3 -m options_risk examples/portfolio.json --output /tmp/options-risk-result.json --html /tmp/options-risk-report.html
python3 -m unittest discover -s tests -v
```

Choose a new output path for each report; existing output files are protected. Optional installation: `python3 -m pip install .`, followed by `options-risk INPUT.json --output OUTPUT.json`.

The JSON input declares one underlying/currency, valuation date, spot, continuous rate/dividend yield, fixed contracts and shocks. Positive quantity is long, negative is short. Strike, expiry and multiplier remain unchanged under every scenario. `vol_change: 0.05` means five absolute volatility points; `spot_return: -0.05` means a 5% price fall. Time is calendar days on ACT/365.

[Read the invented sample report](docs/sample-report.html) · [Machine-readable result](docs/sample-result.json)

## What the result means

- European options use Black–Scholes–Merton with continuous dividends. American options use a 300-step Cox–Ross–Rubinstein tree and early exercise.
- Position market values and Greeks are signed and multiplied by contract size. Delta is currency value per underlying-price unit; gamma per squared price unit. Vega/rho use one percentage-point changes. Theta uses one calendar day.
- Scenario P&L is the change in model value. The Greek approximation includes delta, gamma, vega and theta; its residual includes nonlinearity, omitted cross terms and numerical error.
- At expiry the value is intrinsic. Scenarios after expiry are rejected because exercise/settlement and cash accounting are not implemented.
- Volatility remains flat per contract; this is not a calibrated smile, discrete-dividend model, realised trade ledger or historical strategy backtest. Fees and financing are excluded. American tree Greeks may be unstable; full revaluation is the primary scenario result.

Stock/ETF contracts can permit early exercise; a European-only approximation must not silently be presented as an American-contract valuation. See the [OCC/OIC exercise explanation](https://www.optionseducation.org/optionsoverview/exercising-options). Continuous dividend yield here is an approximation, not a corporate-action schedule.

## Relationship to the MSc project and other tools

The product direction comes from QQQ implied-volatility coursework and the need to explain option risk. This repository is newly implemented using public methods; it contains no copied team pipeline, market dataset, client files or proprietary source. The original daily/contract-level academic pipelines retain their own attribution. Historical academic AUC/Sharpe/returns are not endorsed or reproduced here.

Forecast Review remains a separate model-review application. Its common-sample and temporal-validation ideas inform future research integration; no automatic pipeline connection is currently implemented. Existing VaR code remains a separate single-return-series backtest, not this portfolio's VaR engine.

## Remaining work

Documented permitted data adapters; discrete dividends and richer convergence diagnostics; independently checked portfolio VaR/ES if added. A separate local corrected retrospective academic evaluation is complete; it is not an unseen blind test, exact old-result reproduction or part of this public runtime. These are not completed capabilities. No investment recommendation, production-readiness, external adoption or regulatory-compliance claim is made.

## Development and validation

Independent implementation with AI-assisted development and human-reviewable tests. Current checks: 32 tests (including overnight numerical-boundary regressions); GitHub CI checks Python 3.10/3.12, covering closed-form reference values, parity, American exercise/convergence, fixed-contract scenarios, portfolio offsets, invalid inputs, output protection and report escaping. A readable synthetic report was visually checked at desktop size and for mobile page overflow. These checks do not reproduce the historical academic research.

Browser delivery (2026-09-29): editable positions/scenarios, JSON import, JSON/HTML export, stale-result invalidation and cancellation. The same Python source runs locally and in the self-hosted Pyodide worker; all output fields matched native Python within 1e-8 relative numeric tolerance. See [browser verification](docs/browser-validation.json). No input upload endpoint.

### Overnight numerical corrections (2026-09-29)

European delta/gamma/vega now use analytic BSM derivatives at positive time and volatility. A one-day, 1% volatility ATM example previously understated gamma by 22.1% because the fixed spot bump exceeded the local price curvature scale. Other sensitivities retain the documented differences. Extreme positions producing non-finite portfolio values are rejected, as are invalid dates or calendar overflow. These corrections do not add historical profit or external-user evidence. Source changes reach the public browser only after a separate deployment.

The low-volatility European vega correction was checked against independent 70-digit Decimal references at spot 99/101, strike 100, 30 days and 1% volatility. Finite vol-point shocks still differ from a local derivative; full revaluation remains the scenario result.

## Guided use

The browser offers a one-click straddle example, a large-shock counterexample, and a blank custom-position entry. Results explain portfolio sensitivities before full revaluation and approximation differences. Offline reports include contract type, exercise style and volatility when generated by the CLI or browser. [Chinese walkthrough and English interview explanation](docs/WALKTHROUGH.md).
