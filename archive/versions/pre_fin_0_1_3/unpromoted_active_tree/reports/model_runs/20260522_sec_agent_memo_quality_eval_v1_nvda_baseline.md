# Model Run: 20260522_sec_agent_memo_quality_eval_v1_nvda_baseline

## Summary
- Purpose: 建立第一版投研 memo 质量评估集与 scorer，并用最新 DeepSeek API NVDA 增长 + 竞争对手输出做 baseline。
- Status: completed; current output is evidence-safe but does not yet pass the stricter memo-quality threshold.
- Run type: evaluation over saved inference output.
- Timestamp: 2026-05-22 Asia/Shanghai.
- Environment: local Windows workspace `D:\FIN_Insight_Agent`.

## Code And Command
- Eval set:
  - `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`
- Evaluator:
  - `scripts/score_sec_agent_memo_quality.py`
- Scored run:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112`
- Command:

```powershell
python scripts\score_sec_agent_memo_quality.py `
  --run-dir eval\sec_cases\outputs\interactive_sec_agent\20260522_010002_60a9e00112 `
  --output-path eval\sec_cases\outputs\interactive_sec_agent\20260522_010002_60a9e00112\memo_quality_report.json
```

## Eval Set Contract
- File: `eval_sets/sec_free_query_memo_quality_eval_v1.jsonl`
- Case count: 5
- Cases:
  - `memo_nvda_growth_competitors_001`
  - `memo_amzn_aws_capex_002`
  - `memo_meta_ai_capex_rd_003`
  - `memo_jpm_rate_credit_004`
  - `memo_lly_growth_quality_005`
- Required memo dimensions:
  - direct answer
  - investment thesis
  - what changed
  - why it matters
  - peer readthrough when applicable
  - counterarguments
  - watch items
  - source limitations
- Evidence roles:
  - core facts
  - management explanation
  - peer contrast
  - risk or counterevidence
  - missing evidence

## Results
- Output report:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112/memo_quality_report.json`
- Scored query:
  - `你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁`
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
- The result matches the qualitative read:
  - DeepSeek API synthesis is now strong on thesis, causal explanation, evidence binding, peer roles, and source boundary.
  - It is still weak as a formal investment memo because it does not explicitly render counterarguments, watch items, and memo sections.
  - The low `format_polish` score is driven by saved structured output containing audit fields and a residual unresolved exact-value placeholder from the official run; a post-run cleanup patch exists but was not rerun for this official artifact.
- Decision:
  - Keep deterministic gates as audit-only safety.
  - Next synthesis work should target memo shape and reasoning roles, not more fallback rules.

## Validation
- `python -m py_compile scripts\score_sec_agent_memo_quality.py` passed.
- JSONL parse check found 5 eval cases.
