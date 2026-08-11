# 146 SEC Agent DeepSeek Tool Controller Loop v0

## Summary

- Date: 2026-05-22
- Task: Add a DeepSeek/OpenAI-compatible tool-call controller loop on top of the session-aware SEC agent harness.
- Status: v0 implemented and validated locally plus on cloud DeepSeek route-only evaluation.

## Context

The current memo chain is still the fixed SEC-only DAG behind `SecAgentToolHarness`. The next architecture step is not to let DeepSeek own retrieval, evidence validation, or gates. Instead, DeepSeek should choose high-level tool calls while the harness owns:

- session/user/tenant state;
- source boundary enforcement;
- artifact invalidation;
- graph execution and resume;
- no-rerun artifact reads;
- deterministic verification and gates.

This task adds the controller layer needed for that split.

## Work Completed

Added or updated:

- `src/sec_agent/llm_gateway.py`
  - Added optional `tools`, `tool_choice`, and `parallel_tool_calls` payload support.
  - Parsed `message`, `tool_calls`, and `finish_reason` from OpenAI-compatible chat responses while preserving existing content-only callers.
- `src/sec_agent/tool_controller.py`
  - Added `DeepSeekToolController` and `ControllerConfig`.
  - Added a controller system prompt with routing rules for `start_memo_analysis`, `revise_memo_scope`, `get_session_state`, `explain_evidence`, `inspect_coverage`, `reformat_answer`, and `resume_analysis`.
  - Added a dispatch loop that normalizes provider `tool_calls`, filters unsupported arguments against harness schemas, fills runtime IDs, and sends calls to `SecAgentToolHarness`.
  - Added `route_only` mode for tool-selection evaluation without dispatch.
  - Added default execution safety: when `execute_tools=False`, execute-capable tools are forced to `execute=False` before dispatch.
  - Added a deterministic `heuristic` backend for local smoke tests when no API key is present.
- `scripts/cloud/sec_agent_tool_controller.py`
  - CLI wrapper for one user turn through the controller.
- `scripts/evaluate_sec_agent_tool_controller.py`
  - Replays the reviewed multi-turn tool-harness cases and checks expected tool names plus expected argument subsets.

## Local Validation

Commands run:

```powershell
python -m py_compile src\sec_agent\llm_gateway.py src\sec_agent\tool_controller.py scripts\cloud\sec_agent_tool_controller.py scripts\evaluate_sec_agent_tool_controller.py
python scripts\cloud\sec_agent_tool_controller.py --controller-backend heuristic --route-only --message "<NVDA/AMD memo request>" --session-id s_tool_001 --user-id u_research_001 --tenant-id tenant_demo
python scripts\cloud\sec_agent_tool_controller.py --controller-backend heuristic --route-only --message "<second evidence follow-up>" --session-id s_tool_001 --user-id u_research_001 --active-answer-id ans_demo
python scripts\evaluate_sec_agent_tool_controller.py --controller-backend heuristic --route-only --output-path reports\quality\local_tool_controller_reviewed_v1_route_heuristic.json
python scripts\cloud\sec_agent_tool_controller.py --controller-backend heuristic --message "<NVDA 2024 memo request>" --session-id ctl_smoke_safe_dispatch_v2 --user-id smoke_user --tenant-id tenant_demo --max-steps 3
```

Results:

- `py_compile` passed.
- Route-only controller CLI selected `start_memo_analysis` for a new NVDA/AMD memo request.
- Route-only controller CLI selected `explain_evidence` for a second-driver evidence follow-up and did not hallucinate an evidence ID from the phrase `evidence id`.
- Reviewed multi-turn route-only eval passed:
  - `scenario_count=5`
  - `turn_count=18`
  - `tool_pass_count=18`
  - `arg_pass_count=18`
  - `failure_count=0`
  - report: `reports/quality/local_tool_controller_reviewed_v1_route_heuristic.json`
- Safe dispatch smoke selected `start_memo_analysis`, dispatched to the harness, and forced `execute=False`, producing a `planned` session instead of running the full DAG. Smoke session directories were deleted after validation.

## Current Boundaries

- DeepSeek API tool-call behavior is validated separately in `docs/worklog/147_sec_agent_deepseek_tool_controller_cloud_route_eval.md`; final cloud route-only run passed `18/18` tool and argument checks.
- The reviewed route-only eval supplies runtime `session_id`, `user_id`, and active-answer context from the fixture/runtime layer. In product use, the frontend/session registry must supply these identifiers; natural language alone is not enough to infer a hidden session ID such as `s_tool_004_b`.
- The eval validates routing and argument shape, not fixture-backed execution of completed/partial sessions.
- `reformat_answer` remains v0 request recording only; synthesis-only reformat execution is still pending.
- `inspect_coverage`, `explain_evidence`, and `resume_analysis` still need fixture-backed tests with real `session_state.json` and artifact refs.

## Next Steps

1. Add fixture-backed completed and partial session states so `inspect_coverage`, `explain_evidence`, and `resume_analysis` can be dispatch-tested without rerunning retrieval.
2. Add synthesis-only `reformat_answer --execute`.
3. After the controller/harness path is stable, resume full30 memo eval, context-management work, and pressure testing.
