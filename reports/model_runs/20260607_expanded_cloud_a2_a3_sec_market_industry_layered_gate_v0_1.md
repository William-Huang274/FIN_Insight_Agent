# Model Run: 20260607_expanded_cloud_a2_a3_sec_market_industry_layered_gate_v0_1

## Summary

- Purpose: Resume the lost cloud handoff and run true cloud expanded A2/S3 and A3/S4 layered gates after local full238 A1-A5 had already passed.
- Status: A2/S3 and A3/S4 accepted diagnostic pass; A4/A5 cloud blocked by missing LLM provider key.
- Run type: retrieval/operator evaluation + coverage/reflection evaluation.
- Timestamp: 2026-06-07.
- Environment: cloud workspace `/root/autodl-tmp/fin_agent_sp500_stage/workspace`, Python `/autodl-fs/data/fin_agent_milvus_bge_m3/.venv/bin/python`, BGE on CUDA where available.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_coverage_reflection_gate.py`
- Main accepted runs:
  - `20260607_expanded_a2_cloud_sec_expanded_operator_gate_v0_2`
  - `20260607_expanded_a3_cloud_coverage_reflection_gate_v0_1`
- Relevant code changes:
  - SEC form inference for evidence/object ids missing `form_type`.
  - `margin` ledger alias expansion to audited income-statement base rows.
  - stale summary `output_dir` fallback for S3/S4 artifact roots.
- Seeds: deterministic gate scripts; no random seed used.
- Secrets: no SSH password or API key persisted in files.

## Inputs

- Activation summary: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260607_expanded_a1_research_lead_cost_aware_route_gate_deepseek_v0_1/activation_diagnostic.json`
- Relationship summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260607_expanded_s2_relationship_link_map_gate_deepseek_v0_1/universe_relationship_diagnostic.json`
- SEC evidence: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`
- BGE reranker: `/autodl-fs/data/fin_agent_milvus_bge_m3/models/bge-m3-local`
- Focused A2 ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/ledger/20260607_tier1_tier2_sec_full_source_focused_a2_ledger_from_object_sqlite_v0_2.duckdb`
- Market evidence: `data/processed_private/market/evidence_packs/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl`
- Industry evidence: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_evidence_rows.jsonl`

## Focused Ledger Build

- Output: `/autodl-fs/data/fin_agent_milvus_bge_m3/ledger/20260607_tier1_tier2_sec_full_source_focused_a2_ledger_from_object_sqlite_v0_2.duckdb`
- Source records scanned: `13584`
- Ledger facts written: `11280`
- Writer: `LedgerStoreBulkCsvWriter` / DuckDB CSV copy
- Elapsed: `4.573s`
- Scope: `AMZN/MSFT/NVDA/AMD/GOOGL`, fiscal years `2025/2026`, forms `10-K/10-Q`, primary SEC metric/table rows.
- Caveat: diagnostic focused ledger only; not a full combined Tier1+Tier2 ledger.

## Outputs

- A2/S3 summary: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_cloud_sec_expanded_operator_gate_v0_2/evidence_operator_diagnostic.json`
- A3/S4 summary: `eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_cloud_coverage_reflection_gate_v0_1/coverage_reflection_diagnostic.json`
- A2 log: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_cloud_sec_expanded_operator_gate_v0_2.log`
- A3 log: `eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_cloud_coverage_reflection_gate_v0_1.log`

## Results

### A2/S3 Evidence Operators

- Gate: `pass`
- Cases: `4/4`
- Tool calls: `14`
- SEC context rows: `146`
- Runtime ledger rows: `383`
- Market snapshot rows: `4`
- Industry snapshot rows: `10`
- SEC candidate count pre-rerank: `550`
- SEC candidates sent to BGE: `433`

Case rows:

- `ma_msft_capex_lookup`: runtime ledger `6`
- `ma_amzn_margin_focused`: context `6`, runtime ledger `111`
- `ma_nvda_amd_market_standard`: context `20`, runtime ledger `126`, market `2`
- `ma_ai_capex_supply_chain_deep`: context `120`, runtime ledger `140`, market `2`, industry `10`, relationship lookup/plan `42/42`

### A3/S4 Coverage / Reflection

- Gate: `pass`
- Cases: `4/4`
- second-pass allowed: `1`
- second-pass ran: `1`
- second-pass added rows: `0`
- missing requirement count: `1`

## Interpretation

- The earlier cloud A2 blocker was not BGE or SEC evidence absence. It came from form inference gaps, focused exact ledger absence, `margin` alias mismatch, missing cloud market/industry files, and stale Windows `output_dir` in relationship summary.
- A2/S3 and A3/S4 are now valid cloud diagnostics for the current expanded SEC retrieval/operator path.
- This is not yet an expanded full-chain acceptance run because A4/S5 and A5/S6-S8 require a cloud LLM key, and the ledger is focused rather than full combined Tier1+Tier2.

## Verification

- Local: `python -m pytest tests\test_sec_agent_ledger_store.py tests\test_eval_multi_agent_gate_config_roundtrip.py -q` -> `16 passed`
- Local py_compile for changed retrieval/gate/runtime files passed.
- Cloud py_compile for synced gate/runtime files passed where run.

## Next Decision

- Proceed with cloud A4/A5 only after a provider key is configured in the cloud environment.
- Before expanded full-chain replay, rebuild or locate a verified full combined Tier1+Tier2 exact-value ledger and rerun A2/A3 without the focused ledger shortcut.
