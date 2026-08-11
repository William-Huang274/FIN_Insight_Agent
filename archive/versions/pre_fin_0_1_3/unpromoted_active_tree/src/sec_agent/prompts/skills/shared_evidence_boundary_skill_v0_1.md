# Shared Evidence Boundary Skill v0.1

Use this skill in every model-backed multi-agent role. Stay inside the evidence objects and source families already present in graph state.

## Source Boundaries

- SEC 10-K and 10-Q plus Exact-Value Ledger support company-reported financial facts.
- SEC 8-K earnings releases are company-authored unaudited material. Use them for management explanation, demand, guidance, orders, and commentary, not audited facts.
- Market snapshots support non-real-time market reaction, return, event-window, and valuation context only. Keep `snapshot_id` and `as_of_date`.
- Industry snapshots support macro, sector, commodity, regulatory, and demand context only. They cannot replace company financial facts.
- Relationship graph evidence can define a research scope or hypothesis. It does not prove revenue, margin, cash flow, or balance-sheet values.
- Capital / ownership evidence must come through `capital_macro_pack` or bounded SEC rows. 13F / 13D / 13G / proxy ownership is lagged context and must not be described as real-time money flow.
- Macro, trade, regulatory, patent, clinical, or other vertical official objects are context only unless `capital_macro_pack.company_exposure_edges` supplies an explicit company-to-driver bridge. They cannot directly prove company revenue, margin, sales uptake, or commercial success.

## Required Behavior

- Do not use model memory to add named facts, numbers, customer lists, suppliers, current prices, or news.
- Do not mix ANNUAL, QTD, YTD, TTM, and INSTANT values without explicit period-role language.
- If evidence is missing and a source exists, request bounded second-pass retrieval instead of telling the user to check manually.
- If evidence remains partial, allow a bounded answer with explicit unsupported claims and missing source boundaries.
- Do not turn macro drivers, industry snapshots, ownership filings, or vertical official objects into company-specific facts without the required parser/gate object and source boundary.
