# SEC Agent Broad Non-Contiguous Follow-Up Route Eval

## Run Metadata
- Date: 2026-05-23
- Run ID: `20260523_sec_agent_noncontiguous_followup_deepseek_route_broad_v1`
- Type: tool-call controller route evaluation + harness fixture dispatch
- Model: DeepSeek `deepseek-v4-pro`
- Mode: route-only controller evaluation; no graph/DAG execution; no GPU workload
- Source policy: `SEC_ONLY_10K`

## Goal
- Broaden the non-contiguous follow-up suite beyond the initial 3-scenario smoke.
- Stress the current LangGraph + harness boundary for:
  - completed-session no-rerun evidence/coverage inspection;
  - cross-user and cross-session isolation;
  - explicit session switching and return-to-prior-session behavior;
  - source-boundary requests for latest/current/stock-price topics;
  - partial resume followed by reformat, evidence explanation, and state inspection.

## Eval Set
- File: `eval_sets/sec_agent_multiturn_noncontiguous_followup_eval_v1.json`
- Expanded from `3` scenarios / `11` turns to `6` scenarios / `23` turns.
- Scenario IDs:
  - `multiturn_tool_no_rerun_inspection_001`
  - `multiturn_tool_session_isolation_001`
  - `multiturn_tool_interrupted_resume_001`
  - `multiturn_tool_reformat_only_001`
  - `multiturn_tool_cross_session_return_boundary_001`
  - `multiturn_tool_resume_reformat_evidence_001`

## Harness Fixture Expansion
- Script: `scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`
- Added an alternate completed AMZN/META fixture session:
  - `fixture_dispatch_completed_alt`
  - `fixture_ans_amzn_meta_2025`
- Added direct harness checks for:
  - alternate session state read without MSFT/AAPL/NVDA leakage;
  - alternate coverage read without other-session leakage;
  - AMZN advertising claim-reference evidence resolution;
  - alternate wrong-user rejection.

## Results
- Local py_compile: passed.
- Local fixture dispatch:
  - Output: `reports/quality/local_tool_harness_dispatch_fixtures_broad_noncontiguous_v1.json`
  - Result: `11/11` passed.
- Local heuristic route:
  - Output: `reports/quality/local_tool_controller_noncontiguous_followup_route_heuristic_broad_v1.json`
  - Result: `6` scenarios / `23` turns, tool pass `23/23`, arg pass `23/23`.
- Cloud fixture dispatch:
  - Output: `reports/quality/cloud_tool_harness_dispatch_fixtures_broad_noncontiguous_v1.json`
  - Result: `11/11` passed.
- Cloud DeepSeek route-only:
  - Output: `reports/quality/cloud_tool_controller_noncontiguous_followup_route_deepseek_broad_v1.json`
  - Result: `6` scenarios / `23` turns, tool pass `23/23`, arg pass `23/23`, `all_pass=true`.
  - Controller status: `routed` for `23/23` turns; no fallback.

## Interpretation
- DeepSeek can route the wider non-contiguous suite through the current guarded controller interface.
- The harness fixture layer now has direct coverage for second-session state isolation and AMZN/META claim-reference evidence resolution.
- This run validates routing and fixture-backed dispatch, not final memo quality or end-to-end graph execution.

## Follow-Up
- Keep r4 real full-chain scope-revision run as the current latest end-to-end evidence.
- Next likely project gate is user/session context management beyond route-only fixtures, followed by targeted non-contiguous full-chain replay and then latency/pressure testing.

## Safety
- No API keys, cloud passwords, or temporary credentials are stored in this ledger.
