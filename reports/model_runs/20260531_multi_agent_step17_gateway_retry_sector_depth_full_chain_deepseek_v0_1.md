# Model Run: 20260531_multi_agent_step17_gateway_retry_sector_depth_full_chain_deepseek_v0_1

## Summary

- Purpose: validate Step17 sector-depth full-chain stability after adding LLM gateway transport retry and Specialist failure propagation.
- Status: accepted for diagnostic Step17 stability gate.
- Run type: inference evaluation.
- Timestamp: 2026-05-31 Asia/Shanghai.
- Environment: local Windows workspace, Python 3.10, CUDA BGE reranker requested with `--bge-device cuda`.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- LLM: DeepSeek `deepseek-v4-pro`.
- API key handling: process environment only; key not saved; raw LLM responses not saved.
- Gateway retry profile:
  - `LLM_GATEWAY_TRANSPORT_RETRIES=2`
  - `LLM_GATEWAY_TRANSPORT_RETRY_BACKOFF_S=5`
  - `LLM_GATEWAY_TRANSPORT_RETRY_MAX_BACKOFF_S=20`

```text
python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_gateway_retry_ai_infra_cuda_deepseek_v0_1 --case-id ma_real_sector_ai_infra_full_chain_real_retrieval --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --memo-max-tokens 2200 --strict

python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1 --category sector_depth --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --memo-max-tokens 2200 --strict
```

## Inputs

- Cases: `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
- SEC manifest: `data/processed_private/manifests/sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl`
- BM25 index: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027`
- Object BM25 index: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects`
- Market evidence: `data/processed_private/market/evidence_packs/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl`
- Industry evidence: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_evidence_rows.jsonl`
- BGE reranker: `D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`

## Outputs

- Single-case recovery summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_ai_infra_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- 4-case stability summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- Case-level scores and agent/tool ledgers:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1/*/real_chain_case_score.json`
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1/*/multi_agent_summary.json`

## Results

- Single AI infra recovery run:
  - gate: `pass`
  - cases: `1/1`
  - real Specialist quality: `1/1`
  - claim verification: `pass`
  - specialist verification: `pass`
- 4-case sector-depth stability run:
  - gate: `pass`
  - cases: `4/4`
  - pass rate: `1.0`
  - total tool calls: `39`
  - real retrieval required cases: `4`
  - real Specialist quality required cases: `4`
  - real Specialist quality passed: `4`
  - failed cases: `0`

| Case | Gate | Memo | Claim | Specialist | Tool calls | SEC calls | BGE candidates | CUDA |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| AI infra | pass | draft | pass | pass | 11 | 6 | 96 | true |
| Banking | pass | draft | pass | pass | 9 | 4 | 52 | true |
| Healthcare | pass | draft | pass | pass | 11 | 5 | 73 | true |
| Energy / Utilities | pass | draft | pass | pass | 8 | 4 | 60 | true |

## Interpretation

The earlier all-Specialist provider failure was not reproduced after adding gateway transport retry and rerunning the full chain. The 4-case run shows that Research Lead, Universe Relationship, evidence operators, role-specific Specialists, Memo Writer, Verifier, and Renderer can all be activated in the intended order with real retrieval and source-boundary checks. BGE runtime reported CUDA and positive rerank candidate counts in every case.

## Governance

- Decision label: `proceed` for broader diagnostic multi-turn/resume Step17 eval.
- Mainline status: diagnostic-only; not yet promoted to a frozen release gate.
- Stop conditions: future promotion should block on any dry-run evidence operator in real mode, missing BGE rerank candidates, Specialist route failure without bounded partial-scope caveat, or claim verification failure.
- Safety notes: API key and raw LLM responses were not persisted. Private source artifact paths are referenced only as reproducibility pointers.
