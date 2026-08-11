# P30 Token Budget And Specialist Cost Root-Cause Repair

Date: 2026-07-02

## Prompt

Fix the five cost and execution-discipline issues before running another real full-chain test:

1. full-chain regression is run too often;
2. specialist fanout is too broad;
3. specialist inputs are too fat;
4. claim yield is too low;
5. hard token budget gates are missing.

The user explicitly asked not to burn paid tokens first. This work therefore uses deterministic tests and preflight only.

## Decision

Paid full-chain is now last-step evidence for this repair path. The runtime must first prove that the planned run fits token / paid-call budgets and that specialist activation is scoped to required items. Gates are not being used as the only fix: the upstream specialist activation and prompt payload construction were changed first, and the gates remain as regression protection.

2026-07-02 product-owner clarification: this is not a narrow "save token" issue. It is now classified as a product-core agent framework problem: `Agent Information Economy`. High token consumption with low rendered insight means the agent system failed to plan, compress, route, analyze, coordinate, or write effectively. Token waste is a symptom that can reveal quality failures:

- invalid information transfer between agents;
- overly broad specialist fanout;
- duplicate reading of the same upstream packs;
- repair loops caused by weak first-pass analysis;
- specialist receiving a large payload but producing no useful ClaimCards;
- writer consuming many claims but producing low-density or generic memo prose.

The product goal is not simply lower token count. The goal is higher token-to-workpaper and token-to-judgment yield by improving our own agent architecture.

## Work Completed

- Added hard token-budget preflight and blocking in `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Added default-on required-item specialist activation gating in `src/sec_agent/multi_agent_runtime.py`.
- Added compact specialist prompt pack wrappers in `src/sec_agent/specialist_llm.py`.
- Added output-cost / claim-yield blocking checks to the full-chain aggregate gate.
- Added no-paid deterministic tests for token-budget preflight and specialist prompt pack compaction.
- Updated the P30 source plan and implementation log so broad full-chain remains blocked until the budget preflight fits or is explicitly overridden.

## Evidence

No paid LLM run was executed.

Commands:

```text
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_output_quality_audit.py -q
122 passed

python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py -q
93 passed

python -m compileall -q src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

Two-case AI/Semis preflight:

```text
status=blocked_preflight_token_budget
allowed=false
estimated_total_tokens=272000
estimated_paid_call_count=18
token_budget_total=180000
token_budget_per_case=120000
max_paid_calls=8
```

This proves the next paid run would still be too expensive under the current budget. The correct next step is additional deterministic pruning / coalescing, not another DeepSeek full-chain run.

## Follow-Up

- Inspect the token-budget plan by node and case, then reduce the dominant contributors before real rerun.
- Tighten required-item routing for cases where only product/fundamental/capital dimensions are actually needed.
- Add AgentCoalescer / model-tier routing only after the deterministic budget estimate shows which nodes dominate.
- Rerun full-chain only after preflight fits budget, or after an explicit user-approved expensive-run override.

Product-core follow-up:

- Add an `AgentInformationEconomyLedger` or equivalent runtime view that records per node: input pack refs, selected rows, duplicate refs, input token estimate, output ClaimCards / WorkpaperEvents / accepted judgments, rejected output, and repair reason.
- Add `InformationTransferQualityGate`: fail when a node receives many rows/tokens but produces no accepted downstream artifact.
- Add `SpecialistYieldGate`: fail when a specialist was activated without required-item match or produced output unused by LeadReview / MemoLogicPlan.
- Add `RepairLoopRootCauseGate`: distinguish valid external-data repair from repeated internal failure caused by route, selector, parser, prompt, or writer defects.
- Add Workbench visibility for token-to-insight: users should see whether expensive work produced accepted judgment, gap, or reusable knowledge asset.
