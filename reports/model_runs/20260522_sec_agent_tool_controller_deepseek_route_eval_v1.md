# Model Run: 20260522_sec_agent_tool_controller_deepseek_route_eval_v1

## Summary

- Purpose: Validate DeepSeek API tool-call routing against the reviewed SEC agent multi-turn harness eval.
- Status: completed.
- Run type: inference evaluation.
- Timestamp: 2026-05-22.
- Environment: cloud host, `/root/autodl-tmp/FIN_Insight_Agent`, `/root/miniconda3/bin/python`.

## Code And Command

- Entry point: `scripts/evaluate_sec_agent_tool_controller.py`
- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Controller backend: `deepseek`
- Model: `deepseek-v4-pro`
- Mode: `route_only=true`, `execute_tools=false`, `max_steps=1`
- Command family:

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
  --output-path reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_guarded_v2.json
```

Secrets were supplied only through the immediate process environment and were not written to files or reports.

## Inputs

- Eval contract: `sec_agent_multiturn_tool_harness_eval_v0.1`
- Scenarios: 5
- Turns: 18
- Tool set:
  - `start_memo_analysis`
  - `revise_memo_scope`
  - `get_session_state`
  - `inspect_coverage`
  - `explain_evidence`
  - `reformat_answer`
  - `resume_analysis`

## Outputs

- Cloud report: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_guarded_v2.json`
- Local report copy: `reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_guarded_v2.json`

## Results

Final guarded run:

- `run_id=20260522_221705_tool_controller_reviewed_v1_deepseek`
- `scenario_count=5`
- `turn_count=18`
- `tool_pass_count=18`
- `arg_pass_count=18`
- `all_pass=true`
- `failure_count=0`

Initial unguarded run was diagnostic-only and failed 4 checks:

- DeepSeek rewrote a user query.
- DeepSeek emitted free-form reformat descriptions instead of canonical format IDs.
- DeepSeek used `get_session_state` for one coverage turn and one resume turn.
- A session-isolation turn confirmed that runtime identity must override model-provided identity fields.

The final run passed after deterministic controller guardrails were added.

## Efficiency

- Final DeepSeek route-only wall time observed from the local SSH driver: about 58 seconds for 18 turns.
- No GPU work or full SEC memo DAG execution occurred.
- No retrieval, BGE rerank, ledger, synthesis, verification, or gates were run by this eval.

## Decision

- Decision label: proceed.
- The route-only DeepSeek tool-call path is now good enough for fixture-backed dispatch tests.
- This result does not promote full multi-turn product behavior yet because completed/partial session artifact fixtures still need execution-level validation.

## Safety Notes

- Secret pattern scans on the local and cloud route reports found `0` matches for private-token/password patterns.
- Full DAG execution remains guarded by explicit `execute_tools=True`; default dispatch forces execute-capable tools to `execute=false`.
