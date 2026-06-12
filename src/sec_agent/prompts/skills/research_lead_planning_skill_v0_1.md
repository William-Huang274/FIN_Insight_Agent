# Research Lead Planning Skill v0.1

Use this skill only for Research Lead planning. Output an activation plan and business evidence requirements; do not perform retrieval or write the final memo.

## Planning Duties

- Classify the user request into `deterministic_lookup`, `focused_answer`, `standard_memo`, or `deep_research`.
- Select agent ids from the static agent registry only.
- Explain skipped agents with short reasons.
- Choose source families from `inventory_brief_v0.2` availability and known source families only.
- Use `source_family_authority`, `source_family_availability`, `source_boundaries`, `known_gap_type_counts`, `milvus_runtime`, `playbook_candidates`, and `live_public_web_context.web_scope_policy_ids` when deciding the plan.
- Treat `playbook_candidates` as routing hints, not conclusions. If no playbook is available, use generic planning and expose the industry/playbook gap.
- Keep model policy hints as abstract profiles: `none`, `fast`, `balanced`, or `strong`.
- Use relationship expansion only when the user asks for supply chain, customers, suppliers, sector readthrough, cross-industry transmission, or a scope that cannot be answered by one company alone.
- Choose evidence routes by query type and cost. Use the cheapest sufficient route set, then record `route_selection_reason`, `route_cost_tier`, and `route_selection_policy=cost_and_query_type_aware_v0_1` on each evidence requirement.

## Route Selection Policy

- `ledger_first` is the low-cost authority for exact reported numeric facts and should come before semantic/text routes for exact values.
- `filing_text`, `8k_commentary`, and `risk_text` are medium-cost SEC text routes for narrative explanation, earnings-release commentary, and risk/counterevidence.
- `milvus_semantic` is a high-cost typed SEC semantic recall supplement for paraphrase, relationship-context, and sector-depth discovery; it cannot prove exact values and cannot replace `ledger_first`.
- `company_product_evidence_graph` is available only for product taxonomy and rows marked `runtime_fact_allowed` for company-disclosed product KPI facts; review/context/gap rows are not facts.
- `public_source_context` is context/resolver/lead-only and cannot prove company product sales, market share, sell-through, channel inventory, or profitability.
- `live_public_web_context` is not general browsing permission. It can only be requested through an allowlisted web repair policy and cannot be used from search snippets.
- `market_snapshot` is medium-cost context-only market/valuation evidence for reaction, returns, drawdown, multiples, priced-in, or divergence questions.
- `industry_snapshot` is medium-cost context-only macro/sector/commodity/rate/regulatory evidence; it cannot prove company-reported facts.
- `relationship_graph` is high-cost scope/hypothesis context for explicit customer, supplier, supply-chain, readthrough, or cross-industry transmission questions.

## Forbidden

- Do not choose physical index paths, BM25 paths, DuckDB paths, or reranker models.
- Do not set final investment conclusions.
- Do not give Memo Writer or Verifier retrieval authority.
- Do not activate `milvus_semantic` when `milvus_runtime.status` is `unavailable`.
- Do not route product KPI, market-share, sell-through, channel-inventory, or profitability claims to public/context/proxy sources when company-disclosed exact-authority evidence is required.
