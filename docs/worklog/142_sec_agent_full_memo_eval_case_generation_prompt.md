# 142 SEC Agent Full Memo Eval Case Generation Prompt

## Summary

- Date: 2026-05-22
- Task: Prepare a reusable prompt document for generating the next `full30` memo-quality eval cases.
- Status: prompt document created; no eval cases generated or run in this step.

## Current State

The project currently has a formal 5-case memo eval set at:

- `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`

The latest cloud `api_memo_v1` run passed those 5 cases:

- `5/5` all-gates green
- `12/12` gates per case
- `mean_memo_quality=0.88312`

There is not yet a reviewed `full30` memo eval set. The existing full30 work was for constrained free-query/planner-style evaluation, not the current memo-quality schema.

## Work Completed

Created a self-contained GPT-5.5 prompt document:

- `docs/eval/sec_agent_full_memo_eval_case_generation_prompt.md`

The prompt asks for 25 additional cases to append to the current 5-case memo eval, producing a `full30` candidate set. It records:

- current pipeline state;
- recent gate fixes to stress-test;
- allowed 30-company, 2023-2025, 10-K-only universe;
- current JSONL schema;
- required coverage distribution;
- risk themes to test;
- output and self-check requirements.

## Decision

The next full memo eval should preserve the existing 5 all-green cases and generate 25 new candidate cases, then manually review them before promoting them to a mainline eval set.

## Follow-Up

1. Use GPT-5.5 with `docs/eval/sec_agent_full_memo_eval_case_generation_prompt.md`.
2. Save the generated JSONL as a candidate file, not a mainline eval file.
3. Human-review the candidate cases for source-boundary fairness, ticker validity, duplicate topics, and scorer brittleness.
4. Promote only reviewed cases to a `full30` memo eval JSONL.
