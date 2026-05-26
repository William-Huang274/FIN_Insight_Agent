# Model Run: 20260522_sec_agent_tool_harness_dispatch_fixtures_v1

## Summary

- Purpose: Validate fixture-backed dispatch behavior for SEC agent harness tools.
- Status: completed.
- Run type: evaluation.
- Timestamp: 2026-05-22.
- Environment: local Windows workspace, `D:\FIN_Insight_Agent`.

## Code And Command

- Entry point: `scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`
- Command:

```powershell
python scripts\evaluate_sec_agent_tool_harness_dispatch_fixtures.py --output-path reports\quality\local_tool_harness_dispatch_fixtures_v1.json
```

- Static validation:

```powershell
python -m py_compile scripts\evaluate_sec_agent_tool_harness_dispatch_fixtures.py src\sec_agent\tool_harness.py src\sec_agent\graph_state.py src\sec_agent\graph_nodes.py
```

## Inputs

- Generated completed session fixture:
  - `session_state.json`
  - `sec_agent_state.json`
  - coverage matrix
  - exact-value ledger
  - Judgment Plan
  - memo answer output
  - downstream gate/render placeholders
- Generated partial session fixture:
  - `session_state.json`
  - `sec_agent_state.json`
  - query contract
  - retrieved context
  - exact-value ledger

## Outputs

- Report: `reports/quality/local_tool_harness_dispatch_fixtures_v1.json`
- Fixture runtime: `reports/quality/local_tool_harness_dispatch_fixture_runtime`

## Results

- `run_id=20260522_222734_tool_harness_dispatch_fixtures_v1`
- `case_count=5`
- `passed_count=5`
- `failed_count=0`
- `all_pass=true`

Case coverage:

- `inspect_coverage` read existing Evidence Coverage Matrix and returned `rerun_required=false`.
- `explain_evidence` read existing memo answer, ledger, and Judgment Plan, resolving the expected metric/evidence IDs.
- `resume_analysis` read partial graph state and reported `next_ready_node=build_coverage_matrix` with `execute=false`.
- `reformat_answer` recorded a request and invalidated only `rendered_answer`.
- `get_session_state` rejected a mismatched `user_id`.

## Efficiency

- No API calls, GPU work, retrieval, BGE rerank, ledger rebuild, synthesis, verification, gates, or graph execution were run.
- The harness used a sentinel Python executable in the fixture test to make accidental graph execution visible.

## Decision

- Decision label: proceed.
- The harness dispatch layer is ready for replay tests against one actual completed run and one actual partial/resume run.
- This result does not claim production multi-turn execution readiness yet because fixture data is generated and minimal.

## Safety Notes

- No secrets are required for this evaluation.
- Full graph execution remains outside this fixture dispatch test.
