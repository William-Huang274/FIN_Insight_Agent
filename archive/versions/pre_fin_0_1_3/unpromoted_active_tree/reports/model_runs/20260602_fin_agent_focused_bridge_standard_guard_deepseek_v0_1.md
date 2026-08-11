# 20260602 Fin Agent Focused Bridge Standard Guard DeepSeek v0.1

Date: 2026-06-02

## Status

Accepted as a diagnostic full-chain recovery run. Not a full 17-case release gate.

## Purpose

Resume real DeepSeek full-chain evaluation after the prior transport timeout, while fixing two quality/cost issues:

- focused-answer routes skipped Specialists and therefore had no memo-ready Judgment Plan;
- standard-memo routes were allowed to execute quality source-gap second-pass retrieval, causing long/stalled runs.

## Code Gate

Local validation passed:

```text
compileall: multi_agent_contracts.py, langgraph_orchestrator.py, memo_llm.py
pytest -q tests\test_multi_agent_contracts.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_reflection_second_pass.py
73 passed
```

## Real Runs

| Run ID | Case | Mode | Status | Summary |
| --- | --- | --- | --- | --- |
| `20260602_fin_agent_focused_amzn_margin_v0_6` | `fin_full_focused_amzn_margin_management_zh` | focused_answer | pass | `3` tools, `3` memo claims, `59` context rows, `5` ledger rows. Fixed prior empty-Judgment block. |
| `20260602_fin_agent_standard_consumer_v0_2` | `fin_full_standard_wmt_tgt_consumer_zh` | standard_memo | pass | `3` tools, `5` memo claims, `12` supported ClaimCards, `4/4` memo slots, `371.1s`. Standard second-pass was deferred and recorded. |
| `20260602_fin_agent_focused_lly_rnd_v0_1` | `fin_full_focused_healthcare_lly_rnd_zh` | focused_answer | pass | `5` tools, `2` memo claims, bounded 8-K commentary answer with explicit source gap. |

Diagnostic failed/stalled attempts:

- `20260602_fin_agent_standard_energy_v0_1`
- `20260602_fin_agent_standard_consumer_v0_1`

Both reached real retrieval and then stalled around `quality_source_gap_1_*` routes before final summary artifacts. They were terminated and are not accepted gates.

## Interpretation

Focused mode is now usable for bounded answers. Standard mode is functionally improved and can complete, but runtime remains too high for a responsive product experience. The standard-mode second-pass guard prevents runaway quality-gap retrieval while preserving deep-research second-pass behavior.

## Follow-Up Gates

- Expand per-Specialist diagnostics in eval summaries.
- Rerun one standard case after the latest punctuation/metric-display patch.
- Add a standard latency gate for route count, second-pass decision, and token cost.
- Defer the full 17-case suite until standard runtime is stable.

Runtime credential and raw LLM responses were not saved.
