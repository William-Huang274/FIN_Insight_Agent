# 148 SEC Agent Tool Harness Fixture Dispatch Eval

## Summary

- Date: 2026-05-22
- Task: Add fixture-backed dispatch tests for the session-aware SEC agent tool harness.
- Status: completed; local fixture dispatch eval passed `5/5` cases.

## Context

The prior route-only evals proved that the controller can choose the right tool and normalize arguments. They did not prove that the harness tools read existing artifacts correctly or avoid graph reruns.

This task adds a dispatch-level eval that creates realistic completed and partial session fixtures, then calls `SecAgentToolHarness.dispatch()` directly.

## Work Completed

Added:

- `scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`

The script generates a fixture runtime under:

- `reports/quality/local_tool_harness_dispatch_fixture_runtime`

The completed fixture includes:

- `session_state.json`
- `sec_agent_state.json`
- `query_contract.json`
- `retrieved_context.jsonl`
- `runtime_exact_value_ledger.json`
- `runtime_evidence_coverage_matrix.json`
- `runtime_judgment_plan.json`
- `evidence_pack.json`
- `qwen/agent_outputs.jsonl`
- `claim_verification.json`
- `deterministic_gates.json`
- `rendered_answer.md`

The partial fixture includes:

- `session_state.json`
- `sec_agent_state.json`
- `query_contract.json`
- `retrieved_context.jsonl`
- `runtime_exact_value_ledger.json`

The harness is constructed with a sentinel Python executable (`__sec_agent_fixture_should_not_execute__`) so the fixture test would expose accidental execution attempts in execute-enabled paths. The tested calls use no-rerun or `execute=false` modes.

## Local Validation

Commands run:

```powershell
python -m py_compile scripts\evaluate_sec_agent_tool_harness_dispatch_fixtures.py src\sec_agent\tool_harness.py src\sec_agent\graph_state.py src\sec_agent\graph_nodes.py
python scripts\evaluate_sec_agent_tool_harness_dispatch_fixtures.py --output-path reports\quality\local_tool_harness_dispatch_fixtures_v1.json
```

Result:

- Report: `reports/quality/local_tool_harness_dispatch_fixtures_v1.json`
- `case_count=5`
- `passed_count=5`
- `failed_count=0`
- `all_pass=true`

Passed cases:

- `inspect_coverage_reads_existing_matrix`
  - Reads existing `runtime_evidence_coverage_matrix.json`.
  - Returns `rerun_required=false`.
  - Records exactly one session turn.
- `explain_evidence_reads_answer_ledger_and_plan`
  - Reads prior `qwen/agent_outputs.jsonl`, `runtime_exact_value_ledger.json`, and `runtime_judgment_plan.json`.
  - Resolves `fixture_msft_cloud_revenue_2025` and `fixture_ev_msft_cloud_2025`.
  - Returns one ledger match and one Judgment Plan match.
- `resume_analysis_reports_first_missing_node_without_execute`
  - Reads partial `sec_agent_state.json`.
  - Reports `next_ready_node=build_coverage_matrix`.
  - Preserves `query_contract`, `retrieved_context`, and `runtime_exact_value_ledger`.
  - Does not spawn graph runner because `execute=false`.
- `reformat_answer_records_request_only`
  - Records a reformat request.
  - Invalidates only `rendered_answer`.
  - Keeps `execute_supported=false` for v0.
- `get_session_state_enforces_user_boundary`
  - Rejects wrong `user_id`.
  - Does not append a session turn on failed state read.

## Current Boundaries

- These are generated fixtures, not replayed production run artifacts.
- The test validates harness dispatch and artifact-read contracts, not DeepSeek routing; DeepSeek routing is covered by the prior route-only eval.
- `resume_analysis execute=true` is not tested here because it would intentionally enter graph execution.
- `reformat_answer --execute` is still not implemented; v0 only records the request.

## Next Steps

1. Add one fixture/replay case from an actual completed `api_memo_v1` cloud run.
2. Add one partial-state replay case from a real interrupted/resume run.
3. Implement `reformat_answer --execute` as synthesis-only rendering once artifact-read contracts remain stable.
4. Resume full30 memo eval after controller/harness dispatch contracts are stable.
