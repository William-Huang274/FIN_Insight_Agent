# 145 SEC Agent Multi-Turn Tool Harness Eval Review

## Summary

- Date: 2026-05-22
- Task: Review GPT-generated multi-turn tool harness eval scenarios and normalize them for the current v0 harness schema.
- Status: reviewed eval file created and validated.

## Inputs

User-provided candidate files:

- `D:\downloads\sec_agent_multiturn_tool_harness_eval_candidate_v1.json`
- `D:\downloads\sec_agent_multiturn_tool_harness_eval_candidate_v1.md`

## Assessment

The candidate is directionally strong for the new harness/controller goal:

- `5` scenarios
- each scenario has `3-5` turns
- categories covered:
  - continuous scope revision
  - no-rerun artifact inspection
  - reformat-only
  - session isolation
  - interrupted resume
- expected tools covered:
  - `start_memo_analysis`: `1`
  - `revise_memo_scope`: `1`
  - `inspect_coverage`: `4`
  - `explain_evidence`: `4`
  - `get_session_state`: `5`
  - `reformat_answer`: `2`
  - `resume_analysis`: `1`

The main issue was schema drift: GPT included semantic helper fields inside `expected_arguments`, such as:

- `tickers`
- `peer_scope`
- `active_answer_id`
- `claim_reference`
- `focus_tickers`
- `focus_metric_families`
- `requested_topics`
- `preserve_evidence_ids`
- `tone`
- `sections`

Those are useful scenario expectations, but they are not accepted v0 harness tool parameters.

## Work Completed

Created:

- `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`

Normalization policy:

- `expected_arguments` now contains only parameters supported by the current v0 harness tools.
- Original GPT arguments are preserved as `expected_arguments_raw`.
- Semantic helper fields are preserved as `expected_context`.
- Scenario purpose, turn messages, rerun policy, invalidation expectations, success criteria, and failure modes are preserved.

## Validation

Programmatic validation passed:

- scenario count: `5`
- categories: all required categories present
- unsupported tool args after normalization: `0`
- raw argument preservation: `18` turns
- expected tool coverage:
  - `start_memo_analysis`: `1`
  - `revise_memo_scope`: `1`
  - `inspect_coverage`: `4`
  - `explain_evidence`: `4`
  - `get_session_state`: `5`
  - `reformat_answer`: `2`
  - `resume_analysis`: `1`

## Decision

Use `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json` as the controller/harness eval seed. Keep the original GPT files as external candidate inputs, not mainline repo artifacts.

## Follow-Up

1. Implement the DeepSeek controller loop against `SecAgentToolHarness.tool_specs()`.
2. Add an eval runner that replays `reviewed_v1` turns in dry-run mode first.
3. Add fixture support for `completed_analysis` and `partial_analysis` scenarios.
4. Extend the harness only where repeated real eval failures show the v0 tool schema is too narrow.
