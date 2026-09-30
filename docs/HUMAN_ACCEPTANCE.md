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
