# 306 Analyst Depth Gate And Dimension-Led Memo Surface

Date: 2026-06-13

## Context

Before running the next full-chain G11 pass, the memo surface needed to stop presenting one driver at a time. The target output is a dimension-led analyst memo: fundamentals, product/production, capital/financing, competition/market position, industry/supply-chain transmission, and risk/counterevidence. The opening summary should synthesize mechanisms and evidence boundaries instead of reading like a generic row recap.

## Implemented

- Added ClaimCard analyst-depth annotations in `multi_agent_contracts.py`.
  - New fields: `analysis_dimension`, `analyst_angle`, and nested `analyst_depth`.
  - The depth block carries analysis lens, evidence role, business mechanism, financial bridge, comparison basis, and counter-read.
  - Specialist claims, focused-answer claims, and synthesized thesis claims now use the same annotation path.

- Upgraded `thesis_driver_pack`.
  - Added deterministic `dimension_sections` built only from verified supported ClaimCards, conflicts, gaps, and source-boundary notes.
  - Existing `driver_cards`, `counter_driver_cards`, and `gap_cards` remain for compatibility.
  - `build_multi_agent_memo_draft` now projects `dimension_analyses` for the memo writer.

- Added `analyst_depth_gate` to memo verification.
  - Applies to standard, expanded, and deep profiles.
  - Requires dimension analyses when dimension sections are available.
  - Requires summaries, traceability through claim IDs or evidence refs, and at least two analyst-depth signals such as mechanism, financial bridge, competition read, or counter-read.
  - Blocks known generic template language.

- Updated memo writer normalization and prompt contract.
  - LLM output can now include `dimension_analyses`.
  - If omitted, normalizer fills the field from deterministic pack structure; explicit empty lists remain a verifier failure.
  - Chinese localization now handles dimension-analysis prose fields.
  - Default action-item templates are now dimension/metric aware.

- Updated final memo renderer.
  - Renders `Dimension analysis` / `分维度分析` before key memo claims.
  - Falls back to the old evidence-to-thesis chain only when no dimension structure exists.

- Updated G11 judgment/memo gate eval metrics.
  - Added checks for dimension sections, memo dimension analyses, traceability, and analyst-depth gate pass.
  - Added judgment and memo metrics for dimension counts and dimension IDs.

## Verification

- `python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_judgment_memo_gate.py`
- `python -m pytest -q tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_langgraph_routing.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_workbench_artifacts.py tests/test_multi_agent_real_llm_chain_eval.py`
  - Result: 150 passed.

## Next Checkpoint

Run memo-writer-first cases before full-chain replay:

1. Verify the memo answer carries `dimension_analyses` in the JSON artifact.
2. Verify rendered answers lead with a dense core thesis and dimension sections, not a driver list.
3. Inspect `claim_verification.analyst_depth_gate`; failures should be repaired before final rendering.
4. Only after the memo surface passes on fresh cases should full-chain G11 be rerun.
