# Model Run: 20260516_phase2_qwen35_small_verifier_smoke

## Summary

- Purpose: 将 BGE reranker 输出接成 evidence pool，并用小参 Qwen3.5 做 `direct/partial/false` verifier smoke。
- Status: diagnostic-only
- Run type: inference smoke + evaluation
- Timestamp: 2026-05-16
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 4090 24GB, conda base, Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.1.

## Code And Command

- Entry points:
  - `scripts/build_bge_evidence_pool.py`
  - `scripts/run_qwen_small_verifier.py`
  - `scripts/evaluate_small_verifier.py`
- Model path tested: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
- Commands:

```bash
python scripts/build_bge_evidence_pool.py --top-k 10 --object-max-chars 4000 --output-path reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl
python scripts/run_qwen_small_verifier.py --input-path reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl --output-path reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink.jsonl --model-name /root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B --device cuda --torch-dtype bfloat16 --batch-size 1 --max-length 4096 --max-new-tokens 160 --limit 10
python scripts/evaluate_small_verifier.py --predictions-path reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink.jsonl --report-path reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink_eval.json
```

## Inputs

- Evidence pool source: `reports/retrieval_eval/sec_tech_10k_object_bge_reranker_v2_m3_cloud_predictions.jsonl`
- Evidence pool output: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Pool size: 230 rows, 23 facets, top10 per facet.
- Object type counts: claim 134, metric 69, table 27.
- Label protocol: Codex-assisted first-pass object labels.

## Outputs

- `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_eval.json`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink_eval.json`

## Results

First prompt attempt:

- Rows: 10
- Parse status: 3 parsed, 7 invalid JSON
- Wall time: 190.3126s
- Cause: model emitted long `<think>` reasoning and often did not reach JSON within `max_new_tokens`.

No-think prompt attempt:

- Rows: 10
- Parse status: 10 parsed
- Wall time: 36.0561s
- Accuracy: 0.7000
- Macro F1: 0.6030
- Direct precision/recall/F1: 0.2500 / 1.0000 / 0.4000
- Partial precision/recall/F1: 1.0000 / 0.3333 / 0.5000
- False precision/recall/F1: 1.0000 / 0.8333 / 0.9091
- Policy keep direct: direct precision 0.25, relevant precision 0.75, false rate 0.25.

## Experiment Governance

- Hypothesis: small Qwen3.5 can serve as a second-stage semantic verifier over BGE topK evidence objects.
- Decision target: parseable JSON, materially better direct precision than BGE-only topK, and acceptable latency for top10 x 23 facets.
- Baseline to beat later: BGE top5 direct precision 0.6174 and false@5 0.6957 on the current object review labels.
- Stop condition: if the model cannot emit stable JSON, over-predicts direct, or is too slow without fast attention/linear-attention kernels, do not promote to mainline.
- Decision label: diagnostic-only.
- Mainline decision: keep BGE reranker as current reranker baseline; keep Qwen3.5 verifier code path, but do not run full 230-row evaluation until the Qwen3.5 runtime fast path or a smaller instruct checkpoint is available.

## Runtime Efficiency

- Qwen3.5-4B triggered torch fallback because `flash-linear-attention/causal-conv1d` fast path was unavailable.
- The installed `causal_conv1d_cuda` extension in base was ABI-incompatible with torch 2.11.0. The verifier script disables broken `causal_conv1d` availability and falls back to torch implementation to make the model load.
- Smoke speed after no-think prompt: about 3.6s/row including model loading; full 230-row run would be slow and not currently justified.

## Caveats And Next Step

- Smoke covered only one facet: `agent_daily_aapl_services_2025 / services_net_sales`.
- Some over-direct cases are affected by evidence object construction: table objects may include nearby context text that contains the target claim, while current labels may judge the table identity more strictly.
- Next step: either install compatible FLA/causal kernels for Qwen3.5, or switch the small verifier to a smaller instruction-following checkpoint before full evaluation.
