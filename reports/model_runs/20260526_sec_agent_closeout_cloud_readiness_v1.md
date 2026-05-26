# Model Run: 20260526_sec_agent_closeout_cloud_readiness_v1

## Summary

- Purpose: Run the first-version closeout readiness gate on cloud with real saved full-source DeepSeek runs attached through `--saved-full-source-run-dir --require-full-source-artifacts`.
- Status: completed with no blockers; overall readiness remains `warn` because the local planner diagnostic uses the heuristic planner instead of the production DeepSeek planner.
- Run type: closeout readiness evaluation
- Timestamp: 2026-05-26
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, Python `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`

## Code And Command

- Entry point: `scripts/evaluate_sec_agent_resume_closeout_readiness.py`
- Main command profile:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir <saved_full_source_run_dir> \
  --require-full-source-artifacts \
  --latency-profile-case-path eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b/case.jsonl \
  --timeout-s 900
```

- Git state: local source commit `ba0129f`; cloud workspace is a file-synced project directory without a `.git` checkout.
- Safety: no credentials were written to repo files.

## Inputs

- Full-source manifest: `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl`
- Full-source BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027`
- Full-source ObjectBM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects`
- Market evidence: `data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- Latest interactive saved run: `eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b`
- Full30 benchmark saved run: `eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark/20260526_024807_3fbff2951a`

## Cloud Prep

- Synced missing cloud check scripts:
  - `scripts/evaluate_sec_agent_context_api_smoke.py`
  - `scripts/benchmark_sec_agent_context_api.py`
- Rebuilt the full30 ObjectBM25 index from `data/processed_private/evidence_objects/sec_tech_primary_mixed_with_8k_earnings_full30_evidence_fy2023_2027.jsonl`.
- Rebuilt object index summary:
  - object records: `347015`
  - metrics: `257458`
  - claims: `77745`
  - tables: `11812`

## Results

- Interactive saved-run readiness report: `reports/quality/resume_closeout/20260526_201655_resume_closeout_readiness_local_v1.json`
  - overall: `warn`
  - blocker failures: `0`
  - status counts: `pass=11`, `warn=1`, `skipped=0`
  - P0 readiness: `pass=6/6`
  - saved run elapsed: `78.5981 sec`
  - saved run market rows: `2`
  - saved run gate failures: `0`
  - fallback answers: `0`

- Full30 saved-run readiness report: `reports/quality/resume_closeout/20260526_202136_resume_closeout_readiness_local_v1.json`
  - overall: `warn`
  - blocker failures: `0`
  - status counts: `pass=11`, `warn=1`, `skipped=0`
  - P0 readiness: `pass=6/6`
  - saved run elapsed: `253.8526 sec`
  - saved run selected tickers: `30`
  - saved run market rows: `30`
  - saved run gate failures: `0`
  - coverage complete: `true`
  - primary task support complete: `true`
  - fallback answers: `0`

## Timing Notes

- Latency profile in the full30 readiness rerun:
  - BM25 init: `0.834 sec`
  - ObjectBM25 init: `10.626 sec`
  - candidate generation: `2.3681 sec`
  - first runtime ledger build: `8.4241 sec`
  - cached runtime ledger build: `0.2261 sec`
  - coverage matrix: `0.098 sec`
- Context API small pressure:
  - `40/40` requests passed under mixed workload with concurrency `4`

## Interpretation

- The cloud P0 items from the closeout checklist are green under the saved-run readiness gate: performance/resource tracking, stage observability, source/index presence, context state consistency, fixture resume/recovery, and multi-case main-chain stability.
- The remaining warning is `planner_contract_eval_local`, which intentionally evaluates the heuristic planner as a local diagnostic. It should be replaced or supplemented by a real DeepSeek planner-contract eval before claiming a fully green production planner gate.
- Generated cloud `reports/quality/` JSON artifacts remain runtime outputs and are not staged in Git.
