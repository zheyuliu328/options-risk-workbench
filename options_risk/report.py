"""Offline readable report; escape all user-provided identifiers."""
from html import escape


def render(result, request=None, source_note=None):
    def text(value):
        return escape(str(value), quote=True)

    def money(value):
        return f'{value:,.2f}'

    source_section = f'<p>{text(source_note)}</p>' if source_note else ''
    contracts = {p['id']: p for p in request['positions']} if request else {}
    input_columns = '<th>Kind</th><th>Style</th><th>Annual vol</th>' if request else ''
    def contract_cells(p):
        q = contracts.get(p['id'])
        return (f'<td>{text(q["kind"])}</td><td>{text(q["style"])}</td><td>{q["volatility"]:.4%}</td>' if q else '')
    greek_labels = {'delta': 'Delta: currency per spot unit', 'gamma': 'Gamma: currency per spot unit squared', 'vega_per_vol_point': 'Vega: currency per 1 vol percentage point', 'theta_per_day': 'Theta: currency per calendar day', 'rho_per_rate_point': 'Rho: currency per 1 rate percentage point'}
    greek_rows = ''.join(f'<tr><td>{text(greek_labels[k])}</td><td>{v:.8g}</td></tr>' for k,v in result['greeks'].items())
    rows = ''.join(f'<tr><td>{text(p["id"])}</td><td>{money(p["strike"])}</td>'
                   f'<td>{text(p["expiry"])}</td><td>{p["quantity"]:g}</td><td>{p["multiplier"]:g}</td>'
                   f'{contract_cells(p)}<td>{money(p["market_value"])}</td></tr>' for p in result['positions'])
    scenario_rows = ''.join(f'<tr><td>{text(s["name"])}</td><td>{text(s["date"])}</td>'
                            f'<td>{s["spot_return"]:+.1%}</td><td>{s["vol_change"]*100:+.1f}</td>'
                            f'<td>{money(s["pnl"])}</td></tr>' for s in result['scenarios'])
    details = ''
    for s in result['scenarios']:
        legs = ''.join(f'<tr><td>{text(p["id"])}</td><td>{money(p["pnl"])}</td>'
                       f'<td>{money(p["greek_approximation"])}</td><td>{money(p["approximation_residual"])}</td></tr>'
                       for p in s['positions'])
        details += f'<details><summary>{text(s["name"])}</summary><div class="scroll"><table><thead><tr><th>Position</th><th>Full P&amp;L</th><th>Local approximation</th><th>Residual</th></tr></thead><tbody>{legs}</tbody></table></div></details>'
    assumptions = ''.join(f'<li>{text(s)}</li>' for s in result['assumptions'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Option risk review</title>
<style>body{{margin:0;background:#f5f7fa;color:#192536;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1050px;margin:32px auto;padding:28px;background:white}}h1{{font-size:28px;margin:0}}h2{{font-size:20px;margin-top:32px}}.meta{{color:#4c596b}}.value{{font-size:30px;font-variant-numeric:tabular-nums}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border-bottom:1px solid #dbe0e8;padding:12px;text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef2f7}}.scroll{{overflow:auto}}details{{margin:12px 0;border:1px solid #dbe0e8;padding:12px}}summary{{cursor:pointer}}li{{margin:8px 0}}@media(max-width:600px){{main{{margin:0;padding:18px}}}}@media print{{main{{margin:0}}details{{break-inside:avoid}}}}</style></head><body><main>
<h1>Option risk review</h1><p class="meta">{text(result['underlying'])} · {text(result['currency'])} · {text(result['as_of'])}</p>
{source_section}<p>Signed model value</p><div class="value">{money(result['market_value'])} {text(result['currency'])}</div>
<p>Spot {money(result['spot'])} · Rate {result['rate']:.2%} · Continuous dividend yield {result['dividend_yield']:.2%}</p>
<h2>Fixed contracts</h2><div class="scroll"><table><thead><tr><th>Position</th><th>Strike</th><th>Expiry</th><th>Quantity</th><th>Multiplier</th>{input_columns}<th>Model value</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Portfolio sensitivities</h2><p>Signed quantities and contract multipliers are included. These are local changes, not maximum losses.</p><div class="scroll"><table><tbody>{greek_rows}</tbody></table></div><h2>Scenario P&amp;L</h2><p>Change in model value, excluding fees and financing. Volatility changes are absolute percentage points.</p><div class="scroll"><table><thead><tr><th>Scenario</th><th>Date</th><th>Spot change</th><th>Vol points</th><th>P&amp;L</th></tr></thead><tbody>{scenario_rows}</tbody></table></div>
<h2>Position explanation</h2><p>Full revaluation is the primary result. The local approximation is not a substitute for scenario pricing. Local P&amp;L = Delta × spot change + 0.5 × Gamma × spot change² + Vega × vol-point change + Theta × elapsed calendar days. Higher-order and cross terms are omitted. Large shocks can change the sign as well as magnitude of the estimate. Scenario maximum loss is not VaR.</p>{details}
<h2>Assumptions and limits</h2><ul>{assumptions}</ul></main></body></html>'''
