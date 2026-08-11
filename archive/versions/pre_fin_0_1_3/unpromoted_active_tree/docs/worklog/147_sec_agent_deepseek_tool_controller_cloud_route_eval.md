# 147 SEC Agent DeepSeek Tool Controller Cloud Route Eval

## Summary

- Date: 2026-05-22
- Task: Run the reviewed multi-turn tool-controller eval against real DeepSeek API tool calls on the cloud host.
- Status: completed; final guarded DeepSeek route-only run passed `18/18` tool checks and `18/18` argument checks.

## Context

The local controller loop had passed the reviewed 5-scenario/18-turn harness eval with the deterministic `heuristic` backend. This run tested whether DeepSeek `deepseek-v4-pro` can produce compatible OpenAI-style `tool_calls` for the same harness tools.

The run remained `route_only=true`, so it validated controller routing and normalized arguments without executing the expensive SEC memo DAG.

## Cloud Setup

- Remote repo path: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/miniconda3/bin/python`
- API model: DeepSeek `deepseek-v4-pro`
- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Final report on cloud: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_guarded_v2.json`
- Local copy: `reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_guarded_v2.json`

Secrets were injected only through the remote process environment for the immediate run and were not written to repo files, worklogs, or reports.

## Work Completed

Synced these runtime/eval files to the cloud host:

- `src/sec_agent/llm_gateway.py`
- `src/sec_agent/tool_harness.py`
- `src/sec_agent/tool_controller.py`
- `scripts/cloud/sec_agent_tool_harness.py`
- `scripts/cloud/sec_agent_tool_controller.py`
- `scripts/evaluate_sec_agent_tool_controller.py`
- `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`

Initial DeepSeek route-only result before controller guardrails:

- `turn_count=18`
- `tool_pass_count=16`
- `arg_pass_count=14`
- `failure_count=4`

Observed issues:

- DeepSeek rewrote a new-analysis `query` instead of preserving the exact user message.
- DeepSeek used free-form reformat descriptions instead of canonical `format` IDs.
- DeepSeek preferred `get_session_state` for one explicit coverage turn and one resume turn.
- One session-isolation turn showed why `user_id` must be owned by runtime context, not model-generated arguments.

Controller guardrails added in `src/sec_agent/tool_controller.py`:

- runtime `session_id`, `user_id`, and `tenant_id` override model-provided identity fields;
- artifact tool `answer_id` is filled from runtime `active_answer_id`;
- `start_memo_analysis.query` preserves the exact user message;
- state-confirmation turns are forced to `get_session_state`;
- clear coverage/resume/evidence/reformat turns can override a conservative model `get_session_state`;
- `reformat_answer.format` is canonicalized to stable IDs such as `pm_5_bullets` and `investment_committee_three_sections`;
- route-only and default dispatch force execute-capable tools to `execute=false` unless execution is explicitly enabled.

## Final Cloud Validation

Command family:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
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

Final result:

- `run_id=20260522_221705_tool_controller_reviewed_v1_deepseek`
- `scenario_count=5`
- `turn_count=18`
- `tool_pass_count=18`
- `arg_pass_count=18`
- `all_pass=true`
- `failure_count=0`

Secret pattern scans on the local and cloud report found `0` matches for private-token/password patterns.

## Current Boundaries

- This is a route-only tool-call eval. It does not validate real `inspect_coverage`, `explain_evidence`, or `resume_analysis` dispatch against fixture-backed artifacts.
- Full DAG execution remains opt-in through `execute_tools=True`; default controller dispatch keeps `execute=false`.
- `reformat_answer --execute` still records a request only and does not yet perform synthesis-only reformatting.
- Full30 memo-quality eval was not resumed in this run.

## Next Steps

1. Add fixture-backed completed and partial sessions for dispatch-level tests.
2. Test `inspect_coverage`, `explain_evidence`, and `resume_analysis` against real artifact refs without rerunning retrieval.
3. Add synthesis-only `reformat_answer --execute`.
4. Then resume full30 memo eval, context-management work, and pressure testing.
