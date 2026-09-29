# Options Risk Workbench

Revalue a fixed option portfolio under spot, volatility and time shocks. Inspect signed exposures, full-revaluation P&L and the difference from a local Greek approximation.

**Current delivery: local Python tool, not yet a deployed website.** No external data, credentials or dependencies are required for the numerical calculation. The included ETF example is entirely invented.

## Run

From this checkout, using Python 3.10 or newer:

```sh
python3 -m options_risk examples/portfolio.json --output /tmp/options-risk-result.json
python3 -m unittest discover -s tests -v
```

Choose a new output path for each report; existing output files are protected. Optional installation: `python3 -m pip install .`, followed by `options-risk INPUT.json --output OUTPUT.json`.

The JSON input declares one underlying/currency, valuation date, spot, continuous rate/dividend yield, fixed contracts and shocks. Positive quantity is long, negative is short. Strike, expiry and multiplier remain unchanged under every scenario. `vol_change: 0.05` means five absolute volatility points; `spot_return: -0.05` means a 5% price fall. Time is calendar days on ACT/365.

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

Browser input/result/export workflow; academic evaluation version and leakage repair; documented permitted data adapters; discrete dividends and convergence diagnostics; independently checked portfolio VaR/ES if added. These are not completed capabilities. No investment recommendation, production-readiness, external adoption or regulatory-compliance claim is made.
