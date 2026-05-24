# Model Run: 20260517_phase2_driver_pack_qwen9b_complex6

## Summary
- Purpose: 为 6 个 `complex_insight` query 生成 `Decision Driver Evidence Pack`，验证 9B planner 是否能提供 driver 优先级，并用 deterministic normalization 控制证据 ID、coverage 和 numeric boundary。
- Status: diagnostic-only.
- Run type: inference + deterministic normalization + validation.
- Timestamp: 2026-05-17 CST.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, single NVIDIA RTX 4090; local Windows `D:\FIN_Insight_Agent` for normalization, validation, and log updates.
- Decision label: diagnostic-only.

## Code And Command
- Entry points:
  - `scripts/build_driver_pack_candidates.py`
  - `scripts/run_driver_pack_planner.py`
  - `scripts/normalize_driver_packs.py`
  - `scripts/validate_driver_packs.py`
- Cloud planner command:

```bash
/root/miniconda3/bin/python scripts/run_driver_pack_planner.py \
  --candidate-path reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json \
  --output reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b.json \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 131072 --max-tokens 2600 --dtype float16 \
  --quantization none --gpu-memory-utilization 0.95 --cpu-offload-gb 0 \
  --max-num-seqs 1 --language-model-only --skip-mm-profiling --structured-json
```

- Local normalization and validation:

```powershell
python scripts\normalize_driver_packs.py `
  --input reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b.json `
  --candidate-path reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json `
  --output reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json

python scripts\validate_driver_packs.py `
  --driver-pack-path reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json `
  --candidate-path reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json `
  --output-path reports\quality\sec_tech_10k_expanded_v0_2_complex6_driver_pack_qwen9b_normalized_validation.json
```

## Inputs
- Query Contracts: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json`.
- Evidence Object Contracts: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json`.
- Exact-Value Ledger: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`.
- Driver candidates: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json`.
- Candidate boundary: 6 queries, 30 facets, 274 candidate contracts, 240 candidate metrics, 16/16 primary facets with candidates.
- Leakage guard: planner sees candidate evidence IDs and compact previews; it is instructed not to write exact values in prose. Final normalized pack rebuilds all IDs from candidate facets.

## Model Parameters
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Runtime: vLLM text-only mode, structured JSON output.
- `max_model_len`: 131,072.
- GPU KV cache size in log: 139,914 tokens.
- `max_tokens`: 2,600.
- `dtype`: float16.
- `gpu_memory_utilization`: 0.95.
- `cpu_offload_gb`: 0.
- `max_num_seqs`: 1.
- Seed: vLLM default seed 0.

## Outputs
- Candidate pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json`.
- Candidate report: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidate_report.json`.
- Raw Qwen9B pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b.json`.
- Normalized Qwen9B pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json`.
- Raw validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_qwen9b_validation.json`.
- Normalized validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_qwen9b_normalized_validation.json`.
- Heuristic fallback pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_heuristic.json`.
- Heuristic validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_heuristic_validation.json`.
- Cloud log: `reports/logs/qwen9b_driver_pack_planner_complex6.log`.
- Summary JSON: `reports/logs/qwen9b_driver_pack_planner_complex6_summary.json`.

## Results
- Raw Qwen9B planner:
  - Parse status: `parsed=4`, `parse_error_fallback=2`.
  - Raw validation: `2/6` pass, `4/6` fail.
  - Main hard failures: invalid driver/metric IDs, invalid secondary/caveat IDs, background evidence used as core support, unsupported claimed company/year/facet coverage, exact values in pack prose, one global-claim coverage violation.
- Normalized Qwen9B pack:
  - Validation: `6/6` pass.
  - Hard failures: `0`.
  - Warnings: `0`.
  - Mean primary facet driver coverage rate: `1.0`.
- Heuristic fallback:
  - Validation: `6/6` pass.
  - Hard failures: `0`.
  - Warnings: `0`.
- Runtime:
  - Model load: `63.9399s`.
  - Total planner run: `375.3211s`.
  - Per-query generation: `24.0154s` to `70.2826s`.
  - Prompt tokens: `30,502` to `35,728`.

## Interpretation
- 9B can draft useful high-level driver and caveat prose, but raw structured fields are not reliable enough for production use.
- The serving-safe artifact is the normalized pack, not the raw planner output.
- The normalizer deliberately does not invent new finance judgments. It preserves model thesis/driver text where usable, then rebuilds `supporting_contract_ids`, `supporting_metric_ids`, `covered_companies`, `covered_years`, `covered_facets`, `metric_families`, and `global_claim_allowed` from the candidate facets.
- Exact values remain outside Driver Pack prose; final synthesis must cite only ledger `metric_id` values.

## Experiment Governance
- Hypothesis: Query Contract + Exact-Value Ledger + normalized Driver Pack will improve final synthesis coverage and conclusion calibration while avoiding unsupported broad claims.
- Decision target: 6 complex queries must pass Driver Pack hard validation before final synthesis uses the pack.
- Ceiling / upper bound: candidate builder covered 16/16 primary facets, so this stage is not blocked by primary facet absence.
- Baselines: heuristic Driver Pack and prior long-context contract v3 synthesis.
- Stop conditions: if normalized Driver Pack still fails ID/coverage/numeric gates, do not connect it to final synthesis.
- Mainline decision: proceed to driver-pack-conditioned final synthesis only with normalized packs.

## Runtime Efficiency
- Wall time: `375.3211s`.
- GPU memory: 128k vLLM run used the 4090 with about 139k KV-cache capacity.
- Throughput: logged output speed was about 19.9-26.3 tok/s after warmup; first query was slower due Triton JIT warmup.
- Efficiency diagnosis: acceptable for 6-query diagnostic. For production batch runs, keep resident model loaded and avoid per-run cold start.

## Safety Notes
- No credential was written to project artifacts.
- Local DNS for the cloud hostname failed during this run; direct IP connectivity worked for execution.
- Raw Qwen9B Driver Pack should remain diagnostic-only because it failed hard validation.
- Next step: add normalized Driver Pack input mode to final synthesis and validate answer quality, citation precision, and ledger-only numeric use.
