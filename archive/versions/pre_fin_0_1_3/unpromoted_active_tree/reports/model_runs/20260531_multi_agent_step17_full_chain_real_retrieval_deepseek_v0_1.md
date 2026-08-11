# Model Run: 20260531_multi_agent_step17_full_chain_real_retrieval_deepseek_v0_1

## Summary

- Purpose: Step17 diagnostic full-chain evaluation with real DeepSeek routing/specialist calls and real MCP/interactive retrieval for sector-depth cases.
- Status: accepted for diagnostic Step17 real-retrieval gate.
- Run type: inference evaluation.
- Timestamp: 2026-05-31 Asia/Shanghai.
- Environment: local Windows workspace, Python 3.10, torch `2.10.0+cu126`, CUDA available on `NVIDIA GeForce RTX 4060 Laptop GPU`.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Commands:

```text
python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6 --case-id ma_real_sector_ai_infra_full_chain_real_retrieval --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --strict

python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2 --case-id ma_real_sector_banking_full_chain_real_retrieval --case-id ma_real_sector_healthcare_full_chain_real_retrieval --case-id ma_real_sector_energy_utilities_full_chain_real_retrieval --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --strict
```

- LLM: DeepSeek `deepseek-v4-pro`.
- API key handling: injected via process environment only; key not saved; raw LLM responses not saved.
- Key code changes in this run:
  - `src/sec_agent/multi_agent_runtime.py`
  - `src/sec_agent/research_lead_llm.py`
  - `src/sec_agent/specialist_llm.py`
  - `scripts/eval_multi_agent_real_llm_chain.py`

## Inputs

- Cases: `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
- SEC manifest: `data/processed_private/manifests/sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl`
- BM25 index: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027`
- Object BM25 index: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects`
- Market evidence: `data/processed_private/market/evidence_packs/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl`
- Industry evidence: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_evidence_rows.jsonl`
- BGE reranker: `D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`

## Outputs

- AI infra summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6/real_chain_eval_summary.json`
- Cross-sector summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2/real_chain_eval_summary.json`
- Case-level scores and agent/tool ledgers:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6/*/real_chain_case_score.json`
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2/*/real_chain_case_score.json`

## Results

- AI infra run:
  - gate: `pass`
  - cases: `1/1`
  - total tool calls: `10`
  - real specialist evidence quality: `1/1`
  - SEC search calls: `5`
  - SEC search errors: `0`
  - BGE candidates sent: `80`
  - runtime CUDA: `true`
- Cross-sector run:
  - gate: `pass`
  - cases: `3/3`
  - total tool calls: `30`
  - real specialist evidence quality: `3/3`
  - banking: SEC calls `4`, errors `0`, BGE candidates sent `52`, CUDA `true`
  - healthcare: SEC calls `6`, errors `0`, BGE candidates sent `76`, CUDA `true`
  - energy/utilities: SEC calls `4`, errors `0`, BGE candidates sent `60`, CUDA `true`
- Runtime audit:
  - All four sector-depth cases activated `universe_relationship`, `sec_operator`, `eight_k_operator`, `market_operator`, and `industry_operator`.
  - All four cases ran in `deep_research`.
  - All required Specialist quality checks passed for Fundamental, Industry/Supply-Chain, Market-Valuation, and Risk.

## Interpretation

The initial AI infra diagnostic exposed two implementation issues: context-only `relationship_graph` was being passed into `sec_search_filings`, and Risk Specialist JSON output was too unconstrained for the previous token budget. Cross-sector diagnostics then exposed a Research Lead source-contract gap: non-AI sector-depth prompts with `relationship_graph` source tiers were routed as `standard_memo`. The implemented fixes close those gaps and the rerun passes the diagnostic Step17 real-retrieval gate.

## Governance

- Decision label: `proceed` for additional diagnostic Step17 multi-turn/resume eval work.
- Mainline status: diagnostic-only; not yet promoted to frozen release gate.
- Stop conditions: any future case with `sec_search_errors_absent=false`, `candidate_sent_to_bge=0` when SEC search is expected, missing `universe_relationship` on relationship source requests, or Specialist real evidence quality failure should block promotion.
- Safety notes: API key and raw LLM responses were not persisted. Private data paths are referenced but not copied into fixtures or worklog content.
