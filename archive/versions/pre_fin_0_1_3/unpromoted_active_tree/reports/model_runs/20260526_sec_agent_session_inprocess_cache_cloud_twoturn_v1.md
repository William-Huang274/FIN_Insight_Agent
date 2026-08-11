# Model Run: 20260526_sec_agent_session_inprocess_cache_cloud_twoturn_v1

## Summary

- Purpose: validate session-level in-process graph/context execution so BM25/ObjectBM25/BGE resources persist across follow-up turns.
- Status: completed.
- Run type: inference smoke.
- Timestamp: 2026-05-26.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, DeepSeek API synthesis, `session-mixed-8k-deepseek`.

## Code And Command

- Entry point: `scripts/cloud/sec_agent_interactive.sh session-mixed-8k-deepseek`.
- Key toggles: `graph_execution=in_process`, context runner `in_process`, `BGE_DEVICE=cuda`, `QUERY_PLANNER=llm`.
- Git state: dirty working tree; this run validates the staged working-copy behavior, not a clean commit.
- Secrets: API key and SSH password were supplied interactively or through transient environment variables only; no secret was written to files.

## Inputs

- Session log: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/manual_session_20260526_164403_context_session_turns.jsonl`
- Turn 1 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164427_33283b7f8a`
- Turn 2 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164641_12c1e1f556`
- Source policy: `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`.
- Scope: `MSFT`, `NVDA`; fiscal years `2023`, `2024`, `2025`, `2026`.
- Market snapshot: intentionally absent for this smoke; prompt did not request market data and the follow-up explicitly excluded price/market data.

## Outputs

- `sec_agent_state.json` exists for both turns with 12 completed/skipped stages and no failed stages.
- Query Contract for both turns kept `focus_tickers` and `search_scope_tickers` at `["MSFT","NVDA"]`.
- Query Contract for both turns omitted `market_snapshot`.
- Turn 2 deterministic gate summary: answer ledger, metric role term, table cell, named fact, ledger missing consistency, abstract judgment, caveat claim, ledger unit, metric source grounding, answer-vs-Judgment-Plan, v2 semantic contract, and qwen-answer gates all passed. Trap and gold-vs-pipeline gates were skipped as expected for this interactive smoke.

## Results

- Turn 1 retrieval/rerank: `context_runner=in_process`, `context_cache_hit=false`, `context_resource_load_ms=24968`, `elapsed_ms=38958`.
- Turn 2 retrieval/rerank: `context_runner=in_process`, `context_cache_hit=true`, `elapsed_ms=15969`.
- Observed improvement: the follow-up turn avoided resource reload and reduced retrieval/rerank stage time by about 59% in this two-company mixed 10-K/10-Q/8-K smoke.
- Scope stability: post-fix run stayed at 2 companies instead of expanding to full30.
- Source-boundary stability: market snapshot stayed absent when market/price data was explicitly excluded.

## Full-Source Market Snapshot Validation

- Session: `manual_session_20260526_181742`.
- Market evidence pack: `/root/autodl-tmp/FIN_Insight_Agent/data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`.
- Snapshot: `20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1`, `as_of_date=2026-05-22`.
- Turn 1 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_181811_921e4ad89c`.
- Turn 2 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b`.
- Both turns used `start_memo_analysis`, attached 2 market snapshot rows, had no missing artifacts, and passed all 12 main deterministic gates.
- Turn 1 retrieval/rerank: `context_cache_hit=false`, `context_resource_load_ms=21448`, `elapsed_ms=35942`.
- Turn 2 retrieval/rerank: `context_cache_hit=true`, `elapsed_ms=10498`.
- Controller route fixes added before the final pass: strip tool names before guard, treat substantive "continue/analyze/valuation/market reaction" follow-ups as scoped analysis, and prevent `get_session_state` from swallowing substantive follow-ups.

## Experiment Governance

- Hypothesis: in-process graph/context execution removes repeated BM25/ObjectBM25/BGE load cost across session turns without changing retrieval quality contracts or source-policy gates.
- Decision target: second turn reports `context_cache_hit=true`, all core artifacts complete, no failed graph stages, and deterministic gates still pass.
- Baseline: prior subprocess session turns reloaded retrieval/reranker resources per turn.
- Decision label: proceed.
- Mainline decision: keep `graph_execution=in_process` as default for API-backed session runs; preserve subprocess mode for local Qwen+BGE-first GPU-memory isolation.

## Runtime Efficiency

- First-turn fixed resource load: about 25.0 sec.
- Retrieval/rerank stage: 38.958 sec first turn versus 15.969 sec second turn.
- Remaining bottleneck: query planning and DeepSeek synthesis still dominate end-to-end wall time; BGE scoring still runs per query and was not removed.
- Next optimization: tune reranker candidate count/batch sizing and prompt context row caps under unchanged quality gates.

## Caveats And Next Step

- This smoke now validates both SEC + 8-K behavior and market-snapshot-active follow-up behavior on the two-company MSFT/NVDA slice.
- It does not claim production concurrency safety; request/session storage still needs transactional locking before production use.
- Next run should cover full-source SEC + 8-K + FMP/Yahoo market snapshot in a two-turn session.
