# P30 Agent Information Economy Product-Core Upgrade

Date: 2026-07-02

## Prompt

Upgrade the token/cost issue into a product-core issue. The problem is not only saving tokens. It reflects whether the agent framework is well designed: planning, scheduling, information transfer, context compression, specialist coordination, repair loops, and writer contracts.

## Decision

`Agent Information Economy` is now a core product and runtime quality dimension.

High token consumption with low insight is not acceptable even if the run stays under a budget. It means the system may be transferring invalid information, activating too many specialists, duplicating context across agents, relying on repair because first-pass analysis is weak, or passing large inputs to agents that produce unusable outputs.

## Product Definition

The product should optimize:

- token -> WorkpaperEvent / ClaimCard / JudgmentState conversion;
- required item -> correct specialist activation;
- evidence pack -> role-specific compact input;
- first pass -> useful analyst judgment;
- repair loop -> explicit root cause, not repeated reading;
- writer input -> answer-first memo surface.

The product should expose:

- when a node received too much input and produced little accepted output;
- when the same evidence was read by several agents without adding new insight;
- when a specialist was activated but its output was unused;
- when a repair was caused by internal planning/selector/writer failure rather than public-data absence;
- when a final memo consumed many claims but produced generic text.

## Documents Updated

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
  - Added `Agent Information Economy` as a product principle and acceptance surface.
  - Added product metrics such as token-to-workpaper yield, duplicate-context rate, invalid-information-transfer rate, specialist useful-output rate, first-pass judgment yield, and repair-due-to-agent-failure rate.
- `docs/product/PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md`
  - Added Agent Information Economy to the B2B feature/value matrix.
- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
  - Reclassified the P30 token issue as a product/agent-framework quality problem.
  - Added future runtime objects/gates: `AgentInformationEconomyLedger`, `InformationTransferQualityGate`, `SpecialistYieldGate`, `RepairLoopRootCauseGate`, and Workbench token-to-insight projection.
- `docs/worklog/product_strategy/064_p30_full_chain_root_cause_repair_plan.md`
  - Reframed R14 as agent framework quality, not just budget blocking.
- `docs/worklog/product_strategy/066_p30_token_budget_and_specialist_cost_root_cause_repair.md`
  - Added product-core interpretation and follow-up runtime requirements.
- `docs/worklog/00_internal_master_checklist.md`
  - Added open runtime item for Agent Information Economy ledger/gates/projection.

## Runtime Implementation Update

2026-07-02 follow-up implementation is now partially complete and deterministic-first:

- Added `src/sec_agent/agent_information_economy.py`.
  - Builds a run-level and case-level `AgentInformationEconomyLedger` from saved eval artifacts.
  - Classifies high-token / low-yield symptoms into root-cause candidates such as Research Lead activation breadth, role-specific selector or claim-conversion failure, context-pack dedupe failure, MemoLogicPlan-to-writer payload failure, and repair-loop agent failure.
  - Keeps measurement boundaries explicit: exact cross-agent prompt-token overlap still requires prompt-pack capture; current duplicate-context and invalid-transfer measurements are artifact-derived proxies.
- Updated `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
  - Writes `agent_information_economy_preflight.json` for no-paid preflight runs.
  - Writes `agent_information_economy_audit.json` and `agent_information_economy_audit.md` after output-quality audit for real-chain eval runs.
  - Adds compact `agent_information_economy_audit` to the aggregate eval summary for downstream Workbench / release-gate consumption.
- Added deterministic tests in `tests/test_agent_information_economy.py`.
  - Healthy low-cost / dense-claim case passes.
  - High-token / low-claim-yield / broad-specialist-fanout case fails with root-cause candidates.
  - Preflight-only expensive run flags token and fanout risk before model calls.

Remaining open items:

- Workbench token-to-insight projection is not implemented yet.
- Prompt-pack-level exact duplicate-token overlap is not captured yet.
- The two AI/Semis paid full-chain cases remain blocked until deterministic pruning/coalescing brings preflight under budget or the user explicitly approves expensive-run override.

## Verification

No model run and no paid token use.

- `python -m pytest tests/test_agent_information_economy.py -q` -> `3 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph -q` -> `1 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run tests/test_multi_agent_output_quality_audit.py::test_output_quality_audit_reports_cost_quality_metrics -q` -> `3 passed`
- `python -m pytest tests/test_multi_agent_output_quality_audit.py -q` -> `9 passed`
- `python -m compileall -q src/sec_agent/agent_information_economy.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` -> pass

Follow-up technical implementation should be deterministic-first:

1. use the new ledger on saved/preflight artifacts to identify dominant invalid-transfer / duplicate-context / low-yield nodes;
2. patch routing/compression/coalescing before any paid full-chain rerun;
3. add Workbench projection after the ledger fields stabilize;
4. add exact prompt-pack overlap capture when prompt-pack storage is approved.
