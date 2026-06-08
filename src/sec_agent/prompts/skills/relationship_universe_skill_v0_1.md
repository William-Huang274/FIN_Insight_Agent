# Relationship Universe Skill v0.1

Use this skill only for Universe / Relationship planning. Expand research scope from bounded relationship evidence and source inventory.

## Focus

- Peer, competitor, customer, supplier, sector, and macro-sensitive relationship scope.
- Inclusion and exclusion rationale for focus tickers and expanded tickers.
- Evidence needs that downstream operators can compile.
- Professional universe construction from a bounded catalog: peers, competitors, upstream suppliers, downstream customers, infrastructure dependencies, power/utilities readthrough, non-US supply-chain disclosure companies, and sector or macro-sensitive proxies.
- Source coverage awareness: whether each candidate has SEC primary filings, company-authored unaudited material, market snapshot, industry snapshot, relationship graph rows, or global public disclosure coverage.
- Per-lens candidate selection from catalog only: `peer_competitor`, `upstream_supplier`, `downstream_customer`, `infrastructure_dependency`, `power_utilities_readthrough`, `non_us_supply_chain_disclosure`, `market_divergence_peer`, or `sector_macro_proxy`.

## Output Rules

- Return a `UniverseRelationshipPlan`.
- Relationship evidence can support scope and hypotheses only.
- Full-universe or sector-representative scope must include a short rationale.
- Missing relationship evidence must become an unsupported relationship, not a supported expansion.
- Each included non-focus ticker must have `included_ticker`, `candidate_lens`, `inclusion_rationale`, `available_source_families`, `relationship_strength`, `downstream_operator_owner`, and `source_gap` when applicable.
- `relationship_strength` must be one of `verified`, `inferred`, `hypothesis`, or `source_gap`; do not upgrade hypothesis-only relationship evidence into verified exposure.
- `downstream_operator_owner` should name who can compile the next evidence: `sec_operator`, `eight_k_operator`, `market_operator`, `industry_operator`, `coverage_reflection`, or `universe_relationship`.
- Exclude plausible but unsupported companies when the catalog/source coverage cannot support them; each excluded candidate should have `excluded_ticker`, `candidate_lens`, and `exclusion_rationale` rather than expanding blindly.
- Keep the expanded ticker budget tight. Prefer a representative, evidence-seeking candidate set over all companies in a sector.
- When the current bounded relationship lookup is insufficient, emit evidence requirements or unsupported relationships for Coverage / Reflection; do not fill the gap from model memory.

## Operator Ownership

- Company filings, exact-value ledger coverage, and company-authored disclosure gaps go to `sec_operator` or `eight_k_operator`.
- Market reaction, valuation multiple, event-window return, volume, or relative-performance gaps go to `market_operator`.
- Sector, commodity, rate, regulation, demand, power/load, or infrastructure context gaps go to `industry_operator`.
- Relationship confirmation, additional company scope, and non-US supply-chain disclosure candidate selection go to `universe_relationship` first, then Coverage decides whether an operator second pass is warranted.
- If no bounded catalog/source family can support a candidate, mark `source_gap` and exclude or request rescope; do not keep it as a supported included ticker.

## Forbidden

- Do not prove revenue, margin, cash flow, or balance-sheet facts from relationship graph evidence.
- Do not expand to all companies without relationship evidence and a budget guard.
- Do not choose physical graph paths, databases, or retrieval tools.
- Do not add customers, suppliers, or named counterparties only from general market knowledge.
