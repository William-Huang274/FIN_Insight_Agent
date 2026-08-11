# 131 - SEC Agent Memo Quality Eval v1

## Summary
- Date: 2026-05-22
- Branch: `codex/api-model-call-architecture`
- Purpose: 把“高质量投研 memo”从主观感受变成可运行的评估合同，避免继续只靠 deterministic gates 或 prompt 兜底判断模型质量。
- Status: v1 eval set and scorer added; latest NVDA DeepSeek output is evidence-safe but narrowly fails memo-quality threshold.
- Secret policy: no API key, SSH password, or temporary credential is stored.

## Why This Exists
The existing free-query chain already proves that API synthesis can stay inside:

- SEC-only source boundary
- BGE-M3 retrieval/rerank evidence
- runtime Exact-Value Ledger
- Evidence Coverage Matrix
- Judgment Plan
- deterministic post-gates

But those gates cannot judge whether the final answer is a useful investment memo. They catch hallucinations and evidence drift; they do not require explicit counterarguments, watch items, or a memo-grade thesis structure.

## Added Artifacts
- Eval set:
  - `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`
- Scorer:
  - `scripts/score_sec_agent_memo_quality.py`
- Latest scored report:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112/memo_quality_report.json`
- Model run ledger:
  - `reports/model_runs/20260522_sec_agent_memo_quality_eval_v1_nvda_baseline.md`

## Eval Cases
The v1 set contains 5 prompts:

1. `memo_nvda_growth_competitors_001`
   - NVDA growth quality and competitor landscape.
2. `memo_amzn_aws_capex_002`
   - AMZN AWS growth, capex, cash-flow implications.
3. `memo_meta_ai_capex_rd_003`
   - META AI investment, R&D, capex, profit quality.
4. `memo_jpm_rate_credit_004`
   - JPM net interest income, credit risk, bank business quality.
5. `memo_lly_growth_quality_005`
   - LLY growth quality, R&D, product mix, risk factors.

## Scoring Dimensions
- `thesis_clarity`
- `causal_depth`
- `evidence_usefulness`
- `counterargument_coverage`
- `watch_item_coverage`
- `peer_comparability`
- `source_boundary`
- `memo_structure`
- `format_polish`

This is intentionally stricter than the existing free-query quality scorer. It requires memo sections and explicit reasoning roles instead of only checking whether the answer is fluent and grounded.

## Baseline Result
- Scored run:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112`
- Query:

```text
你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁
```

- Result:
  - `mean_score_total=0.777`
  - `pass_threshold=0.78`
  - `pass_count=0`
  - `fail_count=1`
- Dimension means:
  - `thesis_clarity=1.0`
  - `causal_depth=1.0`
  - `evidence_usefulness=1.0`
  - `counterargument_coverage=0.55`
  - `watch_item_coverage=0.35`
  - `peer_comparability=1.0`
  - `source_boundary=1.0`
  - `memo_structure=0.0`
  - `format_polish=0.45`

## Interpretation
- The latest DeepSeek output is not weak in the same way the local 9B output was weak.
- It is strong on:
  - thesis,
  - causal explanation,
  - evidence binding,
  - peer roles,
  - source boundary.
- It is still short of high-quality memo form because it lacks:
  - explicit counterarguments,
  - explicit watch items,
  - formal memo sections,
  - clean user-facing format after audit artifacts.

## Next Step
Do not add more fallback rules for specific phrases. The next structural change should update the API synthesis schema/prompt toward memo roles:

```text
direct_answer
investment_thesis
what_changed
why_it_matters
peer_readthrough
counterarguments
watch_items
source_limitations
```

Then rerun the same NVDA case and score against `memo_quality_eval_v1` before expanding to all 5 prompts.
