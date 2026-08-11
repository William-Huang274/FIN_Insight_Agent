# Model Run: 20260516_phase2_vllm_2b_cell_verifier_full

## Summary
- Purpose: 将 cell-level BGE evidence pool 的 Qwen3.5-2B verifier 从旧 transformers 单路批处理切到 vLLM 常驻批量推理，先解决 50-60 分钟不可接受的吞吐问题。
- Status: completed diagnostic
- Run type: verifier inference + calibrated pool export + synthesis evaluation
- Timestamp: 2026-05-16 Asia/Shanghai
- Environment: cloud RTX 4090 24GB, Python `/root/miniconda3/bin/python`, vLLM 0.21.0

## Code And Command
- Entry point: `scripts/run_qwen_small_verifier_vllm.py`
- Planned command: `python scripts/run_qwen_small_verifier_vllm.py --input-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bge_aspect_evidence_pool.jsonl --output-path reports/verifier/sec_tech_10k_expanded_v0_2_cell_qwen35_2b_aspect_verifier_vllm.jsonl --model-path /root/autodl-tmp/modelscope_cache/Qwen/Qwen3___5-2B --dtype bfloat16 --max-model-len 4096 --max-num-seqs 64 --gpu-memory-utilization 0.86 --prompt-batch-size 512 --max-new-tokens 48 --object-text-chars 1800 --structured-json`
- Git commit: dirty workspace, no commit created.
- Seeds: not applicable.

## Inputs
- Evidence pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bge_aspect_evidence_pool.jsonl`
- Row count: 6,980 aspect-candidate rows.
- Candidate boundary: BGE reranked top candidates from structured SEC 10-K cell/object retrieval only.
- Leakage guard: verifier sees only task/aspect metadata and one structured evidence object; no baseline answer or expected conclusion is injected.

## Experiment Governance
- Hypothesis: vLLM batched generation should preserve the same verifier task contract while cutting full 6,980-row inference from roughly hour-level to sub-15-minute wall time on a single RTX 4090.
- Decision target: full verifier run completes without CPU offload, writes 6,980 parseable rows, generation throughput is at least 10 rows/sec after model load, and GPU memory stays within 24GB.
- Ceiling / upper bound: This run validates serving efficiency and produces a candidate verifier artifact; it does not by itself prove financial citation precision until calibrated export, synthesis, citation validation, and strict quality scoring are rerun.
- Baselines to beat: old Qwen3.5-2B transformers verifier path was too slow for the expanded cell pool; smoke200 vLLM run wrote 200 rows with generation throughput about 20 rows/sec after load.
- Split and leakage guard: Same v0.2 expanded query set and same BGE pool as the interrupted full-chain run; no tuning on final answer quality inside this verifier stage.
- Stop conditions: If vLLM falls back to CPU/offload, cannot parse JSON reliably, or generation throughput falls below 5 rows/sec after warmup, stop before downstream synthesis and inspect runtime/root cause.
- Efficiency gate: do not proceed to Qwen9B synthesis until the verifier artifact is complete and faster than the old route by a material margin.
- Decision label: proceed.
- Mainline decision: vLLM verifier runtime accepted for the next diagnostic mainline; final answer output is still not teacher-ready.

## Runtime Efficiency
- Smoke reference: 200 rows, generation wall time 9.8491 seconds, 20.3064 rows/sec; first-load wall time 217.1612 seconds due to vLLM compile/warmup.
- Full verifier result: 6,980/6,980 rows written; load wall time 179.2736 seconds, generation wall time 147.7203 seconds, total wall time 327.3133 seconds, generation throughput 47.2515 rows/sec.
- GPU behavior: Qwen3.5-2B ran on CUDA/vLLM with FlashAttention/Triton kernels, no CPU offload, `max_num_seqs=64`, `prompt_batch_size=512`, `gpu_memory_utilization=0.86`.
- Synthesis runtime: Qwen3.5-9B final synthesis used `max_model_len=16384`, `synthesis_max_tokens=1200`, short JSON schema, and finished in 578.2901 seconds including 69.8207 seconds model load.

## Outputs
- Verifier predictions: `reports/verifier/sec_tech_10k_expanded_v0_2_cell_qwen35_2b_aspect_verifier_vllm.jsonl`
- Verifier log: `reports/logs/qwen35_2b_vllm_cell_full_20260516.log`
- Calibrated pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool.jsonl`
- Grouped calibrated pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`
- Pool report: `reports/metrics/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_report.json`
- Synthesis output: `reports/demo/qwen9b_expanded_v0_2_cell_vllm_synthesis_demo_16k_shortjson.json`
- Chinese trace: `reports/demo/qwen9b_expanded_v0_2_cell_vllm_synthesis_trace_zh.md`
- Citation validation: `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_citation_validation_16k_shortjson.json`
- Strict quality report: `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_answer_quality_16k_shortjson.json`

## Results
- Verifier parse: all 6,980 rows parsed. Label distribution was `direct=2,993`, `partial=2,899`, `false=1,088`; direct confidence minimum was 0.90.
- Calibrated pool: 13 queries, 698 facets/aspects, 1,426 citation evidence objects, 3,247 background objects, and 150 missing aspects.
- Context packaging: 8k context would include only 300/698 aspects; 16k context improves this to 574/698 aspects, but still omits 124 aspects, mostly in the largest AI capex and subscription visibility queries.
- Synthesis parse: 12/13 parsed, 1/13 invalid JSON. Model self-quality was `mixed=12`, `good=1`.
- Citation validation: 11/13 pass, 2/13 repair required; no invalid object IDs, but 1 background-only citation and the invalid JSON query remain hard blockers.
- Strict answer quality: mean overall 0.5775, min 0.1299, max 0.8196, `teacher_ready_count=0`.
- Main blockers: `low_citation_use_rate=13`, `low_required_coverage=10`, `missing_machine_readable_cell_json=7`, `citation_or_number_warning=6`, `citation_validation_not_pass=2`, `invalid_or_repaired_json=1`.

## Follow-Up
- Fix the remaining table-output contract before treating any metric/table answer as training or judge material: synthesis should emit machine-readable cell JSON, and the numeric validator should verify `MetricObject/TableObject` values directly.
- Add post-synthesis repair for invalid JSON and background-only citations, but keep repaired outputs separate from raw model quality metrics.
- Revisit evidence memory strategy: even 16k context cannot carry all 698 cell/aspect items, so the next design should use task-specific evidence pools plus per-facet notes instead of trying to stuff all cell evidence into one final prompt.
