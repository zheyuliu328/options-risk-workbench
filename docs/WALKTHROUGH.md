# Understand and demonstrate Options Risk Workbench

## 中文：从一个问题开始

这个工具回答：固定持仓不变，如果价格、波动率或时间改变，组合的模型价值怎样变化？它不预测市场方向。网页提供普通跨式与低波动率大冲击反例；例子均虚构。

1. 选择“普通跨式组合”，点“直接体验示例”。买入相同执行价和到期日的看涨与看跌，观察组合敏感度：Delta看一阶方向，Gamma看Delta如何变化，Vega看波动率，Theta看时间。数量和乘数已计入。
2. 看情景表。模型先按新市场条件重新给每笔合约定价，再减当前价值；这是完整重估。
3. 看近似差值。Delta/Gamma/Vega/Theta仅在当前点描述局部变化，不能替代大冲击后的完整重估。场景里最大的损失不等于VaR，更不等于理论最大损失。
4. 选择“大幅冲击：近似失效”。初始价格99、执行价100、波动率1%，上涨5%跨过执行价。比较0.1%和5%的冲击；局部近似甚至可能和完整重估符号不同。
5. 下载HTML报告及JSON。HTML可独立阅读，JSON包含完整输入和结果，可重新导入。输入自己的持仓时，从空白必填字段开始；数据不上传。

实现：欧式用含连续股息的BSM；美式用300步CRR树。欧式正时间、正波动率的Delta/Gamma/Vega解析计算；其余敏感度保留树或差分方法。计算在浏览器Worker运行Python。

验证故事：独立挑战发现近到期低波动率Gamma的固定差分误差，也发现低波动率Vega偏差。修复后用解析恒等式、高精度参考、有限参数网格和网页导出复算检查。测试通过不是所有极端参数都可靠，更不是生产采纳证明。

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

Without reading this document, explain the two examples in Chinese, give the English introduction, and answer the five follow-ups with units. The user's ability to do this has not been assessed. Do not mark this gate passed merely because the material exists.
