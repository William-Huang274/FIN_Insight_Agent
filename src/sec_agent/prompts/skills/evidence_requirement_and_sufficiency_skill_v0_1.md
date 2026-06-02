# Evidence Requirement and Sufficiency Skill v0.1

Use this skill in planning, coverage reflection, and second-pass retrieval. The model should describe what evidence is needed in business terms; the compiler maps those needs to physical routes.

## EvidenceRequirementPlan Contract

For each research task, specify:

- `requirement_id`: stable id.
- `task_id`: matching decomposed task.
- `analysis_intent`: fundamental change, peer comparison, supply-chain validation, market reaction, valuation context, industry context, or risk review.
- `tickers`: company scope or peer scope.
- `years`: fiscal years available in the inventory.
- `filing_types`: 10-K, 10-Q, 8-K, 20-F, 40-F, or 6-K only when available.
- `source_tiers`: SEC primary filing, company-authored unaudited filing, market snapshot, industry snapshot, or future approved source tier.
- `metric_families`: revenue, margin, capex, cash flow, RPO, deposits, credit quality, inventory, industry-specific metric families, or empty for text-only tasks.
- `period_roles`: ANNUAL, QTD, YTD, TTM, or INSTANT. Never mix these silently.
- `evidence_routes`: ledger_first, filing_text, 8k_commentary, market_snapshot, industry_snapshot, or risk_text.
- `section_hints`: MD&A, risk factors, segment tables, liquidity/capital resources, earnings release, exhibit 99, or industry dataset family.
- `candidate_budget` and `rerank_budget`: route-level budgets; ledger, market, and industry routes do not need BGE rerank.

## Sufficiency Rules

Evidence is sufficient only when:

- The requested companies, years, source tiers, and period roles are covered or gaps are explicit.
- Financial facts come from ledger rows or structured objects with source object ids.
- Management explanation has 8-K or filing text evidence if the answer uses management narrative.
- Market claims have market evidence rows, field refs, and `as_of_date`.
- Industry claims have source family, provider, dataset id, and observation date.
- Risk or counterevidence claims have source support, not just generic caution.

## Second-Pass Policy

Trigger one second pass when:

- A required metric family is missing but the company/year/source exists.
- A management explanation is needed and 8-K evidence exists but was not retrieved.
- A market/valuation claim is needed and market snapshot exists but fields were not attached.
- An industry context claim is needed and an industry source family exists but was not attached.
- Peer comparison selected too few peer rows for the requested scope.

After the second pass:

- If evidence becomes sufficient, continue to synthesis.
- If evidence remains partial, answer with the strongest supported claims, lower confidence, and clear missing evidence boundaries.
- Do not output a separate "suggested lookup" section for evidence that the system could already query; keep the reason in run trace and incorporate the result into the memo.
