# Model Run: 20260522_sec_agent_api_memo_v1_5case_graph_state_resume_validation

## Summary
- Purpose: Rerun the 5-case `api_memo_v1` memo eval after planner/coverage/named-fact fixes and validate graph resume precision from `synthesize_memo`.
- Status: diagnostic-only.
- Run type: inference + evaluation + resume smoke.
- Timestamp: 2026-05-22.
- Environment: cloud RTX 5090 32GB at `/root/autodl-tmp/FIN_Insight_Agent`; local repo at `D:\FIN_Insight_Agent`.

## Code And Command
- Entry point: `/tmp/run_sec_agent_5case_memo_eval.sh`.
- Command:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash /tmp/run_sec_agent_5case_memo_eval.sh
```
- Hotfix before official rerun:
  - `src/sec_agent/graph_state.py`: added `evidence_pack` to graph artifact keys.
  - `src/sec_agent/graph_nodes.py`: declared `synthesize_memo` outputs as `("evidence_pack", "memo_answer")`.
- Validation:
  - Local `py_compile` passed for `graph_state.py` and `graph_nodes.py`.
  - Local and cloud graph-state smoke accepted `evidence_pack`.
- Secrets: runtime-only; not recorded in repo files.

## Inputs
- Eval set: `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`.
- Synthesis profile: `api_memo_v1`.
- Retrieval/gate scope: `TICKERS=ALL`, `YEARS=2023,2024,2025`, SEC-only source boundary.
- BGE device: `cuda`.
- Planner: LLM planner through interactive SEC agent runner.

## Outputs
- Failed pre-hotfix attempt: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_190623`.
- Official rerun summary: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_191918/summary.json`.
- Resume-test artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_193116_914dee0e50`.

## Results
- Completed count: `5/5`.
- All-gates green count: `0/5`.
- Mean memo quality: `0.8657`.
- Previous named-fact failures on AMZN/META/JPM did not recur.
- Gate failures:
  - NVDA: `v2_semantic_contract_gate_pass`, `answer_vs_judgment_plan_gate_pass`.
  - AMZN, META, JPM, LLY: `answer_vs_judgment_plan_gate_pass`.

Case metrics:

| Case | Pass Count | Failed Gates | Memo Quality | API Latency ms | Tokens | Elapsed sec |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| `memo_nvda_growth_competitors_001` | 10 | `v2_semantic_contract_gate_pass`, `answer_vs_judgment_plan_gate_pass` | 0.923 | 77362 | 63894 | 237.2955 |
| `memo_amzn_aws_capex_002` | 11 | `answer_vs_judgment_plan_gate_pass` | 0.7861 | 67291 | 45979 | 211.4543 |
| `memo_meta_ai_capex_rd_003` | 11 | `answer_vs_judgment_plan_gate_pass` | 0.898 | 72045 | 58717 | 230.4841 |
| `memo_jpm_rate_credit_004` | 11 | `answer_vs_judgment_plan_gate_pass` | 0.92 | 71679 | 48319 | 212.8891 |
| `memo_lly_growth_quality_005` | 11 | `answer_vs_judgment_plan_gate_pass` | 0.8014 | 55136 | 59645 | 201.64 |

## Resume Validation
- Artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_193116_914dee0e50`.
- Before deletion: `next_ready_node=null`.
- Deleted memo/gate/render artifacts only.
- After deletion: `next_ready_node="synthesize_memo"`; missing artifacts were `memo_answer`, `claim_verification`, `deterministic_gates`, and `rendered_answer`.
- Resume command:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash scripts/cloud/sec_agent_interactive.sh graph-resume-state \
  /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_193116_914dee0e50/sec_agent_state.json
```
- Resume behavior: started at `[5/6]` synthesis and then `[6/6]` gates; did not rerun retrieval/BGE/ledger/coverage/Judgment Plan.
- Recreated `qwen/run_summary.json`, `qwen/agent_outputs.jsonl`, `qwen/claim_verification.jsonl`, `qwen/input_output.md`, and `post_gates/sec_benchmark_post_gates_summary.json`.
- Final inspect: `next_ready_node=null`, no missing artifacts.
- Caveat: current `graph-resume-state` used local Qwen vLLM synthesis rather than preserving the original DeepSeek API route. Node precision is validated; provider-route fidelity remains open.

## Experiment Governance
- Hypothesis: Evidence-ID propagation plus coverage-prioritized Evidence Pack selection should clear prior named-fact failures and improve 5-case all-gates green count.
- Decision target: at least `4/5` all-gates green on `sec_free_query_memo_quality_eval_v1`.
- Result: target not met; all-gates green `0/5`.
- Mainline decision: diagnostic-only.
- Stop condition hit: do not expand ontology/cases until answer-vs-Judgment-Plan evidence alignment is fixed.

## Runtime Efficiency
- 5-case wall-clock window: 2026-05-22 19:19:17 to 19:37:59 Asia/Shanghai.
- Per-case elapsed range: `201.64` to `237.2955` sec.
- API latency range: `55136` to `77362` ms.
- Token range: `45979` to `63894`.
- Resume wall time: about `195.26` sec.
- Cleanup: Qwen vLLM process started by resume was stopped; final `nvidia-smi` showed `0 MiB / 32607 MiB` and no GPU processes.

## Caveats And Next Step
- Not production quality: all-gates green target failed.
- Main failure is no longer named facts; it is answer evidence IDs not matching the Judgment Plan driver/support IDs.
- Review `answer_vs_judgment_plan_gate` failure details before changing prompts or renderer logic.
- Decide whether graph resume should preserve the original provider/model route or require an explicit override.
