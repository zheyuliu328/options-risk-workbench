# Human acceptance — Options Risk Workbench

**Status: pending.** This is a runnable acceptance kit, not a completed trial. Use only invented files. The walkthrough provides the explanation and five technical follow-ups; read it after the unassisted task, not before, when assessing first-use discoverability.

## Unassisted first-use task

1. Open the public tool without installation and run the standard straddle. Record the model value and explain the Delta, Vega and Theta units.
2. Run the large-shock counterexample. Identify full-revaluation P&L, approximation and residual. Explain why the largest listed loss is not VaR.
3. Import `examples/portfolio.json`; change a quantity and recalculate. Confirm the old result is invalidated.
4. Try malformed JSON, recover by importing a valid file, and complete a calculation.
5. Download JSON and HTML. Open the HTML offline and identify strike, expiry, exercise style, quantity, multiplier and assumptions.
6. Repeat at a narrow phone-sized viewport. Record horizontal table scrolling or any blocking control.

## Blank trial record

- Participant (pseudonym):
- Date, browser, device and viewport:
- Tasks completed without prompting:
- Time to first useful result and to exported report:
- Assistance required and exact confusing wording:
- Failed input, visible message, recovery steps:
- Offline report understood without the website: yes / no / not assessed
- Repeat-use task completed: yes / no / not assessed
- Blocking issue and evidence:
- Overall status: pending / passed within recorded scope / needs repair

## Owner explanation — pending

Give the approximately three-minute English introduction in `WALKTHROUGH.md` without reading, then answer its five technical follow-ups. For each answer, record correct / incomplete / incorrect and the missing reasoning. Demonstrate one fresh invented input and explain the result and limits. Do not mark this gate passed from a generated script or automated browser test.

## Claim boundary

Verified implementation and reproducible test evidence can be described as project work. Human adoption, unaided understanding and production use require their own recorded evidence. No application is submitted by this checklist.

## Published extensions: participant task card

**Status: pending.** Give the participant only this task card, the public URL and the invented example files. Keep the observer rubric below hidden until the task is finished. Record each hint; an assisted completion is useful feedback but is not an unassisted pass. Do not ask participants to supply real positions or confidential quotes.

1. Start from the invented option quotes. Find one quote that can support a volatility estimate and one that cannot. Explain what the failure means without discarding the failed row.
2. Select the European call midpoint. Transfer a short position of two contracts with multiplier 100 into scenarios. Record the current position value, then the full-revaluation P&L from a 2% spot increase with volatility and time unchanged. Export both reports and identify the link between the selected quote and the position.
3. Return to the portfolio page and choose the boundary-put numerical example. Inspect that position's numerical sensitivity and find two step counts with different Vega estimates. Explain whether the screen establishes which estimate is correct. Download the diagnostic report and explain its scope after closing the website.
4. Change the selected position's volatility. Check whether the old diagnostic download remains available. Restore the original input and complete the task again.
5. Repeat the diagnostic task on a narrow screen. Record any inaccessible control or table column and any assistance needed.

## Observer rubric for the published extensions

| Task | Observable evidence | Interpretation needed |
|---|---|---|
| Quote review | Usable endpoint selected explicitly; crossed quote retained with an error | An inverse-model solution does not certify quote authenticity or executable liquidity. |
| Short-position transfer | Midpoint 10.8; IV about 25.09723356%; value about -2,160 USD; 2% spot-rise P&L about -236.29 USD | Signed quantity and multiplier matter; a spot rise hurts this short call under the declared assumptions. Allow displayed rounding. |
| Numerical sensitivity | Six step rows and six perturbation rows; 300-step Vega about 0.067247336 and 301-step about 0.064976349 per unit per volatility point | Availability is not convergence. This task covers one selected contract, not all portfolio scenarios or an independent model reference. |
| Changed input | Previous diagnostic result/export invalidated; recalculation produces a fresh result | A downloaded old report is a historical snapshot and cannot represent edited inputs. |
| Narrow screen | Task and downloads completed, or a precisely recorded blocker | Table scrolling is acceptable if the participant can reach and understand the values. |

Retain the exported files, date, viewport and participant's explanation with the blank trial record. These expected values come from the recorded invented software task; copying them is not evidence that a person completed or understood it. The optional native QuantLib investigation is a separate task and must not be described as a browser feature.

## Price-range task — human acceptance pending

Run the expiry counterexample in **Explore a price range**. Explain why a zero spot change still loses time value, why the full curve has a kink, and why sampled extrema are not VaR. Import an original invented range request, change a quantity, recover from a post-expiry input, and download replay inputs plus the report. Reopen the report offline and identify the fixed contracts, initial value and assumptions. Record assistance, time and failures using the blank record above; automated completion is not a human pass.
