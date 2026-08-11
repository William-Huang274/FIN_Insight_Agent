# Model Run: 20260602_fin_agent_full17_unrun_first_deepseek_v0_1

## Summary

- Purpose: 真实 DeepSeek full-chain 17-case 回归，优先运行此前未覆盖 case。
- Status: failed diagnostic; do not merge/mainline from this run.
- Run type: inference / full-chain evaluation.
- Timestamp: 2026-06-02 Asia/Shanghai.
- Environment: local Windows, DeepSeek API backend, real evidence operators, local BGE CUDA reranker.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Ordered cases file: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/_ordered_cases/20260602_fin_agent_full17_unrun_first_cases_v0_1.jsonl`
- Command:
  - `python scripts/eval_multi_agent_real_llm_chain.py --cases-path eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/_ordered_cases/20260602_fin_agent_full17_unrun_first_cases_v0_1.jsonl --run-id 20260602_fin_agent_full17_unrun_first_real_retrieval_v0_1 --real-evidence-operators --strict`
- Config: real retrieval enabled; BGE device auto; local ledger store default.
- Git commit / dirty files: dirty working tree with ongoing multi-agent quality work.
- Seeds: not applicable.

## Inputs

- Fixture source: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- Ordered run scope: 17 cases, with 7 previously unpassed/unrun fixture cases first.
- Data boundary: local SEC / 8-K / market snapshot / industry snapshot / relationship graph only.
- Leakage guard: API key and raw LLM responses not saved.

## Results

- Gate status: `fail`
- Case count: `17`
- Passed: `8`
- Failed: `9`
- Pass rate: `0.470588`
- Total tool calls: `91`
- Wall time: `3,192,528 ms`

### Category Results

| Category | Cases | Passed | Failed |
| --- | ---: | ---: | ---: |
| `standard_memo` | 5 | 5 | 0 |
| `focused_answer` | 2 | 2 | 0 |
| `sector_depth` | 4 | 0 | 4 |
| `multi_turn` | 4 | 1 | 3 |
| `exact_lookup` | 2 | 0 | 2 |

### Failed Cases

| Case | Failure |
| --- | --- |
| `fin_full_sector_ai_infra_depth_zh` | `specialists.real_evidence_quality_pass=false`; Risk Specialist temporal ref-depth. |
| `fin_full_sector_banking_depth_zh` | Fundamental temporal ref-depth. |
| `fin_full_sector_healthcare_depth_zh` | Fundamental temporal ref-depth. |
| `fin_full_sector_utilities_power_depth_zh` | tool budget exhausted + Risk temporal ref-depth. |
| `fin_full_mt_banking_t2` | missing expected `market_operator` / `market_get_snapshot`. |
| `fin_full_exact_msft_capex_zh` | deterministic lookup gate expects SEC search/BGE; selector chose weak capex rows. |
| `fin_full_exact_jpm_credit_provision_zh` | deterministic lookup gate expects SEC search/BGE; selector chose change-rate rows. |
| `fin_full_mt_semis_scope_t1` | forbidden `risk_counterevidence_analyst` activated. |
| `fin_full_mt_semis_scope_t2` | tool budget exhausted. |

## Runtime Efficiency

- Longest cases:
  - WMT/TGT standard: `394.3s`
  - Utilities sector-depth: `344.5s`
  - Semis T2: `326.3s`
  - Healthcare sector-depth: `320.5s`
  - English MSFT/GOOGL: `306.6s`
- Output quality flags:
  - `high_total_token_cost=5`
  - `low_claim_card_token_efficiency=2`
  - `low_memo_chars_per_token=7`
  - `memo_surface_says_evidence_thin=9`
  - `memo_writer_retry_cost_present=1`

## Interpretation

- Standard and focused paths are stable enough for continued iteration: `7/7` combined pass.
- Sector-depth route activation and retrieval run, but Specialist real-evidence quality gate is too brittle for one-row YoY/prior-period disclosure evidence.
- Exact lookup needs its own eval contract and selector fix; requiring `sec_search_filings/BGE` for deterministic lookup defeats the exact fast path.
- Multi-turn context inheritance remains under-specified: T2 agent/tool expectations do not reliably follow user intent and prior turn state.

## Governance

- Hypothesis: the 17-case run should reveal whether the current optimized chain is ready for merge/mainline.
- Decision target: broad pass with stable standard/focused/sector-depth/multi-turn/exact paths.
- Result: failed diagnostic.
- Decision label: stop full regression; fix failure clusters first.
- Mainline decision: do not merge based on this run.

## Next Step

Run targeted repair and rerun only failed subsets:

1. exact lookup 2 cases;
2. sector-depth 4 cases;
3. multi-turn 3 cases.

Do not rerun all 17 until these clusters pass.
