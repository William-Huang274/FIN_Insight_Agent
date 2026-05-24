# Model Run: 20260522_sec_agent_api_memo_v1_plan_alignment_allgreen

## Summary
- Purpose: Fix answer-vs-Judgment-Plan evidence alignment and rerun the 5-case API memo eval.
- Status: completed.
- Run type: cloud inference + deterministic replay + deterministic gates.
- Timestamp: 2026-05-22.
- Environment: cloud RTX 5090 32GB, `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command
- Main command:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash /tmp/run_sec_agent_5case_memo_eval.sh
```
- Changed files:
  - `scripts/build_sec_benchmark_judgment_plan.py`
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/cloud/sec_agent_interactive.sh`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `src/sec_agent/graph_state.py`
  - `src/sec_agent/graph_nodes.py`
- Secrets were not written to repo files.

## Inputs
- Eval set: `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`.
- Synthesis profile: `api_memo_v1`.
- Provider/model: DeepSeek `deepseek-v4-pro`.
- Source boundary: SEC 10-K evidence, years `2023,2024,2025`, `TICKERS=ALL`.
- BGE reranker device: CUDA.

## Outputs
- Official final run: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_200727/summary.json`.
- Intermediate deterministic support-ID replay: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_191918_plan_support_ids_replay/summary.json`.
- Intermediate deterministic plan-aligned replay: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_191918_plan_aligned_replay/summary.json`.

## Results
- Official final run:
  - `case_count=5`
  - `completed_count=5`
  - `all_gates_green_count=5`
  - `mean_memo_quality=0.8831200000000001`
  - `memo_quality_count=5`
  - `gate_failures=[]`

| Case | Pass Count | Failed Gates | Memo Quality | API Latency ms | Tokens | Elapsed sec |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| `memo_nvda_growth_competitors_001` | 12 | none | 0.896 | 81073 | 53404 | 252.1414 |
| `memo_amzn_aws_capex_002` | 12 | none | 0.8341 | 74509 | 60871 | 217.1026 |
| `memo_meta_ai_capex_rd_003` | 12 | none | 0.8665 | 81667 | 55661 | 233.7451 |
| `memo_jpm_rate_credit_004` | 12 | none | 0.92 | 80179 | 46909 | 239.4338 |
| `memo_lly_growth_quality_005` | 12 | none | 0.899 | 66420 | 53173 | 216.7953 |

## Experiment Governance
- Hypothesis: If Judgment Plan support IDs include every ledger source/object ID and memo-derived legacy drivers are plan-aligned, the 5-case memo eval should clear answer-vs-plan and semantic peer-bleed failures without adding allowlists.
- Decision target: at least `4/5` all-gates green.
- Result: `5/5` all-gates green.
- Decision label: proceed.
- Mainline decision: this 5-case result can replace the earlier diagnostic `0/5` run for the `api_memo_v1` stabilization step.

## Runtime Efficiency
- Per-case elapsed range: `216.7953` to `252.1414` sec.
- API latency range: `66420` to `81667` ms.
- Token range: `46909` to `60871`.
- Final cleanup: cloud `nvidia-smi` showed `0 MiB / 32607 MiB`; no SEC-agent or vLLM process remained.

## Caveats And Next Step
- This validates the 5-case memo eval, not production quality.
- The legacy `answered_qwen9b` status label is still used for DeepSeek outputs and should be renamed later.
- Next reasonable step is expanding validation or route-aware resume tests without changing the now-green plan-alignment contract.
