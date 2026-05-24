# 143 SEC Agent Tool Harness v0

## Summary

- Date: 2026-05-22
- Task: Add an executable harness/tool framework for future DeepSeek tool-call orchestration.
- Status: v0 framework implemented and locally smoke-tested.

## Context

The current SEC memo agent is a stable fixed DAG:

1. Query Contract planner
2. SEC retrieval / BM25 / ObjectBM25 / BGE rerank
3. Runtime Exact-Value Ledger
4. Evidence Coverage Matrix
5. Judgment Plan
6. DeepSeek `api_memo_v1` synthesis
7. claim-first verification
8. deterministic gates
9. rendering and `sec_agent_state.json`

This works for one-shot analysis and graph resume, but it is not yet an enterprise-style multi-turn agent harness. The next direction is to let DeepSeek choose high-level tool calls while our code keeps ownership of state, permissions, artifact validity, deterministic gates, and execution.

## Work Completed

Added:

- `src/sec_agent/tool_harness.py`
- `scripts/cloud/sec_agent_tool_harness.py`

The harness exposes DeepSeek/OpenAI-compatible function tool specs for:

- `start_memo_analysis`
- `revise_memo_scope`
- `explain_evidence`
- `inspect_coverage`
- `reformat_answer`
- `resume_analysis`
- `get_session_state`

The v0 harness supports:

- session state under `eval/sec_cases/session_harness/<session_id>/session_state.json`;
- user/session/preferences state;
- active query and active answer tracking;
- artifact refs copied from `sec_agent_state.json` when execution is enabled;
- high-level tool dispatch by name plus JSON arguments;
- `revise_memo_scope` invalidation rules for scope changes;
- `explain_evidence` and `inspect_coverage` as no-rerun artifact inspection tools;
- `reformat_answer` request recording with only `rendered_answer` invalidated;
- `resume_analysis` inspection of `state_resume_report` and optional graph resume execution.

This keeps the current fixed DAG intact. DeepSeek will be able to choose tools, but the harness still executes tools, validates state, and preserves deterministic gates.

## Local Validation

Commands run:

```powershell
python -m py_compile src\sec_agent\tool_harness.py scripts\cloud\sec_agent_tool_harness.py
python scripts\cloud\sec_agent_tool_harness.py list-tools
python scripts\cloud\sec_agent_tool_harness.py dispatch --tool start_memo_analysis --args-json "{...}"
python scripts\cloud\sec_agent_tool_harness.py revise-memo-scope --session-id smoke_session_harness_v0b --add-tickers AMD --years 2024,2025
```

Results:

- `py_compile` passed.
- `list-tools` returned 7 tool specs.
- Dry-run `start_memo_analysis` created a planned session.
- `revise_memo_scope` preserved inferred `NVDA`, added `AMD`, set years to `2024,2025`, and marked analysis artifacts invalid.
- Smoke session artifacts were deleted after validation.

## Current Boundaries

- `start_memo_analysis --execute` wraps the existing graph runner; no new DAG behavior is introduced.
- `reformat_answer` records a request but does not yet perform synthesis-only reformat execution.
- There is no DeepSeek controller loop yet; the framework provides schemas and dispatch for that next step.
- `explain_evidence` and `inspect_coverage` require an executed analysis with artifact refs.

## Next Steps

1. Add a DeepSeek controller loop that sends `tool_specs()` to `/chat/completions` and dispatches returned tool calls.
2. Add synthesis-only `reformat_answer --execute` using existing memo answer + evidence refs.
3. Add a small multi-turn demo:
   - start NVDA memo;
   - add AMD and restrict years;
   - inspect coverage;
   - explain one evidence driver;
   - reformat as PM bullets.
4. Add harness tests around session state, invalidation matrix, and no-rerun artifact tools.
