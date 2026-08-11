# Model Run: 20260516_phase2_aspect_human_gold_policy_eval

## Summary

- Purpose: 用人工金融证据协议复核 aspect-level top-direct 候选，并评估当前 BGE + Qwen verifier precision gate。
- Status: completed
- Run type: labeling + saved-prediction evaluation
- Timestamp: 2026-05-16
- Environment: local `D:\FIN_Insight_Agent`, Python 3.

## Code And Command

- Label protocol: `docs/worklog/35_financial_evidence_label_protocol.md`
- Entry points:
  - `scripts/build_aspect_policy_human_gold.py`
  - `scripts/evaluate_aspect_policy_human_gold.py`

```powershell
python scripts\build_aspect_policy_human_gold.py
python scripts\evaluate_aspect_policy_human_gold.py
python -m py_compile scripts\build_aspect_policy_human_gold.py scripts\evaluate_aspect_policy_human_gold.py
```

## Inputs

- Aspect pool: `reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl`
- Qwen predictions: `reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl`
- Review scope: union of per-aspect top direct candidates under:
  - `qwen_direct_highest_confidence`
  - `qwen_direct_highest_rerank`
  - `qwen_direct_highest_rerank_conf90`

## Outputs

- Human gold subset: `eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl`
- Metrics: `reports/metrics/sec_tech_10k_aspect_policy_human_gold_v0_1_metrics.json`

## Results

Manual review set:

- reviewed rows: 90
- all aspects: 73
- human labels:
  - direct: 76
  - partial: 14
  - false: 0
- weak-label disagreements: 38/90

Policy results:

| Policy | Selected Aspects | Missing Aspects | Citation Precision | Broad Relevance Precision | Citation Aspect Coverage | Relevant Aspect Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen direct, highest confidence | 70/73 | 3 | 0.9000 | 1.0000 | 0.8630 | 0.9589 |
| Qwen direct, highest rerank | 70/73 | 3 | 0.8571 | 1.0000 | 0.8219 | 0.9589 |
| Qwen direct, highest rerank, confidence >= 0.90 | 70/73 | 3 | 0.8714 | 1.0000 | 0.8356 | 0.9589 |

Missing aspects under all three policies:

- SNOW `customer_metrics`: `11,159 total customers`
- SNOW `rpo_visibility`: `weighted-average remaining life 2.4 years`
- ADBE `rpo_visibility`: `approximately 65% recognized over next 12 months`

Important calibration findings:

- The weak aspect labels are too noisy for precision claims: many `partial` rows are citation-grade direct under the financial protocol, and several `false` rows are actually useful partial evidence.
- The highest-confidence policy is better than highest-rerank for citation precision on this subset. Rerank sometimes prefers a broader table or nearby context object over the exact claim.
- No selected top-direct candidate was fully irrelevant in this reviewed subset, but 7-10 rows per policy should be marked `background` instead of citation evidence.

## Experiment Governance

- Hypothesis: human financial-label protocol will separate model errors from weak-label noise and clarify the right precision gate.
- Decision target: identify whether Qwen top-direct selection can supply citation-grade aspect evidence.
- Ceiling / upper bound: only top direct candidates were reviewed, not the full 730-row pool or all Qwen direct rows.
- Baselines: weak-label aspect evaluation gave Qwen keep-direct direct precision 0.5087 and relevant precision 0.8537.
- Decision label: proceed with calibrated gate design.
- Mainline decision: use `direct` vs `partial` as citation/background roles, not a single binary keep/drop. Prefer highest verifier confidence with rerank as tie-break for first citation candidate, then use background evidence separately for synthesis context.

## Caveats And Next Step

- This is a Codex manual finance review and still needs user spot-checking.
- The subset is policy-focused, not a full-pool gold set.
- Next step: implement a calibrated evidence pool exporter that emits `citation_evidence`, `background_evidence`, and `missing_aspects` per facet.
