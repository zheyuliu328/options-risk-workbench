# Single-contract numerical sensitivity

This optional native task uses the existing pricing engine to show how step counts and perturbation sizes affect one selected contract. It has no extra dependency and does not change production pricing, select a best answer or validate the rest of the portfolio. The development browser now contains this optional task; public publication is still pending.

## Run an original case

```sh
python -m options_risk.diagnostics examples/greek-boundary.json --output /tmp/new-numerical-diagnostics
python -m options_risk.diagnostics examples/portfolio.json --position long-call --output /tmp/new-selected-contract
```

For a multiple-position file, pass the exact ID from that file; never guess a contract. The second command requires an ID present in your request. Existing output directories are refused. Open report.html and keep diagnostics.json with the original input file.

The original boundary put uses spot 95, strike 100, thirty calendar days, rate 8%, zero continuous yield and volatility 20%. Its short quantity -2 and multiplier 100 produce exposure -200. All values are invented.

## What is compared

- Step counts are fixed at 150/151/300/301/600/601. Unit price and the production Greek bundle have independent availability status. A valid price remains available if a bumped Greek fails.
- Vega perturbations at 300 steps are 0.0005/0.001/0.002 absolute volatility; Rho perturbations are 0.00005/0.0001/0.0002 absolute rate. Results are rescaled to one absolute percentage point (+0.01), regardless of perturbation size.
- Near zero volatility the Vega estimate explicitly uses second-order forward differences. All attempted endpoint inputs, prices and failures are retained. This is a declared formula choice, not a silent substitution.
- European production Vega is analytic, whereas the bump table deliberately reports finite-difference estimates. The two are not interchangeable definitions at finite bump size.
- Signed results multiply unit values by quantity × multiplier. Overflow of a scaled result does not erase an otherwise finite unit result. The unavailable count counts the named unit/scaled checks, not distinct contracts.

At the boundary example, 300-step Vega is approximately 0.0672473357 and 301-step Vega 0.0649763490. Neither is automatically declared correct. The separate [independent validator](INDEPENDENT_VALIDATION.md) provides a different-engine comparison. Agreement across this diagnostic's rows alone does not prove convergence or establish a numerical error bound.

## Review the failures and scope

A call with S=K=100, T=1, r=10%, q=0 and volatility `0.1/sqrt(300)+0.0001` has a valid 300-step price near 9.5162581964 but an invalid default volatility bump. The report retains both facts. It does not switch to a European model, clip the tree probability, increase steps silently or fill failed Greeks with zero.

Only the selected contract and shared market inputs are examined. Input position count and selected ID are recorded; other contracts and all scenarios are not validated. Duplicate/missing IDs and unsupported selected fields are rejected. Expiry must be after the valuation date: the task does not treat nonsmooth expiry Greeks as differentiable values or model post-expiry settlement cash flows.

Continuous dividend yield is not a discrete cash-dividend schedule. Flat volatility, ACT/365 and the selected exercise style remain conditional assumptions. There is no market data retrieval, model approval, significance claim, trade recommendation or profit result. These are agent-operated software diagnostics, not external human acceptance.

## Development browser task (not yet published)

Choose the invented **Tree sensitivity: boundary put** example, or enter positions and expand **Inspect numerical sensitivity for one position**. Select the exact ID and inspect. The controls validate only shared market inputs and the selected row; invalid scenarios do not prevent this scoped task. Duplicate IDs are still rejected. Empty numeric fields are never converted into assumed zero inputs.

The result contains unit and signed position tables, fixed-bump checks and separate HTML/JSON downloads. Changing the selection clears the diagnostic report. Editing inputs clears both portfolio and diagnostic results. Cancelling diagnostics retains a previously completed portfolio report when its inputs have not changed. A valid price and unavailable Greek bundle may appear together. Download both reports if you need portfolio scenarios and numerical diagnostics.
