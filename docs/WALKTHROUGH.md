# Understand and demonstrate Options Risk Workbench

## Guided demonstration

The tool asks how the model value of a fixed portfolio changes when spot, volatility or time changes. It does not predict market direction. Both examples are invented.

1. Choose **Standard long straddle**, then **Try an example**. The long call and put share strike and expiry. Delta measures first-order spot exposure; Gamma describes how Delta changes; Vega measures volatility exposure; Theta measures time decay. Quantities and multipliers are included.
2. Read the scenario table. Each unchanged contract is repriced under the new inputs and its initial value is subtracted: full revaluation.
3. Compare the local approximation. Initial Delta/Gamma/Vega/Theta describe nearby changes, not arbitrary large shocks. The largest listed scenario loss is neither VaR nor a theoretical maximum loss.
4. Choose **Large shock: approximation failure**. Spot starts at 99, strike at 100 and volatility at 1%. A 5% rise crosses the strike. Compare the 0.1% and 5% shocks: the approximation can even have the wrong sign.
5. Download the HTML report and JSON. The report is readable offline; JSON contains inputs and results and can be reimported. **Enter your positions** starts with empty required fields. Inputs stay local.

Implementation uses BSM with continuous dividends for European options and a 300-step CRR tree for American options. Positive-time, positive-volatility European Delta/Gamma/Vega are analytic; other sensitivities use tree or finite differences. Python runs in a browser worker.

Independent numerical challenges found fixed-bump errors in near-expiry, low-volatility Gamma and in Vega. Repairs were checked using analytic identities, high-precision references, a bounded parameter grid and browser-export recomputation. Passing tests does not establish universal accuracy or production adoption.

## English introduction — about three minutes at a measured pace

I built Options Risk Workbench to make a specific risk-analysis task reproducible: take a fixed option portfolio, change market assumptions, and explain the resulting change in model value. It is a browser-based tool that runs calculations locally, so the user can try invented examples or enter their own positions without uploading data.

The portfolio keeps strike, expiry, exercise style, signed quantity and contract multiplier explicit. European options use Black–Scholes–Merton with a continuous dividend yield. American options use a 300-step Cox–Ross–Rubinstein tree. The output starts with current model value and portfolio sensitivities, then shows full revaluation under spot, volatility and calendar-time shocks.

An important distinction is between full revaluation and a local Greek approximation. The approximation uses delta, gamma, vega and theta at the starting point. It omits higher-order and cross terms. I added a deliberately simple counterexample: a low-volatility call-and-put portfolio whose underlying moves from below to above the strike. A large move can make the approximation materially inaccurate, even with a different sign from full revaluation. The tool shows that difference rather than hiding it.

The validation work was useful because it found actual defects. Fixed bumps distorted European gamma close to expiry at low volatility, and also introduced vega error. I replaced positive-time, positive-volatility European delta, gamma and vega with analytic expressions, and checked them against independent references. I also tested numerical overflow, invalid dates, cancellation, input recovery and exported browser results against native Python calculations.

The limits are part of the project. The American tree is sensitive to resolution and some very-low-volatility inputs are rejected. The tool does not provide a volatility surface, discrete dividends, transaction costs, financing or an exercise cash-flow ledger. The worst loss among entered scenarios is not VaR. My contribution is a usable and inspectable scenario-analysis workflow, not a profitable trading strategy or a production risk system. The separate QQQ academic research is not the source of the demo's financial performance.

## Five technical follow-ups

1. **Why full revaluation?** It re-prices the unchanged contracts at the shocked inputs. Local Greeks approximate a neighbourhood; neither approach proves the model itself matches market prices.
2. **Why multiply Vega shocks by 100?** The request stores volatility as a decimal; Vega is reported per percentage point. A .05 change is five vol points, not 0.05 points.
3. **Why can American Greeks fail at low volatility?** At fixed tree resolution the CRR probability may fall outside [0,1]. The tool reports the unsupported range instead of silently substituting European pricing.
4. **What does validation establish?** Correctness within specific financial identities, inputs and tolerances, plus working UI/export paths. It does not establish universal accuracy or trading profitability.
5. **What is excluded from scenario P&L?** Fees, funding and actual exercise/settlement cash flows. Contracts beyond expiry require a ledger and are rejected.

## Personal understanding gate — pending

Without reading this document, explain the two examples in English, give the English introduction, and answer the five follow-ups with units. The user's ability to do this has not been assessed. Do not mark this gate passed merely because the material exists.
