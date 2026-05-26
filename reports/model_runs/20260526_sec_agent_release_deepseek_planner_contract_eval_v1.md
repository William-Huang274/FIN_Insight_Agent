# Model Run: 20260526_sec_agent_release_deepseek_planner_contract_eval_v1

## Summary

- Purpose: Close the remaining first-release planner warning by running a real DeepSeek planner-contract eval over the 5-case closeout planner set.
- Status: completed; accepted.
- Run type: planner inference + evaluation
- Timestamp: 2026-05-26
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, Python `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`, DeepSeek `deepseek-v4-pro`

## Code And Command

- Entry point: `scripts/run_sec_free_query_planner_eval.py`
- Evaluator: `scripts/evaluate_sec_free_query_planner.py`
- Eval set: `eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl`
- Contracts output: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_contracts_20260526_r3.jsonl`
- Report output: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`
- API key handling: injected through `DEEPSEEK_API_KEY` environment variable only; no credential was written to repo files.

## Inputs

- Manifest: `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027`
- ObjectBM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects`
- Source policy: `SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`
- Planner settings: `QUERY_PLANNER=llm`, `LLM_BACKEND=deepseek`, `MODEL_NAME=deepseek-v4-pro`, `DISABLE_THINKING=1`, `PLANNER_MAX_TOKENS=4000`, `PLANNER_TIMEOUT_S=240`

## Contract Fixes Before Accepted Run

- The closeout planner eval was aligned to the actual manifest-proven release scope: FY2023-FY2025 annual 10-K plus latest FY2026 10-Q/8-K. The prior eval expected FY2027 even though the accepted full30 manifest contains no FY2027 rows.
- Planner evaluator now counts source-boundary terms found in `required_caveats`, `forbidden_claims`, and `market_snapshot` blocks, not only `decomposed_tasks`.
- Query Contract repair now strips unrequested analyst-consensus, macro, and geopolitical tasks/queries when those sources are not asked for by the user.

## Results

- `case_count=5`
- `pass_count=5`
- `fail_count=0`
- `task_type_accuracy=1.0`
- `primary_ticker_recall=1.0`
- `peer_ticker_recall_any_of=1.0`
- `required_task_coverage=1.0`
- `metric_family_recall=0.96`
- `year_compliance=1.0`
- `source_boundary_violation_rate=0.0`
- `schema_validation_pass_rate=1.0`
- `meets_step1_acceptance=true`

## Interpretation

This closes the earlier release readiness warning that came from a heuristic planner diagnostic. The accepted cloud run validates the real DeepSeek planner route for the current full-source release scope. The remaining `partial_metric_family_coverage` warning is non-blocking because the aggregate metric-family recall remains above threshold.
