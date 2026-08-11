# Model Run: 20260521_sec_agent_free_query_deepseek_api_insight_relaxed_summary_v1

## Summary
- Purpose: test whether API synthesis backends can use a looser evidence-bound analyst thesis while preserving deterministic SEC gates.
- Status: completed; final rerun passed all gates.
- Run type: inference + deterministic gates.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 5090 host; artifacts synced back to local `D:\FIN_Insight_Agent`.

## Code And Command
- Entry points:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- Backend: DeepSeek API `deepseek-v4-pro`, thinking disabled.
- API-only change:
  - For `deepseek` / `openai_compatible` synthesis on broad AI free-query tasks, `summary` is prompted as a 5-8 sentence analyst thesis.
  - Qwen/local vLLM keeps the previous tighter audit-style prompt.
  - Exact numbers remain restricted to `decision_drivers` / `key_points` with metric IDs from runtime Exact-Value Ledger.
- Boundary reinforcement:
  - Drivers using `capital_expenditure_proxy` now get a deterministic proxy caveat during normalization.

## Inputs
- Prompt:
  - `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Scope:
  - 30 companies, years `2023,2024,2025`, SEC 10-K only.
- Inventory digest:
  - `e413b6c9ccd0`

## Outputs
- Final passing run:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_190741_b38c717195`
- Logged query/output:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_190741_b38c717195/qwen/input_output.md`
- Diagnostic pre-fix run:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_185654_b38c717195`

## Results
- Final post-gates:
  - `ok=True`
  - `pass=12`
  - `fail=[]`
  - `qwen_answer_ratio=1.0`
- Runtime ledger:
  - rows `36`
  - context rows `360`
- Runtime:
  - total elapsed `535.16 sec`
  - DeepSeek synthesis latency `169.787 sec`
  - tokens: `44,377 input`, `5,298 output`, `49,675 total`

## Output Quality Read
- Improvement:
  - The opening summary now gives a real thesis: AI evidence clusters around semiconductors, cloud infrastructure, and capex, with uneven disclosure quality and layered benefit timing.
  - The answer still binds exact values to ledger-supported drivers and key points.
- Boundary behavior:
  - The first API insight run produced a stronger summary but failed `answer_vs_judgment_plan_gate` because a `capital_expenditure_proxy` driver missed a proxy caveat.
  - After deterministic proxy caveat repair, the rerun passed all gates.
- Remaining quality issue:
  - The named-fact sanitizer can over-generalize unsupported names into `相关命名标签`, which is safe but awkward for user-facing prose.
  - Next production pass should improve sentence-level citation/support binding and named-fact recovery rather than loosening gates.

## Decision
- Proceed with API insight mode as the preferred production synthesis profile for broad free-query prompts.
- Keep Qwen9B on the stricter profile for smoke/diagnostic usage.
