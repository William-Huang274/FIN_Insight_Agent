# SEC Agent API Memo v1 5-Case Rerun And Resume Validation

## Summary
- Date: 2026-05-22.
- Cloud path: `/root/autodl-tmp/FIN_Insight_Agent`.
- Local path: `D:\FIN_Insight_Agent`.
- Run type: cloud 5-case API memo eval plus graph resume validation.
- Status: diagnostic-only.
- Secrets: credentials and API key were used only at runtime and were not written to repo files.

## Pre-Run Guard
- Confirmed from prior handoff that cloud had no active 5-case memo eval.
- A new run was started from `/tmp/run_sec_agent_5case_memo_eval.sh`.
- First attempt `reports/quality/20260522_api_memo_v1_5case_190623` exposed a state-schema bug:
  - `ValueError: unknown artifact key: evidence_pack`
  - Cause: synthesis wrote `runtime_evidence_pack.json` to graph state, but `SecAgentState.ARTIFACT_KEYS` did not include `evidence_pack`.
- The failing run was stopped before it finished all 5 cases. Only the SEC-agent eval processes were killed; unrelated GPU processes were not touched.

## Hotfix
Changed files:
- `src/sec_agent/graph_state.py`
- `src/sec_agent/graph_nodes.py`

Implemented behavior:
- Added `evidence_pack` to `ARTIFACT_KEYS`.
- Declared `synthesize_memo` outputs as `("evidence_pack", "memo_answer")`.

Validation:
- Local `python -m py_compile src/sec_agent/graph_state.py src/sec_agent/graph_nodes.py` passed.
- Local smoke accepted `state.with_artifact("evidence_pack", ...)`.
- Cloud `py_compile` and graph-state smoke passed after syncing both files.

## 5-Case Memo Eval
Command shape:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash /tmp/run_sec_agent_5case_memo_eval.sh
```

Official rerun:
- Quality summary: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_191918/summary.json`
- Completed count: `5/5`
- All-gates green count: `0/5`
- Mean memo quality: `0.8657`
- Memo quality count: `5/5`

Case results:
- `memo_nvda_growth_competitors_001`: pass_count `10`, failed `v2_semantic_contract_gate_pass`, `answer_vs_judgment_plan_gate_pass`, memo quality `0.923`, total tokens `63894`, API latency `77362 ms`, elapsed `237.2955 sec`.
- `memo_amzn_aws_capex_002`: pass_count `11`, failed `answer_vs_judgment_plan_gate_pass`, memo quality `0.7861`, total tokens `45979`, API latency `67291 ms`, elapsed `211.4543 sec`.
- `memo_meta_ai_capex_rd_003`: pass_count `11`, failed `answer_vs_judgment_plan_gate_pass`, memo quality `0.898`, total tokens `58717`, API latency `72045 ms`, elapsed `230.4841 sec`.
- `memo_jpm_rate_credit_004`: pass_count `11`, failed `answer_vs_judgment_plan_gate_pass`, memo quality `0.92`, total tokens `48319`, API latency `71679 ms`, elapsed `212.8891 sec`.
- `memo_lly_growth_quality_005`: pass_count `11`, failed `answer_vs_judgment_plan_gate_pass`, memo quality `0.8014`, total tokens `59645`, API latency `55136 ms`, elapsed `201.64 sec`.

Interpretation:
- The previous AMZN/META/JPM `named_fact_gate_pass` failures are no longer present.
- The main remaining blocker shifted to `answer_vs_judgment_plan_gate_pass`, specifically answer evidence IDs not matching the corresponding Judgment Plan driver/support IDs.
- NVDA also still fails `v2_semantic_contract_gate_pass`.
- This does not meet the expected target of at least `4/5` all-gates green, so the run remains diagnostic-only.

## Resume Precision Test
Artifact used:
- `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_193116_914dee0e50`

Before deletion:
- `graph-inspect-state` returned `next_ready_node=null`.
- State contained `evidence_pack`, `memo_answer`, `claim_verification`, `deterministic_gates`, and `rendered_answer`.

Deleted only:
- `qwen/agent_outputs.jsonl`
- `qwen/claim_verification.jsonl`
- `qwen/scores.jsonl`
- `qwen/raw_model_outputs.jsonl`
- `qwen/run_summary.json`
- `qwen/input_output.md`
- `post_gates/sec_benchmark_post_gates_summary.json`

After deletion:
- `graph-inspect-state` returned `next_ready_node="synthesize_memo"`.
- Missing artifacts were only `memo_answer`, `claim_verification`, `deterministic_gates`, and `rendered_answer`.
- Retrieval/BGE/ledger/coverage/Judgment Plan artifacts stayed present and digest-clean.

Resume result:
- `graph-resume-state` resumed from `synthesize_memo`.
- Console output started at `[5/6]` synthesis and then `[6/6]` deterministic gates.
- It did not rerun retrieval/BGE/ledger/coverage/Judgment Plan.
- Recreated:
  - `qwen/run_summary.json`
  - `qwen/agent_outputs.jsonl`
  - `qwen/claim_verification.jsonl`
  - `qwen/input_output.md`
  - `post_gates/sec_benchmark_post_gates_summary.json`
- Final inspect returned `next_ready_node=null` and no missing artifacts.

Important caveat:
- The current `graph-resume-state` command resumed synthesis through the local Qwen vLLM route, not the DeepSeek API route used by the 5-case eval. This still validates node precision, but provider-route preservation should be reviewed before using resume for exact API-output reproduction.

Cleanup:
- The Qwen vLLM server started by the resume test was stopped.
- Final `nvidia-smi` showed `0 MiB / 32607 MiB` and no running GPU processes.

## Next Work
- Fix `answer_vs_judgment_plan_gate_pass` by aligning answer evidence IDs with matched Judgment Plan drivers/support evidence, not by relaxing the gate.
- Investigate the NVDA `v2_semantic_contract_gate_pass` failure separately.
- Decide whether `graph-resume-state` should preserve the original synthesis provider/model route from state metadata.
