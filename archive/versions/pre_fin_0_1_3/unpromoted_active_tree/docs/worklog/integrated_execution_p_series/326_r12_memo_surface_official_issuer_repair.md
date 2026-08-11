# 326 R12 Memo Surface And Official Issuer Repair

Date: 2026-06-14

## Scope

This checkpoint fixes two R12 release blockers found after reading rendered outputs:

- Memo renderer exposed internal analysis fields such as `mechanism`, `financial_bridge`, `Bridge the claim`, raw evidence refs, and pipe-joined schema fragments.
- Non-US issuers outside local SEC/MCP route scope, such as ASML, were too easy to expose as bounded gaps before probing official public sources.

## Changes

- Wired `ResearchObjectiveContract`, `LeadReviewCheckpoint`, `TargetedRepairPlan`, and `MemoLogicPlan` into the main LangGraph aggregate -> memo writer path.
- Updated Memo Writer prompt contract to make `memo_logic_plan` the primary writing outline and to forbid visible internal field labels in user-facing prose.
- Reworked renderer surface:
  - section order follows `MemoLogicPlan`;
  - body uses short citations like `[C1]`;
  - raw refs move to an evidence index;
  - internal labels such as `机制`, `财务桥`, `Bridge the claim`, `driver_id`, and `gap_id` are stripped from rendered text.
- Added `surface_readability` eval gate to reject internal field dumps, raw `INTERACTIVE_*` refs, repeated wrapper boilerplate, pipe-joined dumps, and language mismatch.
- Added issuer coverage policy:
  - local SEC/MCP route misses become `issuer_official_source_probe_required` retrievable gaps when official sources are theoretically available;
  - targeted repair uses official-only scope: SEC FPI `20-F`/`6-K`, company IR, local exchange filings, and regulator filings;
  - only after that probe fails may the graph expose `bounded_gap_after_official_issuer_source_probe`.

## Verification

- `python -m py_compile src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_llm.py src/sec_agent/lead_supervision.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
- `python -m pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_runtime_bridge_contracts.py -q`
  - Result: `55 passed`

## Follow-up

- Live/full-chain rerun completed in `327_r12_surface_resource_and_specialist_repair.md`; latest R12 2-case Workbench run passed `2/2`.
- Add real official-source web repair execution for ASML/local-exchange issuers; this change currently establishes policy, graph state, and eval contracts.
