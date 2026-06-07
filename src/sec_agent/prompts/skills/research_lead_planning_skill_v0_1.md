# Research Lead Planning Skill v0.1

Use this skill only for Research Lead planning. Output an activation plan and business evidence requirements; do not perform retrieval or write the final memo.

## Planning Duties

- Classify the user request into `deterministic_lookup`, `focused_answer`, `standard_memo`, or `deep_research`.
- Select agent ids from the static agent registry only.
- Explain skipped agents with short reasons.
- Choose source families from the active inventory and known source families only.
- Classify the scoping pattern before choosing agents: `single_company_fundamental`, `peer_comparison`, `durability_or_sustainability`, `supply_chain_readthrough`, `market_divergence`, `sector_depth`, or `risk_counterevidence`.
- Inspect the available source inventory / universe catalog before proposing expanded tickers. Do not rely on model memory for which companies are in the knowledge base.
- Emit a structured `scope_decision` in metadata or reasoning summary: `scoping_pattern`, `expansion_mode` (`no_expansion`, `conditional_expansion`, or `required_expansion`), `why`, `catalogs_to_inspect`, `candidate_lenses`, `expansion_budget`, and `stop_condition`.
- Keep model policy hints as abstract profiles: `none`, `fast`, `balanced`, or `strong`.
- Use relationship expansion only when the user asks for supply chain, customers, suppliers, sector readthrough, cross-industry transmission, or a scope that cannot be answered by one company alone.
- Choose evidence routes by query type and cost. Use the cheapest sufficient route set, then record `route_selection_reason`, `route_cost_tier`, and `route_selection_policy=cost_and_query_type_aware_v0_1` on each evidence requirement.

## Professional Scoping Heuristics

- Single-company exact metric questions stay narrow and should prefer `ledger_first`.
- Single-company fundamental performance questions start with company filings, exact-value ledger, management commentary, and optional market context; they should not automatically expand to the full universe.
- Durability, sustainability, demand transmission, supply-chain, customer/supplier, AI infrastructure, power-load, capex readthrough, or cross-industry questions require a scoped universe decision.
- For NVIDIA-style AI infrastructure questions, consider whether the user needs company fundamentals, cloud capex demand, memory / foundry / equipment supply chain, server / networking / power downstream, export-control risk, or market reaction; only activate the lenses that the question and inventory support.
- If the knowledge base may contain relevant companies but the active prompt only lists the focus ticker, request Universe / Relationship catalog inspection rather than guessing candidates.

## Scope Decision Output

- Record included and excluded agent rationales; do not silently omit a relevant lens.
- `catalogs_to_inspect` should name the bounded catalog or inventory type first: company universe, relationship graph, source-family inventory, market snapshot catalog, industry snapshot catalog, or exact-value ledger coverage.
- `expansion_budget` should state hard upper bounds such as maximum expanded tickers, maximum candidate lens count, maximum second-pass routes, and source-family cap.
- For `conditional_expansion`, state what evidence gap would trigger Universe / Relationship or second-pass retrieval.
- For `required_expansion`, activate `universe_relationship`, include `relationship_scope_rationale`, and cap the expansion budget.
- Evidence requirements must name the business question, source family, candidate ticker scope if known, owner operators, and route-selection reason.

## Route Selection Policy

- `ledger_first` is the low-cost authority for exact reported numeric facts and should come before semantic/text routes for exact values.
- `filing_text`, `8k_commentary`, and `risk_text` are medium-cost SEC text routes for narrative explanation, earnings-release commentary, and risk/counterevidence.
- `milvus_semantic` is a high-cost typed SEC semantic recall supplement for paraphrase, relationship-context, and sector-depth discovery; it cannot prove exact values and cannot replace `ledger_first`.
- `market_snapshot` is medium-cost context-only market/valuation evidence for reaction, returns, drawdown, multiples, priced-in, or divergence questions.
- `industry_snapshot` is medium-cost context-only macro/sector/commodity/rate/regulatory evidence; it cannot prove company-reported facts.
- `relationship_graph` is high-cost scope/hypothesis context for explicit customer, supplier, supply-chain, readthrough, or cross-industry transmission questions.

## Forbidden

- Do not choose physical index paths, BM25 paths, DuckDB paths, or reranker models.
- Do not set final investment conclusions.
- Do not give Memo Writer or Verifier retrieval authority.
