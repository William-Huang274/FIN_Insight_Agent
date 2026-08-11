# 138 SEC Agent LangGraph State Orchestration POC

## Prompt
- User asked to introduce LangGraph for orchestration and state management because recoverability, observability, and future human-in-the-loop review can improve iteration efficiency.

## Decision
- Introduce LangGraph in a narrow orchestration role only.
- Do not replace the current retrieval, BGE rerank, runtime ledger, Evidence Coverage Matrix, Judgment Plan, claim verification, or deterministic gates.
- Current scope is Step 1 plus a minimal Step 2 POC:
  1. Make every interactive run write `sec_agent_state.json`.
  2. Add a LangGraph wrapper runner for one-shot `ask` execution.
  3. Defer checkpoint resume, coverage approval interrupts, and gate-fail repair branches.

## Work Completed
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - Each full `run_one()` now creates and incrementally writes `sec_agent_state.json`.
  - The state records selected tickers, selected years, model routes, output directory, stage records, and artifact refs.
  - Artifact refs include:
    - `query_contract`
    - `retrieved_context`
    - `runtime_exact_value_ledger`
    - `evidence_coverage_matrix`
    - `judgment_plan`
    - `memo_answer`
    - `claim_verification`
    - `deterministic_gates`
    - `rendered_answer`
  - Stage records include:
    - `plan_query`
    - `validate_query_contract`
    - `retrieve_context`
    - `rerank_context`
    - `build_runtime_ledger`
    - `build_coverage_matrix`
    - `build_judgment_plan`
    - `synthesize_memo`
    - `verify_claims`
    - `run_deterministic_gates`
    - `render_answer`
- Added `scripts/cloud/sec_agent_graph_runner.py`.
  - Uses LangGraph `StateGraph` when the dependency is installed.
  - Builds a two-node POC graph:
    - `run_interactive_pipeline`
    - `load_sec_agent_state`
  - Uses an in-memory checkpointer for the POC.
  - Forwards unknown flags to `sec_agent_interactive.py`.
  - Returns a compact JSON summary with the run root, state path, status, stage count, and artifact keys.
  - Adds `--state-smoke-dir` to validate LangGraph invoke + `sec_agent_state.json` write/read without running the full SEC pipeline.
  - Adds `--inspect-state --state-path <sec_agent_state.json>` to generate a resume-readiness report for an existing run.
- Updated `src/sec_agent/graph_nodes.py`.
  - Added `state_resume_report()`.
  - The report checks artifact existence and digest consistency.
  - It reports `ready_nodes`, `next_ready_node`, `blocked_nodes`, missing artifacts, and digest mismatches.
- Updated `scripts/cloud/sec_agent_interactive.sh`.
  - Added `graph-ask`.
  - Added `graph-ask-deepseek` / `graph-ask-api`.
  - Added `graph-inspect-state` for readiness inspection.
  - Added `graph-resume-state` for the first supported stage-level resume path.
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - Extracted the post-planner chain into `_run_from_planned_state()`.
  - Added `resume_from_state()` to continue an existing run from a saved `query_contract` / `case.jsonl`.
  - The first supported resume boundary is `next_ready_node=retrieve_context`, meaning the planner and query contract are reused and the run continues through retrieval, ledger, coverage, Judgment Plan, synthesis, gates, and rendering.
  - Split later stages into reusable helpers:
    - `_stage_retrieve_context`
    - `_stage_build_runtime_ledger`
    - `_stage_build_coverage_matrix`
    - `_stage_build_judgment_plan`
    - `_stage_synthesize_memo`
    - `_stage_run_deterministic_gates`
    - `_stage_render_answer`
  - `resume_from_state()` can now start from the first missing supported node instead of always restarting at retrieval.
- Updated `requirements.txt`.
  - Added `langgraph>=1.0.0`.

## Validation
- Installed and smoke-tested `langgraph==1.2.1` locally.
- Compile passed:

```powershell
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/cloud/sec_agent_graph_runner.py src/sec_agent/graph_state.py src/sec_agent/graph_nodes.py
```

- Graph compile smoke passed:
  - `CompiledStateGraph`
  - `graph_build=ok`
- State write smoke passed:
  - `sec_agent_state=ok`
  - `query_contract` and `plan_query` present in written JSON.
- Graph state smoke passed locally:
  - `status=completed`
  - `checkpoint_mode=in_memory`
  - `artifact_keys=["query_contract"]`
  - wrote `sec_agent_state.json` and `graph_runner_summary.json`.
- Without LangGraph installed, the graph runner fails clearly with an install message rather than falling through silently.
- Cloud validation on `/root/autodl-tmp/FIN_Insight_Agent` passed after syncing source files and installing `langgraph==1.2.1` into `/root/miniconda3`.
  - Compile passed for `sec_agent_interactive.py`, `sec_agent_graph_runner.py`, `graph_state.py`, and `graph_nodes.py`.
  - Graph compile smoke returned `CompiledStateGraph` and `cloud_graph_build=ok`.
  - Cloud state smoke artifact root: `/tmp/sec_agent_graph_cloud_smoke`.
  - Cloud state smoke returned `status=completed`, `checkpoint_mode=in_memory`, `artifact_keys=["query_contract"]`.
  - Cloud `sec_agent_state.json` contains `plan_query:completed`.
- Local resume inspect smoke passed:
  - `next_ready_node=retrieve_context`
  - missing artifacts: `retrieved_context`, `runtime_exact_value_ledger`, `evidence_coverage_matrix`, `judgment_plan`, `memo_answer`, `claim_verification`, `deterministic_gates`, `rendered_answer`
  - digest mismatch list is empty.
- Cloud resume inspect smoke passed:
  - artifact root: `/tmp/sec_agent_graph_resume_cloud`
  - `graph_resume_report.json` was written.
  - `next_ready_node=retrieve_context`
  - `blocked_nodes.build_runtime_ledger=["retrieved_context"]`
  - digest mismatch list is empty.
- Local no-op resume smoke passed for a complete synthetic state:
  - `next_ready_node=null`
  - `missing_artifacts=[]`
  - no stage rerun attempted.
- Local render-only resume smoke passed:
  - synthetic state had all artifacts except `rendered_answer`.
  - `next_ready_node=render_answer`.
  - resume added `rendered_answer` without triggering retrieval or model synthesis.
- Cloud no-op resume smoke passed for a complete synthetic state:
  - `status=completed`
  - `next_ready_node=null`
  - `missing_artifacts=[]`
  - `checkpoint_mode=in_memory`.
- Cloud render-only resume smoke passed:
  - artifact root: `/tmp/sec_agent_graph_render_cloud_smoke`
  - initial synthetic state omitted only `rendered_answer`.
  - `next_ready_node=render_answer`
  - `resume_action=executed`
  - `resumed_from_node=render_answer`
  - final artifact keys include `rendered_answer`.

## Current Limitations
- The LangGraph POC currently wraps the existing full interactive pipeline as one executable graph node and then loads `sec_agent_state.json`.
- Stage-level rerun/resume now supports the later node names in code, but expensive nodes such as `synthesize_memo` still require real API/local model availability and have only been syntax/smoke validated, not full-cost rerun validated.
- Coverage human approval is not implemented yet.
- Gate-fail repair branches are not implemented yet.
- This is intentionally a state/orchestration scaffold, not a change to SEC evidence quality logic.

## Next Steps
- Split the current full-pipeline wrapper into real LangGraph nodes once the state output is stable in cloud runs.
- Replace the in-memory checkpointer with a durable local checkpointer before claiming recoverability.
- Add an interrupt before synthesis when Evidence Coverage Matrix is partial or primary support is incomplete.
- Add a gate-fail branch that can rerun only claim verification/rendering when the failure is formatting/citation propagation rather than retrieval coverage.
