# Model Run: 20260516_phase2_qwen35_4b_aspect_verifier_eval

## Summary

- Purpose: 将 BGE top10 evidence pool 从 facet-level verifier task 扩展成 aspect-level verifier task，并用 compact Qwen3.5-4B strict-fast-path verifier 评估每个 `must_find` aspect 的 direct/partial/false 判断。
- Status: diagnostic-only
- Run type: inference evaluation + retrieval review
- Timestamp: 2026-05-16
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 4090 24GB, Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.1.

## Code And Command

- Entry points:
  - `scripts/build_aspect_evidence_pool.py`
  - `scripts/run_qwen_small_verifier.py`
  - `scripts/evaluate_aspect_verifier.py`
- Model: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
- Runtime: strict fast path required; causal-conv1d and flash-linear-attention available; `fallback_enabled=false`.
- Command profile:

```bash
python scripts/build_aspect_evidence_pool.py \
  --input-path reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl \
  --labels-path eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl \
  --output-path reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl

python scripts/run_qwen_small_verifier.py \
  --input-path reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl \
  --output-path reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl \
  --model-name /root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B \
  --device cuda \
  --torch-dtype bfloat16 \
  --batch-size 4 \
  --max-length 4096 \
  --max-new-tokens 64 \
  --require-fast-path

python scripts/evaluate_aspect_verifier.py \
  --predictions-path reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl \
  --report-path reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full730_metrics.json
```

## Inputs

- Source evidence pool: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Expanded aspect evidence pool: `reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl`
- Pool boundary: BGE reranker top10 per `(query_id, facet)`, then one verifier row per `must_find` aspect.
- Weak label protocol: aspect labels are derived from existing review candidate fields:
  - `matched_must_find` -> direct
  - `partial_must_find` -> partial
  - `missing_must_find` -> false
- Rows:
  - source rows: 230
  - aspect rows: 730
  - facets: 23
  - aspects: 73
  - weak aspect labels: direct 157, partial 261, false 312

## Outputs

- Predictions: `reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl`
- Metrics: `reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full730_metrics.json`
- Retrieval review: `reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full730_retrieval_review.csv`
- Log: `reports/logs/qwen35_4b_aspect_compact_full730_20260516.log`

## Results

Full compact aspect verifier:

- Rows: 730
- Parse status: 730 parsed, 0 invalid
- Accuracy: 0.5438
- Macro F1: 0.5057
- Gold label counts: direct 157, partial 261, false 312
- Predicted label counts: direct 287, partial 102, false 341

Class metrics:

- Direct precision / recall / F1: 0.5087 / 0.9299 / 0.6576
- Partial precision / recall / F1: 0.3627 / 0.1418 / 0.2039
- False precision / recall / F1: 0.6276 / 0.6859 / 0.6555

Policy metrics:

| Policy | Kept Objects | Avg / Aspect | Avg / Facet | Direct Precision | Relevant Precision | False Rate | Direct Aspect Recall On Gold-Direct | Relevant Aspect Recall On Gold-Relevant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE top10 aspect pool | 730 | 10.0000 | 31.7391 | 0.2151 | 0.5726 | 0.4274 | 1.0000 | 1.0000 |
| Qwen keep direct | 287 | 3.9315 | 12.4783 | 0.5087 | 0.8537 | 0.1463 | 1.0000 | 0.9851 |
| Qwen keep direct+partial | 389 | 5.3288 | 16.9130 | 0.3985 | 0.7481 | 0.2519 | 1.0000 | 0.9851 |

Coverage:

- BGE top10 pool has weak direct evidence for 48/73 aspects and weak relevant evidence for 67/73 aspects.
- Qwen keep-direct recovered 48/48 weak-gold direct aspects.
- Qwen keep-direct recovered relevant evidence for 66/67 weak-gold relevant aspects.
- Facets with all weak-gold direct aspects covered: 19/23.
- Facets with all weak-gold relevant aspects covered: 22/23.

## Retrieval Review

The retrieval review supports the aspect-level direction but also exposes weak-label noise:

- Aspects total: 73
- Aspects with predicted direct: 70
- Aspects with weak gold direct: 48
- Weak-gold direct aspects recovered by predicted-direct gold-direct evidence: 48/48
- Aspects with predicted direct but no weak gold direct: 22
- Aspects with at least one predicted-direct weak-false object: 16

Examples where the model selected semantically useful evidence but weak labels are conservative:

- AAPL `services_net_sales` / `advertising`: selected table text states Services net sales were higher from advertising, App Store, and cloud services; weak aspect label was partial.
- ADBE `arr_growth` / annual value of subscription contracts: selected ARR growth claim is useful to the aspect, while weak aspect label was false.
- ADBE `contract_caveats`: claims about generally non-cancellable contracts, limited cancellation rights, and RPO exclusions are semantically direct/near-direct for caveat analysis, but weak labels are often partial/false.
- NVDA `third_party_manufacturing_risk` / foundries: selected foundry and contract-manufacturing risk evidence is semantically useful but weak label was partial.
- AMZN `aws_segment_metrics`: selected claim that AWS operating income increased primarily due to increased sales is useful, but weak label was partial.

Clean direct examples:

- AAPL Services gross margin drivers and metrics are recovered from claim/table evidence.
- SNOW consumption visibility risk is recovered from claims about consumption-based recognition and limited visibility.
- MSFT cloud growth is recovered from Microsoft Cloud revenue and Azure growth evidence.

## Experiment Governance

- Hypothesis: aspect-level verifier tasks reduce the prompt/label mismatch seen in facet-level tasks and preserve wider evidence coverage for synthesis.
- Decision target: recover all weak-gold direct aspects while reducing BGE top10 false evidence before synthesis.
- Ceiling / upper bound: BGE top10 aspect pool has direct evidence for only 48/73 aspects under current weak labels, but relevant evidence for 67/73.
- Baselines:
  - BGE top10 aspect pool: direct precision 0.2151, relevant precision 0.5726, false rate 0.4274.
  - Facet-level Qwen keep-direct: 89 kept objects, direct precision 0.7416, relevant precision 0.9551, false rate 0.0449, 23/23 direct facet coverage.
- Stop conditions: do not promote aspect verifier metrics as final if weak labels are not human-reviewed or if aspect labels remain derived from object-level matched/partial/missing fields.
- Efficiency gate: strict fast path required; no torch fallback accepted.
- Decision label: diagnostic-only.
- Mainline decision: aspect-level verifier is the better semantic unit for recall/coverage, but current weak labels are not reliable enough for precision claims. Keep this path, then human-review aspect gold labels or add reranker score thresholds before promoting as a precision gate.

## Runtime Efficiency

- Batch size: 4
- Max length: 4096
- Max new tokens: 64
- Load wall time: 76.9277s
- Generation wall time: 434.2391s for 730 rows
- Total wall time: 511.1668s
- Shell elapsed: 513s
- Effective generation throughput: about 1.68 rows/sec excluding cold model load.
- Bottleneck diagnosis: small-verifier inference is now GPU fast-path, but row count grows linearly with number of aspects. Serving should batch aspect tasks and keep the model resident.

## Caveats And Next Step

- Current aspect labels are weak labels derived from earlier candidate review fields, not final human-reviewed gold.
- Aspect-level `direct` recall looks strong, but direct precision is understated when the weak label marks semantically useful evidence as partial/false.
- The next step is to convert a subset of aspect labels into human-reviewed gold, then calibrate BGE reranker score + Qwen verifier label/confidence as a two-stage evidence-pool policy.
