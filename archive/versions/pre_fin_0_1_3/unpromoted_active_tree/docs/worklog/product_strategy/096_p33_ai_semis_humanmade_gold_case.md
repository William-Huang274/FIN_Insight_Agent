# 096 - P33 AI/Semis Humanmade Gold Case

Date: 2026-07-06

Status: `humanmade_gold_case_v0_1_documented_no_paid_run_superseded_by_polished_memo_v0_2`

Current follow-up: `097_p33_ai_semis_humanmade_gold_memo_v0_2.md` upgrades the polished memo surface from v0.1 to v0.2. This entry remains the historical record for creating the original humanmade gold case and source ledger.

## Trigger

The user clarified that P33 should not continue from engineering gates into paid Memo Writer or model comparison. The next step must first create a humanmade gold case: a human analyst workflow and workpaper built from public sources, then use it to reverse-engineer Research Lead, specialist, JudgmentCard, ProductIntelligenceGraph, MemoLogicPlan, writer, verifier, and Workbench requirements.

This is a product-quality correction. It addresses the prior failure mode where runtime nodes could pass engineering contracts while still producing thin research judgment.

## What Changed

Added:

- `docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md`

Updated:

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
- `docs/worklog/README.md`

## Humanmade Gold Scope

The gold case focuses on:

```text
AI workload / hyperscaler capex
 -> accelerator product capability / supply
 -> cloud/OEM/customer deployment
 -> server OEM revenue quality / margin bridge
 -> foundry / packaging / HBM / semicap read-through
 -> market expectation / price-in
 -> counter-thesis and what-would-change
```

The case uses source-backed public evidence for Dell, NVIDIA, AMD, Google, Microsoft, Amazon, Alphabet, Meta, TSMC, ASML, AMAT, LRCX, and MLCommons.

## Output

The humanmade gold case now contains:

- source authority ledger;
- human research workflow;
- evidence strength model: strong / medium / proxy / cannot infer;
- human workpaper v0.1;
- polished memo v0.1, later superseded by polished memo v0.2;
- public data ceiling and typed gaps;
- reverse-engineering requirements for Research Lead, specialist, JudgmentCard, ProductIntelligenceGraph projection, MemoLogicPlan, and writer.

## Governance Update

P33 status is now:

```text
humanmade_gold_case_v0_1_documented_pending_machine_readable_audit_superseded_by_polished_memo_v0_2
```

The next allowed action is:

1. Convert the humanmade gold case into machine-readable `HumanmadeGoldCaseSpec`.
2. Run no-paid audit over accepted aggregate r7 and Memo Writer payload.
3. Attribute every miss to data, parser, runtime projection, specialist skill, aggregation, or writer.

Forbidden until that audit passes or reaches a bounded pass:

- paid Memo Writer rerun;
- model comparison;
- broad full-chain;
- case expansion.

## Verification

No paid LLM call, full-chain, model comparison, or runtime mutation was used for this worklog.

Required follow-up verification:

- JSONL parse for `docs/project_os/p33_execution_plan_ledger.jsonl`;
- `git diff --check` on touched files.
