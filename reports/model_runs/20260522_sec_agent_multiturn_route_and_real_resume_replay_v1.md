# Model Run: 20260522_sec_agent_multiturn_route_and_real_resume_replay_v1

## Summary

- Purpose: Rerun GPT-generated multi-turn harness route eval and validate a real partial/resume replay.
- Status: completed.
- Run type: inference evaluation + resume replay.
- Timestamp: 2026-05-22.
- Environment: cloud host, `/root/autodl-tmp/FIN_Insight_Agent`, `/root/miniconda3/bin/python`.

## Code And Command

Route eval entry point:

- `scripts/evaluate_sec_agent_tool_controller.py`

Route eval command family:

```bash
DEEPSEEK_API_KEY=<runtime only> /root/miniconda3/bin/python scripts/evaluate_sec_agent_tool_controller.py \
  --controller-backend deepseek \
  --llm-backend deepseek \
  --base-url https://api.deepseek.com \
  --chat-completions-path /chat/completions \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --route-only \
  --max-steps 1 \
  --output-path reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_rerun_latest.json
```

Resume replay entry point:

- `scripts/cloud/sec_agent_tool_harness.py dispatch --tool resume_analysis`

Resume replay command family:

```bash
DEEPSEEK_API_KEY=<runtime only> SEC_AGENT_RESUME_USE_STATE_ROUTE=1 \
  /root/miniconda3/bin/python scripts/cloud/sec_agent_tool_harness.py \
  --session-root reports/quality/real_partial_resume_replay_session_harness \
  --python /root/miniconda3/bin/python \
  dispatch \
  --tool resume_analysis \
  --args-json '{"session_id":"real_partial_resume_synthesize_session","answer_id":"real_partial_resume_synthesize_answer","execute":true}'
```

Secrets were supplied only through the immediate process environment.

## Inputs

Route eval:

- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Scenarios: 5
- Turns: 18
- Model: DeepSeek `deepseek-v4-pro`

Resume replay:

- Source completed run: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_200800_60a9e00112`
- Replay run root: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/real_partial_resume_replay_synthesize_20260522`
- Deleted artifacts:
  - `runtime_evidence_pack.json`
  - `qwen/agent_outputs.jsonl`
  - `qwen/claim_verification.jsonl`
  - `post_gates/sec_benchmark_post_gates_summary.json`
  - `qwen/input_output.md`

## Outputs

- Route report: `reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_rerun_latest.json`
- Combined summary: `reports/quality/cloud_multiturn_route_and_real_resume_replay_20260522.json`
- Resume graph summary: `reports/quality/real_partial_resume_replay_synthesize_20260522/graph_runner_summary.json`
- Resume report: `reports/quality/real_partial_resume_replay_synthesize_20260522/graph_resume_report.json`
- Final replay state: `reports/quality/real_partial_resume_replay_synthesize_20260522/sec_agent_state.json`

## Results

Route eval:

- `run_id=20260522_223339_tool_controller_reviewed_v1_deepseek`
- `scenario_count=5`
- `turn_count=18`
- `tool_pass_count=18`
- `arg_pass_count=18`
- `all_pass=true`
- `failure_count=0`

Resume inspect before execution:

- `next_ready_node=synthesize_memo`
- Preserved complete artifacts:
  - `query_contract`
  - `retrieved_context`
  - `runtime_exact_value_ledger`
  - `evidence_coverage_matrix`
  - `judgment_plan`
- Missing downstream artifacts:
  - `evidence_pack`
  - `memo_answer`
  - `claim_verification`
  - `deterministic_gates`
  - `rendered_answer`

Resume execution:

- `resume_action=executed`
- `resumed_from_node=synthesize_memo`
- `elapsed_sec=82.5983`
- `final_status=completed`
- `final_missing_artifacts=[]`
- `final_digest_mismatch_artifacts=[]`
- Post-gates: `failed_gates=[]`, `qwen_answer_ratio=1.0`

Preserved upstream artifact digests after replay:

- `query_contract=4d540b1bdffd0e24`
- `retrieved_context=917402cfe318935b`
- `runtime_exact_value_ledger=94bf842bd8557383`
- `evidence_coverage_matrix=4e47be39f2a2b435`
- `judgment_plan=873a40b1df1ddae1`

## Efficiency

- Route eval wall time observed from SSH driver: about 57 sec for 18 turns.
- Resume replay elapsed time: 82.5983 sec.
- Resume replay did not rerun retrieval, BGE rerank, runtime ledger, coverage matrix, or Judgment Plan.

## Decision

- Decision label: proceed.
- Controller route stability and real `synthesize_memo` resume replay are both validated.
- Next execution-level risk is earlier-node resume from a real partial state, especially `build_coverage_matrix` or `build_judgment_plan`.

## Safety Notes

- Secret pattern scans on fetched reports found `0` matches.
- Full30 memo eval was not run.
