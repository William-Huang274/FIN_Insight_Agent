# 144 SEC Agent Multi-Turn Tool Harness Eval Prompt

## Summary

- Date: 2026-05-22
- Task: Reassess whether the full30 memo candidate cases can evaluate the new harness/tool-call direction, and create a specialized prompt if not.
- Status: current full30 deemed insufficient for harness/controller evaluation; new prompt document created.

## Assessment

The current file:

- `eval_sets/sec_free_query_memo_quality_eval_full30_candidate_v1.jsonl`

is useful for single-turn memo content coverage and sector/ticker generalization. Static review found:

- `30` rows
- `30/30` primary ticker coverage
- `11` multi-primary cases
- `3` source-boundary cases

However, it does not contain:

- multi-turn `turns`;
- expected tool calls;
- session/user state expectations;
- artifact invalidation expectations;
- no-rerun inspection expectations;
- reformat-only expectations;
- interrupted/resume expectations;
- non-contiguous session isolation cases.

Therefore it should not be used as the primary eval for the DeepSeek controller loop or the session-aware tool harness.

## Work Completed

Created:

- `docs/eval/sec_agent_multiturn_tool_harness_case_generation_prompt.md`

The prompt asks GPT-5.5 to generate exactly 5 multi-turn scenarios, each with 3-5 turns, covering:

- continuous scope revision;
- no-rerun artifact inspection;
- reformat-only;
- non-contiguous session isolation;
- interrupted/resume;
- source-boundary behavior;
- expected tool sequence and rerun policy per turn.

## Decision

Keep the full30 memo candidate as a single-turn content/regression eval. Create a separate harness/controller eval set for multi-turn tool-call stability.

## Follow-Up

1. Use GPT-5.5 with `docs/eval/sec_agent_multiturn_tool_harness_case_generation_prompt.md`.
2. Save returned scenarios as `eval_sets/sec_agent_multiturn_tool_harness_eval_candidate_v1.json`.
3. Review expected tools, rerun policy, invalidation rules, and source-boundary fairness before implementing the controller loop eval runner.
