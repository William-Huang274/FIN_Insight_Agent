# 227 - Fin Agent Focused Bridge And Standard Guard Real Runs

Date: 2026-06-02

## Context

After the previous DeepSeek transport timeout diagnostic, the next action was to resume small real full-chain runs instead of launching the full 17-case suite. The immediate targets were:

- Repair focused-answer cases that skip Specialist agents but still need a memo-ready Judgment Plan.
- Keep standard-memo runs from expanding into expensive quality source-gap second-pass retrieval.
- Check whether the chain can produce usable output across focused and standard modes with real retrieval.

## Changes

Implemented focused-answer synthesis and output cleanup:

- Added `focused_answer_synthesizer` as a bounded bridge agent for focused-answer routes that deliberately skip Specialist analysts.
- `aggregate_focused_answer_judgment_plan()` now builds supported ClaimCards from retrieved context rows and runtime ledger rows, instead of letting Memo Writer see an empty Judgment Plan.
- Focused bridge ClaimCards now honor `response_language`, with Chinese user-facing thesis/caveats and localized common metric labels.
- Memo Writer numeric-fidelity cleanup now falls back to safe claim-derived direct answers when deleting unsupported numeric tokens would damage Chinese syntax.
- Chinese output normalization now removes mixed `。.` punctuation and separates hard-concatenated ticker transitions such as `增长TGT`.

Implemented standard-mode second-pass guard:

- Coverage and quality second-pass decisions are now filtered by execution mode.
- `deep_research` keeps normal second-pass behavior.
- `standard_memo` and `focused_answer` record source/quality gaps but defer second-pass retrieval by default.
- A debug escape hatch remains through `allow_standard_second_pass=True` in state/context.

## Local Verification

Passed:

```text
python -m compileall src\sec_agent\multi_agent_contracts.py src\sec_agent\langgraph_orchestrator.py src\sec_agent\memo_llm.py
pytest -q tests\test_multi_agent_contracts.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_reflection_second_pass.py
73 passed
```

Key regression coverage added:

- Focused-answer bridge builds memo-ready ClaimCards from bounded rows.
- Focused graph path produces a judgment plan without activating Specialist subgraph.
- Chinese numeric cleanup does not leave damaged direct-answer text.
- Standard memo defers coverage second-pass by default while deep-research second-pass remains covered by existing tests.
- Chinese punctuation normalization separates concatenated ticker transitions.

## Real DeepSeek Runs

Accepted real diagnostic runs:

| Run | Case | Mode | Gate | Tool calls | Memo claims | Runtime / rows | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `20260602_fin_agent_focused_amzn_margin_v0_6` | `fin_full_focused_amzn_margin_management_zh` | focused_answer | pass | 3 | 3 | 194.2s; context `59`, ledger `5` | Focused bridge fixed the earlier empty-Judgment blocked memo path. |
| `20260602_fin_agent_standard_consumer_v0_2` | `fin_full_standard_wmt_tgt_consumer_zh` | standard_memo | pass | 3 | 5 | 371.1s; context `59`, ledger `3`, market `2` | Standard full chain completed after second-pass guard; quality gaps were recorded and deferred. |
| `20260602_fin_agent_focused_lly_rnd_v0_1` | `fin_full_focused_healthcare_lly_rnd_zh` | focused_answer | pass | 5 | 2 | 207.2s; context `45`, ledger `0` | Correctly bounded output to 8-K management commentary and source gaps. |

Two abandoned diagnostic attempts are also informative:

- `20260602_fin_agent_standard_energy_v0_1`
- `20260602_fin_agent_standard_consumer_v0_1`

Both produced partial retrieval artifacts and then stalled after `quality_source_gap_1_*` retrieval. The pattern led to the standard-mode second-pass guard above.

## Quality Read

Focused mode is now functionally stable:

- It no longer blocks merely because Specialists are intentionally skipped.
- It keeps tool usage bounded.
- It produces useful caveated answers when evidence is thin.
- Remaining weakness: it is still a bounded answer, not a full memo; if users ask for investment depth, Research Lead should route to standard or deep mode.

Standard mode improved but remains expensive:

- Consumer case produced a coherent thesis: WMT revenue growth versus TGT profit/cash-flow pressure and market-relative divergence.
- Aggregator generated `12` supported ClaimCards with `4/4` memo slots covered.
- Memo Writer produced an expanded draft in one attempt.
- Remaining weakness: standard case still took about `371s`; Research Lead and retrieval startup cost are still high even with second-pass disabled.

## Open Issues

- Standard-mode runtime is still too high for interactive UX.
- Specialist token/latency diagnostics are aggregated under `specialists`; per-agent audit expansion should be improved.
- Focused bridge localization now has tests, but some older run previews predate the latest display-label patch.
- Deep-research second-pass should be retained, but its request generation should still be audited for precision before broad 17-case execution.

## Next

Recommended next sequence:

1. Add per-specialist token/latency summary to `multi_agent_summary.json` and eval case score.
2. Run one standard memo after the latest punctuation patch, preferably a lower-cost banking or semis case, before rerunning energy.
3. Add a standard-mode latency gate that flags route count, second-pass decision, and per-agent token cost separately.
4. Only after standard latency is acceptable, run a 3-case mini-suite: exact + focused + standard.
5. Keep full 17-case regression and merge-closeout deferred until standard runtime is stable.

No runtime credential or raw LLM response was saved.
