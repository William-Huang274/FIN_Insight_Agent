# Shared Evidence Boundary Skill v0.1

Use this skill in every model-backed multi-agent role. Stay inside the evidence objects and source families already present in graph state.

## Source Boundaries

- SEC 10-K and 10-Q plus Exact-Value Ledger support company-reported financial facts.
- SEC 8-K earnings releases are company-authored unaudited material. Use them for management explanation, demand, guidance, orders, and commentary, not audited facts.
- Market snapshots support non-real-time market reaction, return, event-window, and valuation context only. Keep `snapshot_id` and `as_of_date`.
- Industry snapshots support macro, sector, commodity, regulatory, and demand context only. They cannot replace company financial facts.
- Relationship graph evidence can define a research scope or hypothesis. It does not prove revenue, margin, cash flow, or balance-sheet values.

## Required Behavior

- Do not use model memory to add named facts, numbers, customer lists, suppliers, current prices, or news.
- Do not mix ANNUAL, QTD, YTD, TTM, and INSTANT values without explicit period-role language.
- Do not directly call tools unless the agent registry grants `bounded_execute` or `orchestrate_subgraph`.
- Inspect-only agents may not request fresh retrieval in prose, but they must emit structured `evidence_gap_requests` when a material source, metric, ticker, relationship confirmation, market field, or industry context is missing.
- `evidence_gap_requests` are routed to Coverage / Reflection first. Coverage decides whether to compile a second-pass route, ask Universe / Relationship to rescope, or allow a bounded answer.
- Each `evidence_gap_requests` item must include `request_type`, `owner_agent`, `tickers`, `source_family`, `reason`, `blocking_level`, and `can_answer_bounded_without`.
- If evidence remains partial, allow a bounded answer with explicit unsupported claims and missing source boundaries.

## Evidence Gap Request Types

- `missing_metric`: a company-reported metric, period, unit, or ledger row is needed.
- `missing_source_family`: the selected source family was expected but absent from bounded rows.
- `additional_company_scope`: the current ticker scope is too narrow and should return to Universe / Relationship before more retrieval.
- `relationship_confirmation`: a customer, supplier, peer, infrastructure, or economic-link hypothesis needs relationship evidence or company confirmation.
- `market_field`: a market reaction, valuation, return, volume, or snapshot timing field is missing.
- `industry_context`: an industry, macro, commodity, regulatory, demand, or power/load context row is missing.
- `counterevidence_test`: a thesis needs direct risk, conflict, or disconfirming evidence before a full memo can be supported.
