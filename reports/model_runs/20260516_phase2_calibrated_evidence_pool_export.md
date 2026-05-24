# Model Run: 20260516_phase2_calibrated_evidence_pool_export

## Summary

- Purpose: 将 aspect-level verifier 输出转成可供 synthesis 使用的 calibrated evidence pool，显式区分 `citation_evidence`、`background_evidence` 和 `missing_aspects`。
- Status: completed
- Run type: saved-prediction postprocessing + evaluation
- Timestamp: 2026-05-16
- Environment: local `D:\FIN_Insight_Agent`, Python 3.

## Code And Command

- Entry points:
  - `scripts/export_calibrated_evidence_pool.py`
  - `scripts/evaluate_calibrated_evidence_pool.py`

```powershell
python scripts\export_calibrated_evidence_pool.py
python scripts\evaluate_calibrated_evidence_pool.py
python -m py_compile scripts\export_calibrated_evidence_pool.py scripts\evaluate_calibrated_evidence_pool.py
```

## Inputs

- Aspect pool: `reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl`
- Qwen verifier predictions: `reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl`
- Human gold for evaluation only: `eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl`

## Outputs

- Aspect JSONL pool: `reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool.jsonl`
- Grouped query/facet/aspect pool: `reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool_grouped.json`
- Export report: `reports/metrics/sec_tech_10k_calibrated_evidence_pool_report.json`
- Human-gold evaluation: `reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json`

The formal pool was exported without human audit labels so downstream synthesis cannot leak manual labels.

## Policy

- Citation candidates: Qwen verifier label must be `direct` and confidence must be at least `0.90`.
- Citation selector: `verifier_confidence + 0.20 * rerank_score`, then confidence, then rerank, then pool rank.
- Max citations per aspect: 1.
- Background candidates: remaining Qwen `direct` or `partial` rows, up to 3 per aspect.
- Missing aspects: no confident Qwen direct candidate.

## Results

Export summary:

- queries: 6
- facets: 23
- aspects: 73
- citation evidence: 70
- background evidence: 178
- missing aspects: 3
- citation object types:
  - claim: 39
  - metric: 15
  - table: 16

Missing aspects:

- SNOW `customer_metrics`: `11,159 total customers`
- SNOW `rpo_visibility`: `weighted-average remaining life 2.4 years`
- ADBE `rpo_visibility`: `approximately 65% recognized over next 12 months`

Human-gold evaluation on reviewed rows:

- reviewed citation rows: 70
- citation human labels:
  - direct: 65
  - partial: 5
- citation precision: 0.9286
- broad relevance precision: 1.0000
- reject rate: 0.0000

The weighted selector improved over pure highest-confidence selection on the reviewed subset:

| Selector | Citation Precision | Selected Aspects |
| --- | ---: | ---: |
| highest confidence | 0.9000 | 70/73 |
| highest rerank | 0.8571 | 70/73 |
| confidence + 0.20 * rerank | 0.9286 | 70/73 |

Remaining non-direct citation cases are mostly definitional or specificity misses:

- AAPL App Store context does not by itself prove App Store drove 2025 Services net sales growth.
- ADBE ARR growth does not define ARR as annual subscription contract value.
- ADBE variable-consideration evidence is related but not the full RPO exclusion statement.
- NVIDIA CSP demand context does not say industry-standard servers from every major cloud provider.
- NVIDIA reduced supplier control does not explicitly say lack of guaranteed supply.

## Experiment Governance

- Hypothesis: a calibrated evidence pool with separate citation/background roles will reduce downstream synthesis noise without throwing away useful context.
- Decision target: keep citation precision above the previous 0.9000 policy while preserving 70/73 selected aspects and exposing missing aspects.
- Ceiling / upper bound: this evaluation is on a 90-row reviewed policy subset, not a full 730-row human gold pool.
- Baseline: highest-confidence Qwen direct selector had 0.9000 citation precision on the reviewed subset.
- Decision label: proceed.
- Mainline decision: use `confidence + 0.20 * rerank_score` as the first calibrated selector, but treat it as versioned and subject to revision after a larger reviewed subset.

## Caveats And Next Step

- The 0.20 rerank weight is calibrated on a small reviewed subset and should not be overfit into a final claim.
- Background evidence still contains some citation-grade direct alternates, which is acceptable for synthesis context but should be tracked if final citation selection needs multiple citations per aspect.
- Next step: run final synthesis against the grouped calibrated pool and explicitly report any `missing_aspects`.
