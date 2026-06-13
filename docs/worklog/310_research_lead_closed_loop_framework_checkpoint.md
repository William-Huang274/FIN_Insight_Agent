# 310 - Research Lead Closed-loop Framework Checkpoint

Date: 2026-06-14

## Prompt

The user asked to preserve the latest two discussion turns before continuing design work. The discussion covered:

- Whether the current reflection mechanism is effective enough.
- Upgrading Research Lead from one-shot dispatcher to supervising analyst.
- Letting Research Lead inspect downstream artifacts, run audit, gaps, and evidence boundaries.
- Having Research Lead trigger targeted repair or expose bounded/commercial gaps.
- Making Memo Writer only responsible for natural language, report structure, and file generation.
- Ensuring the new design includes `FundamentalStatementPack`, `JudgmentState`, and deeper financial statement analysis.
- Adopting a more comfortable output style: natural-language conclusion, evidence-backed bullets, boundary notes, and next-step suggestions.
- Adding a BGE/rerank resource scheduler instead of falling back to CPU for all concurrent work.
- Adding token/model dynamic scheduling, including cheaper models, deterministic paths, agent merge/skip, and cost audit.

## Work Completed

- Added `docs/architecture/agent_graph_vnext/09_lead_supervised_closed_loop_research_framework.zh-CN.md`.
  - Records the new closed-loop graph.
  - Defines `ResearchObjectiveContract`, `LeadReviewCheckpoint`, `TargetedRepairPlan`, `MemoLogicPlan`, role-specific evidence selector, BGE resource scheduler, and model/token router.
  - Promotes `FundamentalStatementPack` and `JudgmentState` to first-class nodes in the next-stage graph design.
  - Records Memo Surface vNext output style.
  - Splits the next stage into L1-L7 implementation packages.
- Updated `docs/architecture/agent_graph_vnext/README.zh-CN.md` to index the new 09 document.
- Updated `docs/worklog/00_internal_master_checklist.md` with the new Research Lead closed-loop supervision checklist.

## Result

This is a documentation checkpoint only. It does not change runtime behavior.

## Verification

- No code tests were run because only Markdown planning/checklist files changed.
- `git diff --check` should be run before commit if this document is staged with later implementation work.

## Follow-up

Next implementation sequence should start from:

1. L1 `ResearchObjectiveContract`.
2. L2 `LeadReviewCheckpoint`.
3. L4 role-specific Product / Market / Capital selector and quotas.
4. L3 targeted repair loop.
5. L5 MemoLogicPlan / Memo Surface vNext.
6. L6 BGE scheduler and L7 ModelRouter / AgentCoalescer.
