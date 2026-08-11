# 270 Company Product Evidence Graph Public Gap

Date: 2026-06-11

## Prompt

After targeted repair, fill the 600+ company universe by evidence graph. Commercial gaps are allowed, but only after public/free/available sources are checked; do not turn missing commercial data into fallback facts or a garbage pile.

## Decision

Keep the accepted SEC product-KPI fact layer unchanged at `company_product_kpi_facts_parser_verified_with_structured_v0_1.jsonl`: `6,162` parser-verified facts across `179` tickers. Targeted repair is useful for recall diagnostics, but its additions are not clean enough to promote automatically. The evidence graph therefore treats targeted repair additions as `review_queue_not_runtime_fact`, while SEC parser-verified rows remain the only runtime company product KPI facts.

Commercial market-tracker gaps are exposed only after the graph records which public sources were checked for the company/industry. Official, regulatory, macro, trade, resolver, and web-public rows can be context or leads, but they cannot be rewritten as company product sales, market share, channel inventory, prescriptions, POS sell-through, registrations, or app revenue estimates.

## Work Completed

- Added targeted structured taxonomy repair gates to `scripts/data_expansion/build_product_taxonomy_kpi_parser.py`.
- Added sentence-metric structured parsing support with explicit product/segment, value/unit, period, source URL, document id, and citation gates.
- Rejected broad table-row taxonomy repair as too noisy after full materialization audit.
- Added `scripts/data_expansion/build_company_product_evidence_graph.py`.
- Added `tests/test_company_product_evidence_graph.py`.
- Materialized a 603-company product evidence graph and explicit gap ledger under `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/`.

## Targeted Repair Result

Final strict sentence-only repair run:

- Normalized taxonomy nodes: `5,619` (`+29` repaired segment nodes).
- Repaired ticker count: `26`.
- Table taxonomy repair: disabled.
- Parser-verified facts in the repair run: `5,512` across `186` tickers.
- Repair output adds recall candidates, but also loses many accepted baseline fact ids and still contains sentence-relation noise, so it is not a replacement for the accepted `6,162`-fact baseline.

Promotion boundary:

- Accepted runtime SEC fact layer: `company_product_kpi_facts_parser_verified_with_structured_v0_1.jsonl`.
- Repair run output: `review_queue_not_runtime_fact`.
- Broad/table repair outputs are audit artifacts only and must not feed runtime.

## Evidence Graph Result

Materialized output:

- Companies: `603`.
- Evidence nodes: `5,857`.
- Gaps: `2,986`.
- SEC taxonomy coverage: `566` companies.
- SEC parser-verified product-KPI coverage: `179` companies.
- Repair candidate coverage: `103` companies, review only.
- Company-disclosed KPI gap: `424` companies.

Node promotion counts:

- `runtime_fact_allowed`: `179`.
- `runtime_context_taxonomy_only`: `566`.
- `context_or_lead_available`: `5,009`.
- `review_queue_not_runtime_fact`: `103`.

Gap counts:

- `commercial_market_tracker_gap_after_public_source_check`: `2,562`.
- `company_disclosed_product_kpi_not_verified`: `424`.

## Outputs

- Graph: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_graph_v0_1.jsonl`.
- Nodes: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_nodes_v0_1.jsonl`.
- Gaps: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_gaps_v0_1.jsonl`.
- Summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_graph_summary_v0_1.json`.
- Report: `Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/company_product_evidence_graph_execution.zh-CN.md`.
- Targeted repair report: `Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_taxonomy_kpi_parser_targeted_repair_strict_sentence_execution.zh-CN.md`.

## Evidence

- `python -m py_compile scripts\data_expansion\build_product_taxonomy_kpi_parser.py scripts\data_expansion\build_company_product_evidence_graph.py` -> pass.
- `python -m pytest tests\test_product_taxonomy_kpi_parser.py tests\test_company_product_evidence_graph.py tests\test_product_evidence_strategy_artifacts.py tests\test_public_source_strength_materialization_report.py tests\test_public_source_extended_materialization.py` -> `31 passed`.

## Follow-Up

- Do source-specific promotion gates for graph nodes before Evidence Fusion or Specialist prompts can consume them as runtime evidence.
- Add manual/high-confidence review for the `103` repair-candidate companies before any targeted repair rows are promoted.
- Build public-source parsers for specific industry claims, for example DART tables, NHTSA model/recall context, ClinicalTrials/openFDA product status, FDIC institution context, and EIA energy context.
- Keep commercial tracker gaps explicit under no-commercial policy until the user approves a licensed provider path.

## Safety Notes

- Large outputs remain on Z because D has very little free space.
- No API keys or secrets were written to tracked files.
- The graph deliberately separates `runtime_fact_allowed`, `context_or_lead_available`, and `review_queue_not_runtime_fact` to prevent proxy fallback claims.
