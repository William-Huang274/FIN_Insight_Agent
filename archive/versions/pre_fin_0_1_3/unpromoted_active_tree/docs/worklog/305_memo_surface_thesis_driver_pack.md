# 305 Memo Surface Thesis Driver Pack

Date: 2026-06-13

## Scope

This checkpoint closes the first memo-surface quality pass after G11 full-chain validation. The test strategy follows the current graph policy: use memo-writer-entry gates for existing cases, and reserve full-chain Workbench runs for new cases or graph-level regressions.

## Changes

- Added `thesis_driver_pack` to the judgment contract. It is derived only from verified ClaimCards, conflicts, unsupported exclusions, and source-boundary notes.
- Wired the pack through specialist aggregation, focused-answer bridge, and governance-filter refresh.
- Updated Memo Writer input projection so `thesis_driver_pack` is the first writing brief, followed by `memo_thesis_pack`, `memo_thesis_plan`, and `memo_outline`.
- Kept the pack base-only in Memo Writer normalization. Model-emitted `thesis_driver_pack` is discarded and replaced from verified judgment state.
- Updated renderer output to add a stable `Core thesis` / `核心判断` section and a compact evidence-to-thesis chain without copying raw driver statements into Chinese output.
- Persisted full memo surface artifacts for multi-agent runs: `qwen/rendered_answer.md`, `memo_answer.json`, `verified_judgment_plan.json`, `claim_cards.json`, and `thesis_driver_pack.json`.
- Tightened verifier profile gating so standard/expanded/deep_research memo outputs must satisfy profile-specific minimum `memo_claims` when a thesis pack is ready. Compact/focused answers keep the lighter claim-count rule.

## Gates

Local unit gates:

- `pytest -q tests\test_multi_agent_contracts.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_langgraph_routing.py`
- Result: `94 passed`

Memo-writer-entry real gates from reusable S5 artifacts:

- `20260613_memo_surface_thesis_driver_gate_v0_2`
  - Case: `ma_nvda_amd_market_standard`
  - Result: pass
- `20260613_memo_surface_thesis_driver_gate_v0_3`
  - Case: `ma_ai_capex_supply_chain_deep`
  - Result: pass

Earlier combined run `20260613_memo_surface_thesis_driver_gate_v0_1` found a useful failure: expanded profile allowed only 3 memo claims. The fix was to move profile minimum claim count into deterministic verifier gates instead of relaxing the diagnostic.

## Boundary

No full-chain Workbench run was executed for this change because no new case was introduced and the user explicitly asked to focus testing from Memo Writer for existing cases. Full-chain should be rerun when adding new cases, changing upstream retrieval/evidence operators, or changing graph node ordering.
