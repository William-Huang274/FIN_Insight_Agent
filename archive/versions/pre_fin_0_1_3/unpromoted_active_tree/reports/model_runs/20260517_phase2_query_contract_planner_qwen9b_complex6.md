# Model Run: 20260517_phase2_query_contract_planner_qwen9b_complex6

## Summary
- Purpose: 用 Qwen3.5-9B 为 6 个 `complex_insight` query 生成第一层 `Query Contract`，验证它能否作为后续 Evidence Pack / Exact-Value Ledger 的 query intent 边界。
- Status: completed.
- Run type: inference + validation.
- Timestamp: 2026-05-17 CST.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, single NVIDIA RTX 4090, local validation on `D:\FIN_Insight_Agent`.
- Decision label: diagnostic-only.

## Code And Command
- Git commit: `820df59` with dirty worktree from current phase artifacts and scripts.
- Entry points:
  - `scripts/run_query_contract_planner.py`
  - `scripts/normalize_query_contracts.py`
  - `scripts/validate_query_contracts.py`
- Cloud planner command:

```bash
/root/miniconda3/bin/python scripts/run_query_contract_planner.py \
  --eval-path eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl \
  --grouped-pool-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --output reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json \
  --query-id expanded_insight_ads_ai_infra_2023_2025 \
  --query-id expanded_insight_ai_capex_monetization_2023_2025 \
  --query-id expanded_insight_ai_semiconductor_durability_2023_2025 \
  --query-id expanded_insight_cloud_profitability_comparison_2023_2025 \
  --query-id expanded_insight_platform_services_recurring_quality_2023_2025 \
  --query-id expanded_insight_subscription_visibility_2023_2025 \
  --max-model-len 32768 --max-tokens 2200 --dtype float16 \
  --quantization none --gpu-memory-utilization 0.90 --cpu-offload-gb 0 \
  --max-num-seqs 1 --language-model-only --skip-mm-profiling --structured-json
```

- Local normalization and validation:

```powershell
python scripts\normalize_query_contracts.py `
  --input reports\query_contracts\sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts_raw.json `
  --output reports\query_contracts\sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json

python scripts\validate_query_contracts.py `
  --contracts-path reports\query_contracts\sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json `
  --output-path reports\quality\sec_tech_10k_expanded_v0_2_complex6_query_contract_validation.json
```

## Inputs
- Eval set: `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Evidence inventory: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Query cohort: 6 `complex_insight` queries only.
- Candidate boundary: planner sees query metadata, ideal facets, evidence needs, grouped facet inventory, and metric-family hints; it does not see full raw citation pool.
- Leakage guard: planner is instructed not to answer, not to cite object IDs, and not to emit exact numeric values.

## Model Parameters
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Runtime: vLLM text-only mode, structured JSON output.
- `max_model_len`: 32768.
- `max_tokens`: 2200.
- `dtype`: float16.
- `quantization`: none.
- `gpu_memory_utilization`: 0.90.
- `max_num_seqs`: 1.
- Seed: vLLM default seed 0.

## Outputs
- Canonical normalized contracts: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json`.
- Raw planner contracts: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts_raw.json`.
- Validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_query_contract_validation.json`.
- Summary: `reports/logs/qwen9b_query_contract_planner_complex6_summary.json`.
- Cloud log: `reports/logs/qwen9b_query_contract_planner_complex6.log`.

## Results
- Raw planner parse: `6/6` parsed.
- Normalized contract validation: `6/6` pass.
- Hard failures after normalization: none.
- Warnings after normalization: none.
- Facets: `30` total, `5` per query.
- Prompt token range: `1464` to `1791`.
- Runtime:
  - model load: `69.5401s`.
  - total run: `348.7041s`.
  - per-query generation: `43.2595s` to `56.0271s`.
- GPU notes from log/status:
  - model loading used about `16.8 GiB`.
  - process memory observed about `21408 MiB`.
  - KV cache size reported as `97,311` tokens at `max_model_len=32768`.

## Query-Level Notes
| Query | Parse | Validation | Normalization Notes |
| --- | --- | --- | --- |
| `expanded_insight_ai_capex_monetization_2023_2025` | parsed | pass | clamped one out-of-scope year and one malformed company coverage field. |
| `expanded_insight_ai_semiconductor_durability_2023_2025` | parsed | pass | clamped historical years and converted final facet to caveat. |
| `expanded_insight_subscription_visibility_2023_2025` | parsed | pass | converted final facet to caveat. |
| `expanded_insight_ads_ai_infra_2023_2025` | parsed | pass | clamped historical years and filled one empty facet metric-family list. |
| `expanded_insight_platform_services_recurring_quality_2023_2025` | parsed | pass | clamped historical years and converted final facet to caveat. |
| `expanded_insight_cloud_profitability_comparison_2023_2025` | parsed | pass | clamped one historical year and filled one empty facet metric-family list. |

## Experiment Governance
- Hypothesis: 9B can draft useful query-intent contracts, but deterministic validators must own scope and hard evidence boundaries.
- Decision target: 6/6 Query Contracts parse and pass hard validation before moving to Evidence Object Contract / Exact-Value Ledger.
- Baseline: no explicit Query Contract layer; prior v3 prompt contract only constrained final synthesis.
- Stop condition: if normalized contracts still fail hard validation, do not proceed to Driver Pack generation.
- Mainline decision: proceed to next diagnostic step because normalized contracts pass 6/6; keep this diagnostic-only because Driver Pack and final synthesis have not been run.

## Interpretation
9B is adequate for semantic intent drafting, facet grouping, and metric-family selection. It is not reliable enough to be the sole owner of scope: raw output put historical years such as 2020-2022 into `required_coverage`, produced one malformed company coverage field, and left some facet metric families empty. Therefore the accepted design is planner plus deterministic normalization and validation, not free-form planner output.

## Safety Notes
- No credentials are recorded in this run ledger.
- The canonical contract file preserves `raw_query_contract` and `normalization_notes` for audit.
- This run does not prove final answer quality. It only proves the first layer, Query Contract, can be generated and validated for 6 complex queries.
