# Portfolio price-range review

Status: native Python and public browser workflow, deployed in Sites version10. See [publication receipt](publication.json).

## Browser task

Open **Explore a price range** from the portfolio page, then choose **Try straddle range** or **Try expiry counterexample**. To analyse your own portfolio, edit the market and positions above and calculate the range. Custom scenario rows are outside this task. Download replay inputs, full results or the standalone HTML report.

**Import range request** accepts the grid `request.json` format and replaces market/positions, resetting custom scenarios to Unchanged. Browser input supports up to10 positions and30 generated nodes; the native engine supports up to30 positions. Results files are not request files. Unedited numeric inputs retain their original precision through percentage display conversion. Editing any relevant field invalidates old curve downloads. Calculations and selected files stay in the browser.

## Complete a native task

```sh
python -m options_risk.grid examples/price-grid.json --output /tmp/price-range-review
python -m options_risk.grid /tmp/price-range-review/request.json --output /tmp/price-range-replayed
```

Use a new output directory for every run. Open `report.html` offline. Compare the full-revaluation curve with the local approximation, then inspect the exact node table. `results.json` preserves unrounded numeric outputs. `request.json` retains all inputs; `manifest.json` records input, artifact and calculation-source hashes. These hashes support integrity checks, not authenticity certification.

The invented long-straddle fixture contains one European call and put with spot and strike 100, quantity 1 each, multiplier 100, 30 calendar days to expiry and volatility 25%. The default range is -20% to +20%, with 21 equally spaced return nodes and an exact zero-return anchor. An asymmetric range may require one extra node.

For an independently checkable counterexample, change `grid.days` to 30. At expiry, portfolio value must be `100 * abs(spot - 100)`. Value change subtracts the initial model value. The kink cannot be reproduced by the initial local quadratic approximation over the whole range; even zero spot change loses the initial time value. This is not paid-premium trade profit.

## Input contract

The wrapper has `schema_version: 1`, `portfolio`, `grid` and optional `source_note`. The portfolio uses the existing market and position fields, with no `scenarios` field. All positions share one underlying and currency. Every node uses the same fixed contracts, volatility change and elapsed calendar days.

Grid fields are all required:

| Field | Meaning |
|---|---|
| `lower_return`, `upper_return` | Fractions, e.g. -0.2 and 0.2. Must span zero, differ, and have lower return greater than -1. |
| `points` | Integer from 3 to 29, plus an exact zero anchor if necessary; at most 30 total nodes. |
| `days` | Nonnegative whole calendar days, no later than the earliest position expiry. |
| `vol_change` | Absolute volatility fraction: 0.05 means five percentage points. |

Nonfinite, unsupported, collapsed floating-point nodes and invalid contracts are rejected. The existing European BSM and American 300-step CRR engines remain unchanged. Rates and continuous dividend yields remain fixed; volatility is flat per position.

## Read results accurately

Full change is scenario model value minus current model value. Residual is full change minus local approximation, with signed quantity and contract multiplier included. Zero spot return only implies zero change when time and volatility also stay unchanged. Connecting lines are visual guides between evaluated nodes, not extra valuations. Report tables use the shortest round-trip numeric representation; JSON retains the calculation values.

Sampled minima and maxima are not guaranteed continuous-range extrema, VaR, expected shortfall, or worst-case losses. No paid-premium ledger, financing, commissions, discrete dividends, settlement after expiry, calibrated surface or probability model is supplied. American full revaluation retains discretisation error; it is not exact ground truth.

`scenario-request.json` can be passed to the existing native portfolio CLI. More than ten nodes exceed the existing browser scenario editor's import limit. Replay the grid's `request.json` with the grid CLI instead; do not silently truncate nodes.

## Acceptance evidence

Automated identities cover put-call parity with negative rates and dividends, expiry straddle payoff, signed exposures, exact zero anchoring, invalid input rejection, replay and output protection. The independent validation job also exercises the existing pricing engine. This native evidence does not establish browser availability, external user adoption or production model approval.
