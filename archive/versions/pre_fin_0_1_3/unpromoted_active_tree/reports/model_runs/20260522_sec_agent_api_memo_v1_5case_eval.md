# Model Run: 20260522_sec_agent_api_memo_v1_5case_eval

## Summary
- Purpose: Run the full 5-case `sec_free_query_memo_quality_eval_v1` set through the API memo synthesis chain.
- Status: diagnostic completed
- Run type: inference + deterministic audit + memo-quality evaluation
- Timestamp: 2026-05-22
- Environment: cloud `westd`, `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command
- Runner: `/tmp/run_sec_agent_5case_memo_eval.sh`
- Entry point per case: `scripts/cloud/sec_agent_interactive.sh ask-deepseek`
- Profile: `USER_OUTPUT=1 SYNTHESIS_PROFILE=api_memo_v1 TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=5200 BGE_DEVICE=cuda`
- Eval set: `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`
- Secret handling: API key and SSH credentials were used only at runtime and were not written into repo files.

## Inputs
- Universe: 30 companies, fiscal years 2023-2025, SEC 10-K source boundary.
- Retrieval: BM25 + BGE-M3 rerank on CUDA.
- Intermediate artifacts per case: Query Contract, Evidence Coverage Matrix, runtime Exact-Value Ledger, Judgment Plan, DeepSeek memo answer, deterministic post-gates.

## Outputs
- Aggregate summary: `reports/quality/20260522_api_memo_v1_5case_125123/summary.json`
- Per-case artifacts:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_125201_60a9e00112`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_125556_c52f12a630`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_125958_961ed825c6`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_130400_914dee0e50`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_130827_ffe40ede99`

## Results

| Case | Gates | Memo Quality | API Latency MS | Tokens | Elapsed Sec |
|---|---:|---:|---:|---:|---:|
| `memo_nvda_growth_competitors_001` | 12/12 | 0.8270 | 101572 | 24242 | 237.7067 |
| `memo_amzn_aws_capex_002` | 11/12 | 0.9005 | 95403 | 30594 | 224.8205 |
| `memo_meta_ai_capex_rd_003` | 11/12 | 0.8590 | 99092 | 33539 | 245.8372 |
| `memo_jpm_rate_credit_004` | 11/12 | 0.9440 | 120466 | 27838 | 250.7750 |
| `memo_lly_growth_quality_005` | 12/12 | 0.8980 | 102029 | 27322 | 245.1332 |

Aggregate:
- Completed: `5/5`
- All gates green: `2/5`
- Mean memo quality: `0.8857`
- `qwen_answer_ratio`: `1.0` for every case
- Ledger repairs: `0`
- Failed gate type: `named_fact_gate_pass`

## Interpretation
The API memo interface is no longer the bottleneck for parse stability or basic answer usefulness. All cases produced model answers, all memo-quality scores cleared the threshold, and no run fell back to ledger repair.

The blocker moved upstream and sideways:
- AMZN: peer readthrough introduced unsupported peer company names.
- META: answer mentioned `Reality Labs` without cited support.
- JPM: retrieval/ledger drifted into irrelevant employee-diversity evidence and unsupported banking peer/metric names.

## Experiment Governance
- Hypothesis: `api_memo_v1` should pass the 5-case memo eval with useful memo outputs while retaining deterministic gates.
- Decision target: 5/5 completed, memo quality above threshold, and deterministic gates all green.
- Result: Memo quality passed, deterministic gates did not.
- Decision label: diagnostic-only for full 5-case reliability.
- Mainline decision: proceed with API memo synthesis as the model interface, but block reliability claims until planner/evidence coverage and named-fact support improve.

## Caveats And Next Step
- The memo scorer is currently too forgiving of unresolved sanitizer phrases and irrelevant evidence contamination.
- The next fix should not be a broad named-fact allowlist. It should add peer-evidence requirements and stronger Evidence Coverage Matrix failure modes for missing/contaminated task evidence.
