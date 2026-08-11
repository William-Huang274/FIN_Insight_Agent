# Model Run: 20260607_expanded_cloud_full_combined_603_assets_a2_a5_layered_gate_deepseek_v0_1

## Summary

- Purpose: Replace the focused A2 ledger and old full238 market/industry assets with verified full combined Tier1+Tier2 ledger plus 603-company market/industry assets, then finish cloud A2-A5 layered gates.
- Status: accepted layered cloud diagnostic; A2-A5 pass.
- Run type: retrieval/operator evaluation + coverage/reflection evaluation + DeepSeek inference evaluation.
- Timestamp: 2026-06-07.
- Environment: cloud workspace `/root/autodl-tmp/fin_agent_sp500_stage/workspace`; Python `/autodl-fs/data/fin_agent_milvus_bge_m3/.venv/bin/python`; BGE-M3 local model on cloud GPU where available; DeepSeek `deepseek-v4-pro` for A4/A5.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_coverage_reflection_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_specialist_layer_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_judgment_memo_gate.py`
- Code changes in this run:
  - A4 and A5 now resolve input artifact roots through the same stale-`output_dir` fallback already used by S3/S4.
  - Added A4/A5 config roundtrip tests for stale artifact roots.
- Secrets: SSH password, temporary OSS URLs, and DeepSeek key were used only for this session and were not persisted.
- Seeds: deterministic gate scripts; LLM temperature `0`.

## Inputs

- Activation summary: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260607_expanded_a1_research_lead_cost_aware_route_gate_deepseek_v0_1/activation_diagnostic.json`
- Relationship summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260607_expanded_s2_relationship_link_map_gate_deepseek_v0_1/universe_relationship_diagnostic.json`
- SEC evidence: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`
- Full asset upload root: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1`
- Combined ledger: `indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`
- Market evidence/catalog: `market/processed/evidence_packs/20260606_market_yahoo_chart_tier1_tier2_1y_v0_1_3m_market_evidence.jsonl`, `market/processed/market_snapshot_catalog.duckdb`
- Industry evidence/snapshot: `industry/processed/20260606_industry_fred_eia_tier1_tier2_merged_v0_1/industry_evidence_rows.jsonl`, `industry/processed/20260606_industry_fred_eia_tier1_tier2_merged_v0_1/industry_snapshot.duckdb`

## Input Contract Checks

- Combined ledger facts: `6789032`
- Combined ledger tickers: `581`
- Market evidence/snapshot/analytics rows: `603/603/603`
- Market daily bars: `151320`
- Industry evidence rows: `23`
- Industry observations: `27750`
- Package SHA256: `a3c351b7f9201313ada1676902660adadf757e1fe52dda972d686be03c5161d1`

## Outputs

- A2/S3: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_cloud_full_combined_603_assets_operator_gate_v0_1/evidence_operator_diagnostic.json`
- A3/S4: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_cloud_full_combined_603_assets_coverage_reflection_gate_v0_1/coverage_reflection_diagnostic.json`
- A4/S5: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260607_expanded_a4_cloud_full_combined_603_assets_specialist_gate_deepseek_v0_2/specialist_layer_diagnostic.json`
- A5/S6-S8: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260607_expanded_a5_cloud_full_combined_603_assets_judgment_memo_gate_deepseek_v0_1/judgment_memo_diagnostic.json`

## Results

### A2/S3 Evidence Operators

- Gate: `pass`
- Cases: `4/4`
- Tool calls: `14`
- Context rows: `146`
- Runtime ledger rows: `430`
- Market snapshot rows: `4`
- Industry snapshot rows: `9`
- SEC pre-rerank candidates: `550`
- SEC candidates sent to BGE: `433`

### A3/S4 Coverage / Reflection

- Gate: `pass`
- Cases: `4/4`
- second-pass allowed: `1`
- second-pass ran: `1`
- second-pass added rows: `0`
- missing requirement count: `1`

### A4/S5 Specialist

- Gate: `pass`
- Cases: `2/2`
- Specialist routes: `7`
- Route pass cases: `2`
- Real evidence quality pass cases: `2`
- Token usage: input `42872`, output `8164`, total `51036`
- Repair attempts: `0`

### A5/S6-S8 Judgment / Memo / Verifier

- Gate: `pass`
- Cases: `2/2`
- Memo route pass cases: `2`
- Verifier pass cases: `2`
- Memo profiles: `expanded=2`
- Token usage: memo writer `19094`, verifier `9288`, total `28382`
- Memo repair attempts: `0`

## Interpretation

- This supersedes the earlier cloud A2/A3 diagnostic that used a focused A2 ledger and old full238 market/industry assets.
- The A4 v0_1 failure was caused by stale relationship artifact root resolution, not missing relationship evidence or model failure. After fallback repair, the deep supply-chain case sees the S2 relationship rows and passes Specialist real-evidence quality.
- A2-A5 layered gates are now green for the expanded cloud asset path, but this is not yet A6 full-chain / multi-turn promotion evidence.

## Verification

- Local py_compile for changed A4/A5 scripts and config test passed.
- `python -m pytest tests\test_eval_multi_agent_gate_config_roundtrip.py -q` -> `4 passed`
- `python -m pytest tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_universe_relationship.py -q` -> `49 passed`
- Cloud py_compile for synced A4/A5 scripts passed.
- Cloud relationship artifact fallback check: `ma_ai_capex_supply_chain_deep` reads `42` relationship rows from the resolved S2 artifact root.

## Next Decision

- Proceed to A6 small-batch full-chain / multi-turn evaluation over 10-20 cases before setting the expanded path as the default agent route.
- Keep non-US global-public parser/profile-specific downloader and external relationship evidence as separate open data-source tasks.
