# Model Run: 20260516_phase2_qwen35_fastpath_2b4b_smoke

## Summary

- Purpose: 修复 Qwen3.5 verifier 的 causal/FLA fast path，并对 Qwen3.5-2B 与 Qwen3.5-4B 做同一 evidence pool 的 smoke 对比。
- Status: diagnostic-only
- Run type: environment build + inference smoke + evaluation
- Timestamp: 2026-05-16
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 4090 24GB, conda base, Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.1.

## Code And Command

- Entry points:
  - `scripts/run_qwen_small_verifier.py`
  - `scripts/evaluate_small_verifier.py`
- Code change:
  - Added `--require-fast-path` to fail before model loading when `causal_conv1d_cuda`, Transformers causal-conv1d availability, or flash-linear-attention availability is false.
  - Added load/generation split timing and `fast_path_status` to the verifier run report.
- Key model paths:
  - 4B: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
  - 2B: `/root/autodl-tmp/modelscope_cache/Qwen/Qwen3___5-2B`
- Representative strict fast-path command:

```bash
python scripts/run_qwen_small_verifier.py \
  --input-path reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl \
  --output-path reports/verifier/sec_tech_10k_qwen35_4b_require_fastpath_sanity2.jsonl \
  --model-name /root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B \
  --device cuda \
  --torch-dtype bfloat16 \
  --batch-size 1 \
  --max-length 4096 \
  --max-new-tokens 160 \
  --limit 2 \
  --require-fast-path
```

## Runtime Build

- Root cause: installed `causal-conv1d` 1.6.0 was ABI-incompatible with torch 2.11.0+cu130 and failed on `causal_conv1d_cuda` import.
- Fix path:
  - Installed CUDA 13 nvcc package `nvidia-cuda-nvcc==13.0.88`.
  - Aligned `nvidia-nvvm==13.0.88` and `nvidia-cuda-crt==13.0.88`; earlier 13.2.x NVVM generated PTX 9.2 while ptxas 13.0 accepted PTX 9.0.
  - Installed `cuda-cccl==1.0.0` for missing `nv/target` headers.
  - Built `causal-conv1d==1.6.2.post1` from source for RTX 4090 `sm_89`.
  - Added a temporary runtime symlink directory for `libcudart.so` because the pip runtime package only ships `libcudart.so.12`.
- Built wheel:
  - `/root/autodl-tmp/wheels/causal_conv1d_torch211_cu13_sm89/causal_conv1d-1.6.2.post1-cp312-cp312-linux_x86_64.whl`
- Verification:
  - `causal_conv1d_cuda` import: OK
  - `is_causal_conv1d_available`: true
  - `is_flash_linear_attention_available`: true
  - Strict sanity reports show `fallback_enabled=false`.

## Inputs

- Evidence pool: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Pool boundary: BGE reranker top10 per `(query_id, facet)`.
- Smoke subset: first 10 rows, one facet `agent_daily_aapl_services_2025 / services_net_sales`.
- Label protocol: Codex-assisted object labels in `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl`.

## Outputs

- 4B smoke:
  - `reports/verifier/sec_tech_10k_qwen35_4b_fastpath_smoke10.jsonl`
  - `reports/metrics/sec_tech_10k_qwen35_4b_fastpath_smoke10_metrics.json`
  - `reports/logs/qwen35_4b_fastpath_smoke10_20260516.log`
- 2B smoke:
  - `reports/verifier/sec_tech_10k_qwen35_2b_fastpath_smoke10.jsonl`
  - `reports/metrics/sec_tech_10k_qwen35_2b_fastpath_smoke10_metrics.json`
  - `reports/logs/qwen35_2b_fastpath_smoke10_20260516.log`
- Strict fast-path sanity:
  - `reports/verifier/sec_tech_10k_qwen35_4b_require_fastpath_sanity2.jsonl`
  - `reports/logs/qwen35_4b_require_fastpath_sanity2_20260516.log`
  - `reports/verifier/sec_tech_10k_qwen35_2b_require_fastpath_sanity2.jsonl`
  - `reports/logs/qwen35_2b_require_fastpath_sanity2_20260516.log`

## Results

Qwen3.5-4B fast-path smoke:

- Fast path warning: none observed.
- Rows: 10
- Parse status: 10 parsed
- Accuracy: 0.7000
- Macro F1: 0.6030
- Direct precision / recall / F1: 0.2500 / 1.0000 / 0.4000
- Partial precision / recall / F1: 1.0000 / 0.3333 / 0.5000
- False precision / recall / F1: 1.0000 / 0.8333 / 0.9091
- Keep-direct policy: kept 4 objects, direct precision 0.25, relevant precision 0.75, false rate 0.25.
- Full smoke generation time: 35.7215s for 10 rows.
- Strict sanity timing for 2 rows: load 78.8360s, generation 7.5353s, wall 86.3713s.

Qwen3.5-2B fast-path smoke:

- ModelScope id: `Qwen/Qwen3.5-2B`.
- Fast path warning: none observed.
- Rows: 10
- Parse status: 7 parsed, 3 invalid JSON
- Accuracy: 0.4000
- Macro F1: 0.5556
- Direct precision / recall / F1: 1.0000 / 1.0000 / 1.0000
- Partial precision / recall / F1: 0.5000 / 1.0000 / 0.6667
- False precision / recall / F1: 0.0000 / 0.0000 / 0.0000
- Keep-direct policy: kept 1 object, direct precision 1.0, relevant precision 1.0, false rate 0.0.
- Full smoke generation time: 146.9374s for 10 rows.
- Strict sanity timing for 2 rows: load 37.9768s, generation 9.8751s, wall 47.8519s.

## Interpretation

- The causal/FLA fast path is now technically usable on the current RTX 4090 cloud environment. Future verifier experiments can require it explicitly and fail fast instead of silently falling back.
- Qwen3.5-4B remains the better small-verifier candidate among these two. It emits stable JSON under the no-think prompt and preserves false rejection better than 2B, but still over-predicts direct on table/context boundary cases.
- Qwen3.5-2B is not a good current verifier baseline. Its raw outputs often become long explanations, hit the 160-token cap, and truncate JSON. It also fails to reject false evidence in this smoke slice, so the apparent keep-direct precision comes from being extremely conservative rather than broadly useful.
- Cold model load dominates one-off command wall time. A real serving demo should keep the verifier resident; otherwise load time hides the actual per-candidate verifier cost.

## Experiment Governance

- Hypothesis: compiling the causal/FLA fast path should remove the runtime fallback blocker and make Qwen3.5 small-verifier experiments valid under the intended model architecture.
- Decision target: strict fast-path import and Transformers availability must be true; smoke outputs must be parseable enough to justify full 230-row evaluation.
- Ceiling / upper bound: BGE top10 evidence pool already covers the current candidate boundary; this run tests only verifier behavior inside that pool.
- Baselines to beat later: BGE reranker selected top5 direct P@5 0.6174, nDCG@5 0.9458, false@5 0.6957; rule verifier selected relevant precision 0.9294 under Codex-assisted labels.
- Stop conditions: do not promote a small verifier if it cannot emit stable JSON, cannot reject false objects, or requires fallback kernels.
- Efficiency gate: strict fast path must be available; full evaluation should be run only after the model candidate is likely to be useful.
- Decision label: diagnostic-only.
- Mainline decision: keep BGE as current reranker baseline. Keep 4B strict-fast-path verifier as the next semantic verifier candidate; do not use 2B as mainline without prompt/decoder changes and a larger validation slice.

## Runtime Efficiency

- Build time was spent on CUDA extension compilation; future reruns can install the saved wheel directly.
- 4B generation speed after load is roughly 3.6-3.8s/row at batch size 1 on the smoke prompt.
- 2B generation speed is unstable because several outputs hit the token cap; model size alone did not make it faster for this structured verifier task.
- Serving implication: use a resident process and batched candidate verification. Cold-start shell runs are not representative of final serving latency.

## Caveats And Next Step

- Smoke covered only the first 10 rows and one facet; it is not a full verifier evaluation.
- Metrics still rely on Codex-assisted labels, not final human gold.
- Next step: tune the verifier prompt/decoder for short JSON, then run a full 230-row 4B strict-fast-path evaluation before considering verifier integration into the evidence pool.

## Follow-up: Compact Verifier Output Sanity

- Timestamp: 2026-05-16
- Code change:
  - `scripts/run_qwen_small_verifier.py` now defaults to compact classification output.
  - Added `--debug-output-explanations`; only this mode asks for and persists `reason`, `missing_requirements`, and `raw_output`.
  - Default prompt schema is now `label/confidence/usable_for_synthesis` only.
- Cloud sanity command used Qwen3.5-4B with `--require-fast-path`, `--max-new-tokens 64`, `--limit 2`, and no debug flag.
- Output:
  - `reports/verifier/sec_tech_10k_qwen35_4b_compact_sanity2.jsonl`
  - `reports/logs/qwen35_4b_compact_sanity2_20260516.log`
- Result:
  - Rows: 2
  - Parse status: 2 parsed
  - Debug fields present in prediction rows: none
  - `debug_output_explanations`: false
  - Fast path: causal-conv1d true, FLA true, `fallback_enabled=false`
  - Generation time: 3.0531s for 2 rows
- Interpretation:
  - The default verifier path now behaves like a compact classifier.
  - Explanation-bearing output is explicitly a debug/audit mode, not the serving default.
