# Independent public-data quant lab

This small CPU prototype is separate from FIN's agent runtime and deployed backend.
It tests a research hypothesis, not report correctness or autonomous agent capability.
There are no provider-model calls, broker connections, or service changes.

Read `experiment.json` before running. Its fixed design must be archived before data
evaluation. The prototype downloads the Kenneth French monthly three-factor file,
uses only market excess return and RF, fits one standardized ridge regression on
1960–1999, reports 2000–2009 validation and 2010–2025 test without tuning/refitting.
Four return/volatility features end **two calendar indices before** the target month:
January observations may inform March, not January or February returns. This
intentional delay reduces same-close assumptions but cannot establish historical
publication availability or repair revised historical data.

Dependencies: Python 3.11+, NumPy, matplotlib (the project environment already
contains these in the development setup; no scikit-learn/pandas dependency).

```powershell
python scripts/research_lab/market_timing.py --output-root <directory-outside-repository>
python -m pytest -q tests/test_public_market_timing.py
```

The runner freezes the specification and source hash **before downloading**,
caches the raw ZIP, records HTTP provenance and SHA-256, and writes an immutable
run directory containing metrics, predictions/positions/returns, fitted parameters,
charts, an HTML dashboard, and execution/failure records. Reuse cached data with
`--data-zip <previous-raw.zip>`; record every rerun rather than deleting a failure.
Future observations after 2025 are not used to fit or evaluate the model.

Baselines are passive market, cash, fixed 50/50 market/cash, and a 12-month trend
rule with the identical information lag. Costs are charged on risky-asset turnover,
including initial entry and rebalancing from drifted weights, at 0/10/25 bps.
Portfolio returns reinvest remaining capital after the modeled fee. No terminal
liquidation is assumed. Reported Sharpe uses monthly RF; drawdown includes initial
wealth. Positions continue through the validation/test boundary without a reset.

The output is a **research-market simulation**, not an ETF/futures backtest. Current
French data reconstruct historical returns; CIZ/FIZ and RF-source changes matter.
Using chronological samples does not make these data point-in-time. No claim of
alpha, trading readiness, or reproduction of the AQR multi-market study is made.
The fixed half-exposure baseline helps reveal improvements due merely to holding
less market risk. Subperiods/cost scenarios/bootstrap were specified in advance;
none chooses a winning strategy. Bootstrap intervals are descriptive and do not
adjust for choosing this topic after reading published literature.

Method references:
- [French data and revision notes](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- [Factor construction](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html)
- [Hurst, Ooi, Pedersen, 2017](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf)

This lab's maintained scope is download/validate → frozen fit → chronological
prediction → transparent portfolio arithmetic → reproducible evidence. Integrating
a research agent, choosing tradable data, or expanding model searches requires a
separate experiment; it is not silently done by this script.
