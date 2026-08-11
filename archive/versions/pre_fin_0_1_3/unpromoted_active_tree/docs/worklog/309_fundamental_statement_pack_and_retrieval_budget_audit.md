# 309 - Fundamental Statement Pack and Retrieval Budget Audit

Date: 2026-06-13

## Objective

Implement the next memo-depth upgrade after the diagnostic full-chain runs exposed two related gaps:

- Fundamental analysis did not yet treat income statement, balance sheet, and cash flow statement analysis as a normal dimension of the memo.
- The pipeline had not audited whether retrieval candidate/rerank budgets or role-specific evidence caps were starving downstream agents.

This work follows the user-approved 1-5 sequence:

1. Audit and use SEC/FSD/companyfacts/ledger coverage for financial statement analysis.
2. Add a financial statement taxonomy and industry-specific financial focus policy.
3. Generate a FundamentalStatementPack with three-statement rows, period changes, derived metrics, and peer comparisons.
4. Upgrade the fundamental analyst into a dimension analyst instead of a generic evidence summarizer.
5. Carry the result through ClaimCards, Thesis / Counter-thesis, JudgmentState, and Memo Writer.

## Implemented

- Added `src/sec_agent/financial_statement_analysis.py`.
  - `FinancialStatementTaxonomy` covers income statement, balance sheet, cash flow, and derived metrics.
  - `IndustryFinancialFocusPolicy` gives industry-specific priority metrics for semiconductor/hardware, SaaS, consumer electronics, autos/EV, banks, pharma/biotech/medtech, energy/utilities, retail/CPG, and general coverage.
  - `FundamentalStatementPack` is built from parser/reconciliation/derived-metric controlled rows.
  - Peer comparison is intentionally conservative: same metric, same period key, same unit, and company-total scope only.
  - Public proxy / industry / semantic rows remain context or gap material and cannot become company financial facts.

- Wired FundamentalStatementPack into the multi-agent runtime.
  - `build_agent_data_view` now attaches a compact pack reference for the fundamental analyst.
  - The fundamental analyst gets explicit claim slots for three-statement quality, peer comparison, industry focus metrics, and product/capital bridge.
  - Specialist prompt and repair payload include compact pack rows and allow citation refs from the pack.

- Added deterministic JudgmentState before memo writing.
  - `attach_judgment_state(...)` converts thesis-driver dimension sections and fundamental pack summaries into a dimension-first judgment state.
  - Memo Writer now uses `judgment_state.dimension_judgments` before raw claim cards or thesis-driver rows.
  - Model-emitted `judgment_state` is stripped and replaced with deterministic state from the runtime.

- Persisted the new artifacts in the graph.
  - `fundamental_statement_pack.json`
  - `judgment_state.json`
  - Summary/checkpoint payloads now expose line-item counts, peer-comparison counts, validation status, and judgment dimension counts.

- Added retrieval budget diagnostics to the output quality audit.
  - The audit now reports SEC candidate rows before rerank, rows sent to BGE, post-rerank proxy rows, observed route budgets, specialist-visible row counts, and budget-related proxy flags.
  - It explicitly marks true recall/rerank precision as unavailable unless a gold relevant-document / target-in-candidate label set exists.

## Diagnostic Result

Re-audited the saved R7 diagnostic full-chain artifacts:

- `fin_diag_ai_infra_dell_product_capex_zh`
  - SEC pre-rerank candidates: `1081`
  - sent to BGE: `671`
  - post-rerank proxy rows: `578`
  - route budget hits: `0`
  - specialist visible rows: `fund=32, ind=32, mkt=7, prod=4, risk=20`
  - flags: `some_specialist_inputs_tightly_capped`, `product_specialist_visible_rows_too_low`

- `fin_diag_healthcare_product_regulatory_gap_zh`
  - SEC pre-rerank candidates: `755`
  - sent to BGE: `755`
  - post-rerank proxy rows: `478`
  - route budget hits: `0`
  - specialist visible rows: `fund=32, ind=32, mkt=14, prod=4, risk=20`
  - flags: `some_specialist_inputs_tightly_capped`, `product_specialist_visible_rows_too_low`

Conclusion: the old R7 failure pattern was not primarily a global candidate or BGE rerank budget ceiling. Candidate volume and rerank surface were adequate, and route budgets were not hit. The measurable issue was role-specific visibility, especially the Product / Technology Specialist only seeing four rows in both diagnostic cases. The current code raises fundamental/product runtime and prompt budgets, but product-source selection and product-specific evidence availability remain a separate follow-up.

## Verification

- `python -m py_compile src/sec_agent/financial_statement_analysis.py src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_contracts.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/audit_multi_agent_output_quality.py`
- `pytest -q tests/test_financial_statement_analysis.py tests/test_multi_agent_output_quality_audit.py`
- `pytest -q tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py`
- `pytest -q tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py`
- `pytest -q tests/test_derived_metric_layer.py tests/test_sec_agent_retrieval_plan.py`
- Combined targeted regression: `144 passed`

## Boundaries and Follow-ups

- Strict retrieval recall and rerank precision still require a labeled eval set; current audit is a proxy/budget diagnostic.
- Product / Technology evidence remains the largest observed row-visibility gap and needs source-selector quota/backfill work before the next full-chain quality run.
- DB materialization of FundamentalStatementPack / JudgmentState is not added in this slice; D-series DB hardening can add durable tables after the runtime shape stabilizes.
- Industry financial focus policy is v0.1 and should be expanded as new sector-specific full-chain cases expose missing metrics.
