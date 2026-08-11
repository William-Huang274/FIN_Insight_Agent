# 230 Fin Agent Issue 2-4 Targeted Repairs

## Summary

- Date: 2026-06-02
- Branch: `codex/api-model-call-architecture`
- Scope: repair only the full17 failure buckets 2-4, without rerunning the whole 17-case suite.
- Target buckets:
  - 2: sector-depth / relationship evidence quality and second-pass budget loop.
  - 3: exact lookup deterministic row selector and exact-value runtime ledger gate.
  - 4: multi-turn focused/deep-research activation, source/operator alignment, and budget stability.

## Changes

1. Exact lookup gate and selector:
   - `scripts/eval_multi_agent_real_llm_chain.py` now allows exact deterministic lookup to satisfy the real retrieval gate through `runtime_ledger_rows` when the case explicitly requires runtime ledger rows.
   - `src/sec_agent/langgraph_orchestrator.py` ranks deterministic lookup rows by requested metric family, answer role, and amount-vs-rate fit, reducing capex/provision answers being displaced by broad balance-sheet or rate rows.

2. Sector-depth evidence quality:
   - Real-evidence quality scoring now recognizes bounded row refs across `evidence_ref`, `evidence_id`, `ref_id`, `metric_id`, `source_evidence_id`, and related IDs.
   - Bounded rows preserve `raw_value_text`, `display_value_zh`, and `source_statement` so temporal / YoY claims can be checked against real row values.
   - Temporal-ref detection no longer misclassifies non-temporal phrasing like demand growth "from AI data centers" as a two-period numeric inference.

3. Multi-turn activation and source/operator alignment:
   - `Research Lead` normalization now aligns active source families with operators: 8-K source activates `eight_k_operator`; market source activates `market_operator`, and standard market cases can activate market valuation.
   - Focused-answer fallback routing now honors company-authored 8-K and market source requests.
   - Evidence requirement planning reconciles activation-required source families, so an active `market_operator` cannot be lost because the LLM evidence plan was narrower than the activation plan.

4. Sector-depth budget-loop repair:
   - `quality_second_pass` now suppresses a top-level budget loop break when the pass has already produced incremental evidence rows and only remaining routes hit per-agent/tool budget.
   - The suppressed reason remains in `second_pass_result.suppressed_loop_break_reason` for audit.
   - Market snapshot arguments in `deep_research + relationship_graph` now expand to `search_scope_tickers` when bounded to <= 12 tickers, so sector-depth market context covers both focal and relationship-side tickers earlier.
   - Market snapshot route coalescing now groups routes across ticker groups and promotes coverage scope back to route-level fields for stable tool arguments and audit.

## Verification

Local:

- `python -m compileall src\sec_agent\langgraph_orchestrator.py src\sec_agent\multi_agent_runtime.py scripts\eval_multi_agent_real_llm_chain.py`
- `pytest -q tests\test_multi_agent_langgraph_routing.py` -> `20 passed`
- `pytest -q tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_research_lead_llm.py` -> `34 passed`

Real DeepSeek targeted runs:

- `20260602_fin_agent_issue_2_4_targeted_exact_multi_v0_2`: `6` targeted exact/multi-turn cases, `5/6` pass. Exact lookup and semis multi-turn passed; banking T2 exposed missing market route reconciliation.
- `20260602_fin_agent_issue_2_4_targeted_banking_t2_market_v0_1`: banking T1/T2 targeted rerun, `2/2` pass after source/operator reconciliation.
- `20260602_fin_agent_issue_2_sector_utilities_targeted_v0_1`: utilities sector-depth failed only on top-level `agent_tool_budget_exhausted`; real retrieval and real Specialist quality already passed.
- `20260602_fin_agent_issue_2_sector_utilities_budget_fix_v0_1`: utilities sector-depth `1/1` pass after quality second-pass loop suppression, `13` tool calls.
- `20260602_fin_agent_issue_2_sector_utilities_scope_budget_fix_v0_2`: utilities sector-depth `1/1` pass after market scope expansion, `11` tool calls, real retrieval `1/1`, real Specialist quality `1/1`, all hard checks true.

No full 17-case rerun was performed in this repair slice.

## Current Assessment

- Issue 3 exact lookup is repaired for the tested capex and banking provision cases.
- Issue 4 multi-turn focused source/operator alignment is repaired for the tested banking T2 case and semis T2 remains passing from the targeted run.
- Issue 2 sector-depth utilities is repaired at gate level: relationship lookup, SEC/BM25/ObjectBM25/BGE, market/industry rows, Specialist quality, Memo Writer, and Verifier all pass.
- Remaining cost note: utilities still records a suppressed quality-second-pass budget reason inside `second_pass_result` and can still run a second market snapshot call under coverage second-pass. It no longer fails the gate and total calls are within case budget, but a future cost pass should filter already-covered second-pass market routes.
